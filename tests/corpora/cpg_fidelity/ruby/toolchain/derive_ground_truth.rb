# frozen_string_literal: true

# derive_ground_truth.rb  --  CMP-CORP-CPG-ruby ground-truth deriver
#
# Reproducible-by-construction ground truth for the Ruby CPG-fidelity corpus.
# Given a pinned Ruby source file, emit four JSON artifacts:
#
#   ast.json        full RubyVM::AbstractSyntaxTree node tree (type, line, children)
#   cfg.json        per-method control-flow graph (basic blocks + successor edges)
#   callgraph.json  call edges (LOWER BOUND, see methodology.md "Call graph")
#   pdg.json        intra-method def-use data-dependence edges (LOWER BOUND)
#
# This is the single, pinned annotation tool referenced by methodology.md.
# It depends only on the standard library shipped with the pinned Ruby toolchain
# (RubyVM::AbstractSyntaxTree + json + set). No gems, no network, no wall-clock,
# no global RNG -- output is a deterministic function of (source bytes, ruby ver).
#
# Usage:  ruby derive_ground_truth.rb <source.rb> <ground_truth_out_dir>
#
# Soundness direction (INV-6, DOC sec.5): the call graph and PDG are treated as
# a LOWER BOUND. Edges we emit are demonstrably present from the static AST; we
# never claim completeness. Dynamic-dispatch call sites (send / public_send /
# __send__ / method_missing / define_method / instance_eval / const_get / eval)
# are recorded as `dynamic_sites`, NOT resolved into edges, so the gate harness
# reads recall against this set as a lower bound.

require 'json'
require 'set'

ABORT_USAGE = 'usage: ruby derive_ground_truth.rb <source.rb> <out_dir>'

DYNAMIC_DISPATCH = %w[
  send public_send __send__ method_missing define_method
  instance_eval class_eval module_eval instance_exec
  const_get const_set eval
].freeze

# Higher-order indirect-call method names: the concrete callee behind these is a
# block/proc/lambda value, not a statically-fixed method. Recorded as dynamic.
HIGHER_ORDER_CALL = %w[call yield].freeze

# Method definitions that themselves implement dynamic dispatch. When a corpus
# item *defines* one of these, the open set of names it intercepts is a dynamic
# mechanism even though no `send`-style call site appears in the same file.
DYNAMIC_DEF_NAMES = %w[method_missing respond_to_missing?].freeze

def node?(x)
  x.is_a?(RubyVM::AbstractSyntaxTree::Node)
end

# --- AST -------------------------------------------------------------------

def ast_to_h(node)
  return node unless node?(node)

  {
    'type' => node.type.to_s,
    'line' => node.first_lineno,
    'children' => node.children.map { |c| ast_to_h(c) }
  }
end

# --- helpers ---------------------------------------------------------------

def each_node(node, &blk)
  return unless node?(node)

  blk.call(node)
  node.children.each { |c| each_node(c, &blk) if node?(c) }
end

def method_defs(root)
  defs = []
  each_node(root) do |n|
    case n.type
    when :DEFN
      defs << { name: n.children[0].to_s, body: n.children[1], node: n, kind: 'instance' }
    when :DEFS
      defs << { name: n.children[1].to_s, body: n.children[2], node: n, kind: 'singleton' }
    end
  end
  defs.sort_by { |d| [d[:node].first_lineno, d[:name]] }
end

def body_statements(body)
  return [] unless node?(body)

  inner = body.type == :SCOPE ? body.children[2] : body
  return [] unless node?(inner)

  if inner.type == :BLOCK
    inner.children.compact.select { |c| node?(c) }
  else
    [inner]
  end
end

# --- CFG -------------------------------------------------------------------

# Documented walker (methodology.md "Control-flow graph"):
#  * One linear basic block per maximal run of straight-line statements.
#  * A branch node (IF / UNLESS / WHILE / UNTIL / CASE) closes the current
#    block; its branches become successor blocks; control rejoins after.
#  * RETURN closes a block with an edge to the synthetic EXIT.
# Conservative, reproducible CFG; a LOWER BOUND for exception/ensure flow
# (documented in methodology.md sec.5).
class CFGBuilder
  BRANCH_TYPES = %i[IF UNLESS WHILE UNTIL CASE CASE2 CASE3].freeze

  def initialize
    @blocks = []
    @bid = 0
    @edges = []
  end

  def build(method_name, statements)
    @blocks = []
    @edges = []
    @bid = 0
    entry = new_block('ENTRY')
    exit_b = new_block('EXIT')
    last = walk(statements, entry, exit_b)
    add_edge(last, exit_b['id']) if last
    {
      'method' => method_name,
      'entry' => entry['id'],
      'exit' => exit_b['id'],
      'blocks' => @blocks,
      'edges' => @edges.uniq.sort_by { |e| [e['from'], e['to']] }
    }
  end

  private

  def new_block(kind, line = nil)
    b = { 'id' => "b#{@bid}", 'kind' => kind, 'line' => line, 'stmts' => [] }
    @bid += 1
    @blocks << b
    b
  end

  def add_edge(from_id, to_id)
    return unless from_id && to_id

    @edges << { 'from' => from_id, 'to' => to_id }
  end

  def walk(stmts, cur, exit_b)
    cur_id = cur['id']
    stmts.each do |s|
      next unless node?(s)

      if BRANCH_TYPES.include?(s.type)
        cur_id = walk_branch(s, cur_id, exit_b)
      elsif s.type == :RETURN
        block_for(cur_id)['stmts'] << stmt_repr(s)
        add_edge(cur_id, exit_b['id'])
        return nil
      else
        block_for(cur_id)['stmts'] << stmt_repr(s)
      end
    end
    cur_id
  end

  def walk_branch(node, cur_id, exit_b)
    join = new_block('JOIN', node.first_lineno)
    case node.type
    when :IF, :UNLESS
      _cond, then_b, else_b = node.children
      then_block = new_block('THEN', node.first_lineno)
      add_edge(cur_id, then_block['id'])
      then_out = walk(stmts_of(then_b), then_block, exit_b)
      add_edge(then_out, join['id']) if then_out
      if node?(else_b)
        else_block = new_block('ELSE', node.first_lineno)
        add_edge(cur_id, else_block['id'])
        else_out = walk(stmts_of(else_b), else_block, exit_b)
        add_edge(else_out, join['id']) if else_out
      else
        add_edge(cur_id, join['id'])
      end
    when :WHILE, :UNTIL
      _cond, body = node.children
      loop_block = new_block('LOOP', node.first_lineno)
      add_edge(cur_id, loop_block['id'])
      loop_out = walk(stmts_of(body), loop_block, exit_b)
      add_edge(loop_out, loop_block['id']) if loop_out
      add_edge(cur_id, join['id'])
    else # CASE family: one branch per when, all rejoining.
      add_edge(cur_id, join['id'])
      node.children.compact.each do |c|
        next unless node?(c)

        wb = new_block('WHEN', c.first_lineno)
        add_edge(cur_id, wb['id'])
        out = walk(stmts_of(c), wb, exit_b)
        add_edge(out, join['id']) if out
      end
    end
    join['id']
  end

  def stmts_of(node)
    return [] unless node?(node)
    return body_statements(node) if node.type == :SCOPE

    if node.type == :BLOCK
      node.children.compact.select { |c| node?(c) }
    else
      [node]
    end
  end

  def block_for(id)
    @blocks.find { |b| b['id'] == id }
  end

  def stmt_repr(node)
    { 'type' => node.type.to_s, 'line' => node.first_lineno }
  end
end

# --- Call graph (LOWER BOUND) ---------------------------------------------

def callgraph(root, defs)
  edges = []
  dynamic_sites = []
  defs.each do |d|
    # A def whose own name implements dynamic dispatch (method_missing /
    # respond_to_missing?) is itself a dynamic mechanism (lower-bound recall).
    if DYNAMIC_DEF_NAMES.include?(d[:name])
      dynamic_sites << {
        'caller' => d[:name], 'kind' => "def:#{d[:name]}", 'line' => d[:node].first_lineno
      }
    end

    each_node(d[:body]) do |n|
      case n.type
      when :CALL, :FCALL, :VCALL, :OPCALL, :QCALL
        mid = call_mid(n)
        next unless mid

        if DYNAMIC_DISPATCH.include?(mid)
          dynamic_sites << { 'caller' => d[:name], 'kind' => mid, 'line' => n.first_lineno }
        elsif HIGHER_ORDER_CALL.include?(mid)
          # block/proc/lambda invocation: callee is a value, not a fixed method.
          dynamic_sites << { 'caller' => d[:name], 'kind' => "higher-order:#{mid}", 'line' => n.first_lineno }
        else
          edges << {
            'caller' => d[:name], 'callee' => mid, 'line' => n.first_lineno,
            'node' => n.type.to_s
          }
        end
      when :YIELD
        dynamic_sites << { 'caller' => d[:name], 'kind' => 'higher-order:yield', 'line' => n.first_lineno }
      when :SUPER, :ZSUPER
        edges << {
          'caller' => d[:name], 'callee' => "super:#{d[:name]}",
          'line' => n.first_lineno, 'node' => n.type.to_s
        }
      end
    end
  end
  top_level_dynamic(root, defs, dynamic_sites)
  {
    'convention' => 'lower-bound',
    'edges' => edges.uniq.sort_by { |e| [e['line'], e['caller'], e['callee']] },
    'dynamic_sites' => dynamic_sites.uniq.sort_by { |s| [s['line'], s['kind']] }
  }
end

def call_mid(node)
  case node.type
  when :CALL, :QCALL, :OPCALL
    node.children[1]&.to_s
  when :FCALL, :VCALL
    node.children[0]&.to_s
  end
end

def top_level_dynamic(root, defs, sink)
  # RubyVM AST nodes are regenerated on each child access, so object identity
  # cannot be used to test containment. Instead use line spans: a dynamic site
  # is top-level only when its line falls outside every method-definition span.
  spans = defs.map { |d| def_line_span(d[:node]) }
  each_node(root) do |n|
    next unless %i[CALL FCALL VCALL QCALL].include?(n.type)

    mid = call_mid(n)
    next unless mid && DYNAMIC_DISPATCH.include?(mid)

    line = n.first_lineno
    next if spans.any? { |lo, hi| line >= lo && line <= hi }

    sink << { 'caller' => '<toplevel>', 'kind' => mid, 'line' => line }
  end
end

def def_line_span(def_node)
  lo = def_node.first_lineno
  hi = def_node.last_lineno
  [lo, hi]
end

# --- PDG (LOWER BOUND): intra-method def-use data dependence ---------------

def pdg(defs)
  methods = []
  defs.each do |d|
    events = []
    param_names(d[:node]).each do |pn|
      events << { kind: 'def', name: pn, line: d[:node].first_lineno }
    end
    each_node(d[:body]) do |n|
      case n.type
      when :LASGN, :DASGN, :DASGN_CURR
        events << { kind: 'def', name: n.children[0].to_s, line: n.first_lineno }
      when :LVAR, :DVAR
        events << { kind: 'use', name: n.children[0].to_s, line: n.first_lineno }
      end
    end
    edges = []
    last_def = {}
    events.sort_by { |e| e[:line] }.each do |e|
      if e[:kind] == 'def'
        last_def[e[:name]] = e[:line]
      elsif (dl = last_def[e[:name]])
        edges << { 'var' => e[:name], 'use_line' => e[:line], 'def_line' => dl }
      end
    end
    methods << {
      'method' => d[:name],
      'edges' => edges.uniq.sort_by { |x| [x['use_line'], x['var']] }
    }
  end
  { 'convention' => 'lower-bound', 'methods' => methods }
end

def param_names(def_node)
  scope = def_node.type == :DEFS ? def_node.children[2] : def_node.children[1]
  return [] unless node?(scope) && scope.type == :SCOPE

  tbl = scope.children[0]
  (tbl || []).map(&:to_s).reject { |s| s.start_with?('_') }
end

# --- main ------------------------------------------------------------------

def write_json(path, obj)
  File.write(path, "#{JSON.pretty_generate(obj)}\n")
end

def main
  abort ABORT_USAGE unless ARGV.length == 2

  src_path = ARGV[0]
  out_dir = ARGV[1]
  abort "no such file: #{src_path}" unless File.file?(src_path)

  Dir.mkdir(out_dir) unless Dir.exist?(out_dir)

  root = RubyVM::AbstractSyntaxTree.parse_file(src_path)
  defs = method_defs(root)

  ast = { 'ruby_version' => RUBY_VERSION, 'tree' => ast_to_h(root) }
  cfg = {
    'ruby_version' => RUBY_VERSION,
    'methods' => defs.map { |d| CFGBuilder.new.build(d[:name], body_statements(d[:body])) }
  }
  cg = callgraph(root, defs).merge('ruby_version' => RUBY_VERSION)
  pd = pdg(defs).merge('ruby_version' => RUBY_VERSION)

  write_json(File.join(out_dir, 'ast.json'), ast)
  write_json(File.join(out_dir, 'cfg.json'), cfg)
  write_json(File.join(out_dir, 'callgraph.json'), cg)
  write_json(File.join(out_dir, 'pdg.json'), pd)

  warn "derived ground truth for #{src_path} (#{defs.length} methods)"
end

main if $PROGRAM_NAME == __FILE__
