// extract_ground_truth.mjs — CMP-CORP-CPG-js ground-truth extractor (v0.1.0).
//
// Reproducible, deterministic extraction of AST / CFG / call-graph / PDG ground
// truth for each program under programs/<id>/source/, written to
// programs/<id>/ground_truth/{ast,cfg,callgraph,pdg}.json.
//
// Methodology (DOC-CMP-CORP-CPG-js §3.4; see README.md §3 for command lines):
//   AST  : @typescript-eslint/typescript-estree 6.18.0 parses both JS and TS into
//          one ESTree-shaped AST. Canonical serialization: keys sorted, `parent`
//          back-refs stripped, source positions (loc/range) preserved.
//   CFG  : per FunctionDeclaration / FunctionExpression / ArrowFunctionExpression /
//          MethodDefinition. Statement-sequence edges + branch (if/for/while/switch)
//          + async-await suspension edges (tagged `await`) + generator `yield` edges.
//   CALL : statically-resolvable call sites only. Direct identifier calls and
//          method calls whose receiver/name resolves to a top-level/prototype
//          function are emitted as `(caller, callee, line)` triples tagged
//          `static`. Property-access calls whose target is NOT statically fixed
//          (registry[name](), obj[k]()), eval, new Function -> tagged `dynamic`
//          and EXCLUDED from gate precision/recall (CW-DETECT territory).
//          NOTE: v0.1.0 ground truth is the documented intraprocedural resolver
//          below, hand-verifiable on these small programs. v1.0.0 replaces it with
//          Jelly 1.4 (+ tsc --noEmit --declaration for TS type-informed edges) per
//          DOC §3.4 — see CLAR-CORP-07.
//   PDG  : intra-function def->use data-dependence edges over simple variable
//          declarations/assignments and their later identifier reads.
//
// This script is a PURE function of the source bytes: no wall-clock, no RNG,
// no FS-ordering dependence (entries are sorted). Re-running reproduces a
// byte-identical ground_truth/ tree and hence the same corpus_digest.

import { parse } from '@typescript-eslint/typescript-estree';
import { readFileSync, writeFileSync, readdirSync, statSync, mkdirSync } from 'fs';
import { join, dirname, extname, basename } from 'path';
import { fileURLToPath } from 'url';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROGRAMS_DIR = join(HERE, '..', 'programs');

const PARSE_EXTS = new Set(['.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx']);

// ---- canonical JSON (sorted keys, stable, LF-terminated) -------------------
function canonicalStringify(value) {
  return JSON.stringify(sortDeep(value), null, 2) + '\n';
}
function sortDeep(v) {
  if (Array.isArray(v)) return v.map(sortDeep);
  if (v && typeof v === 'object') {
    const out = {};
    for (const k of Object.keys(v).sort()) out[k] = sortDeep(v[k]);
    return out;
  }
  return v;
}

// ---- AST -------------------------------------------------------------------
// Strip volatile/back-ref fields; keep loc+range for position preservation.
function stripAst(node) {
  if (Array.isArray(node)) return node.map(stripAst);
  if (node && typeof node === 'object') {
    const out = {};
    for (const k of Object.keys(node)) {
      if (k === 'parent' || k === 'tokens' || k === 'comments') continue;
      out[k] = stripAst(node[k]);
    }
    return out;
  }
  return node;
}

function parseSource(text, ext) {
  return parse(text, {
    loc: true,
    range: true,
    jsx: ext === '.tsx' || ext === '.jsx',
    comment: false,
    tokens: false,
  });
}

// ---- function discovery ----------------------------------------------------
function functionName(node, parent) {
  if (node.id && node.id.name) return node.id.name;
  if (parent) {
    if (parent.type === 'VariableDeclarator' && parent.id && parent.id.name) return parent.id.name;
    if (parent.type === 'MethodDefinition' && parent.key && parent.key.name) return parent.key.name;
    if (parent.type === 'Property' && parent.key && parent.key.name) return parent.key.name;
    if (parent.type === 'AssignmentExpression' && parent.left) {
      const l = parent.left;
      if (l.type === 'MemberExpression' && l.property && l.property.name) return l.property.name;
    }
  }
  return '<anonymous>';
}

const FN_TYPES = new Set([
  'FunctionDeclaration',
  'FunctionExpression',
  'ArrowFunctionExpression',
]);

// walk producing (node, parent) pairs deterministically (source order)
function* walk(node, parent = null) {
  if (Array.isArray(node)) {
    for (const c of node) yield* walk(c, parent);
    return;
  }
  if (!node || typeof node !== 'object' || typeof node.type !== 'string') return;
  yield [node, parent];
  for (const k of Object.keys(node)) {
    if (k === 'loc' || k === 'range' || k === 'parent') continue;
    yield* walk(node[k], node);
  }
}

function line(node) {
  return node.loc ? node.loc.start.line : null;
}

// ---- CFG -------------------------------------------------------------------
// Lightweight statement-level CFG: nodes = statements within the function body
// (and nested blocks), edges = sequential + branch + loop-back + await/yield.
function buildCfg(fnNode, fnId) {
  const nodes = [];
  const edges = [];
  let counter = 0;
  const idOf = new Map();
  function nid(stmt) {
    if (!idOf.has(stmt)) {
      const id = `${fnId}#n${counter++}`;
      idOf.set(stmt, id);
      nodes.push({ id, kind: stmt.type, line: line(stmt) });
    }
    return idOf.get(stmt);
  }
  function edge(from, to, kind) {
    if (from && to) edges.push({ from, to, kind });
  }
  // entry
  const entry = { id: `${fnId}#entry`, kind: 'Entry', line: line(fnNode) };
  nodes.push(entry);

  const body = fnNode.body && fnNode.body.type === 'BlockStatement' ? fnNode.body.body : null;
  if (!body) {
    // expression-bodied arrow
    nodes.push({ id: `${fnId}#expr`, kind: 'Return', line: line(fnNode.body) });
    edge(entry.id, `${fnId}#expr`, 'seq');
    return { function: fnId, nodes, edges };
  }

  function seqStatements(stmts, prevId) {
    let prev = prevId;
    for (const s of stmts) {
      const cur = nid(s);
      edge(prev, cur, 'seq');
      // record await/yield suspension within the statement
      for (const [n] of walk(s)) {
        if (n === s) continue;
        if (FN_TYPES.has(n.type)) break; // do not descend into nested functions
        if (n.type === 'AwaitExpression') edge(cur, cur, 'await');
        if (n.type === 'YieldExpression') edge(cur, cur, 'yield');
      }
      if (s.type === 'IfStatement') {
        if (s.consequent) {
          const c = s.consequent.type === 'BlockStatement' ? s.consequent.body : [s.consequent];
          seqStatements(c, cur);
        }
        if (s.alternate) {
          const a = s.alternate.type === 'BlockStatement' ? s.alternate.body : [s.alternate];
          seqStatements(a, cur);
        }
      } else if (
        s.type === 'ForStatement' ||
        s.type === 'ForOfStatement' ||
        s.type === 'ForInStatement' ||
        s.type === 'WhileStatement' ||
        s.type === 'DoWhileStatement'
      ) {
        const b = s.body && s.body.type === 'BlockStatement' ? s.body.body : s.body ? [s.body] : [];
        const last = seqStatements(b, cur);
        edge(last, cur, 'loop-back');
      }
      prev = cur;
    }
    return prev;
  }
  seqStatements(body, entry.id);
  return { function: fnId, nodes, edges };
}

// ---- call graph ------------------------------------------------------------
// Resolve call targets against the set of named functions/methods in the file.
function buildCallGraph(ast, knownNames) {
  const edges = [];
  // collect (function -> calls) by walking and tracking enclosing function
  function collect(node, enclosing) {
    if (Array.isArray(node)) {
      for (const c of node) collect(c, enclosing);
      return;
    }
    if (!node || typeof node !== 'object' || typeof node.type !== 'string') return;

    let nextEnclosing = enclosing;
    if (FN_TYPES.has(node.type) || node.type === 'MethodDefinition') {
      nextEnclosing = node.__fnId || enclosing;
    }

    if (node.type === 'CallExpression' || node.type === 'NewExpression') {
      const callee = node.callee;
      let target = null;
      let tag = 'dynamic';
      if (callee.type === 'Identifier') {
        if (knownNames.has(callee.name)) {
          target = callee.name;
          tag = 'static';
        } else if (callee.name === 'Function') {
          tag = 'dynamic';
        }
      } else if (callee.type === 'MemberExpression') {
        if (callee.computed) {
          tag = 'dynamic'; // obj[name]()
        } else if (callee.property && callee.property.name) {
          const mname = callee.property.name;
          if (mname === 'call' || mname === 'apply' || mname === 'bind') {
            // X.prototype.add.call(...) / fn.bind(...) — resolve base method name
            if (
              callee.object &&
              callee.object.type === 'MemberExpression' &&
              callee.object.property &&
              callee.object.property.name &&
              knownNames.has(callee.object.property.name)
            ) {
              target = callee.object.property.name;
              tag = 'static';
            } else {
              tag = 'dynamic';
            }
          } else if (knownNames.has(mname)) {
            target = mname;
            tag = 'static';
          } else {
            tag = 'dynamic';
          }
        }
      }
      edges.push({
        caller: enclosing || '<module>',
        callee: target,
        line: line(node),
        tag,
      });
    }
    for (const k of Object.keys(node)) {
      if (k === 'loc' || k === 'range' || k === 'parent') continue;
      collect(node[k], nextEnclosing);
    }
  }
  collect(ast, null);
  return edges;
}

// ---- PDG -------------------------------------------------------------------
// Intra-function def->use edges over variable declarations + later reads.
function buildPdg(fnNode, fnId) {
  const defs = new Map(); // name -> {line}
  const edges = [];
  for (const [n] of walk(fnNode.body)) {
    if (FN_TYPES.has(n.type) && n !== fnNode) continue;
    if (n.type === 'VariableDeclarator' && n.id && n.id.name) {
      defs.set(n.id.name, line(n));
    } else if (
      n.type === 'AssignmentExpression' &&
      n.left &&
      n.left.type === 'Identifier'
    ) {
      defs.set(n.left.name, line(n));
    } else if (n.type === 'Identifier' && defs.has(n.name)) {
      const defLine = defs.get(n.name);
      const useLine = line(n);
      if (defLine != null && useLine != null && useLine > defLine) {
        edges.push({ var: n.name, def_line: defLine, use_line: useLine, kind: 'data' });
      }
    }
  }
  // dedupe + sort
  const seen = new Set();
  const out = [];
  for (const e of edges) {
    const k = `${e.var}:${e.def_line}:${e.use_line}`;
    if (!seen.has(k)) {
      seen.add(k);
      out.push(e);
    }
  }
  return { function: fnId, edges: out };
}

// ---- per-program driver ----------------------------------------------------
function listSourceFiles(srcDir) {
  const out = [];
  function rec(d) {
    for (const name of readdirSync(d).sort()) {
      const p = join(d, name);
      const st = statSync(p);
      if (st.isDirectory()) rec(p);
      else if (PARSE_EXTS.has(extname(name))) out.push(p);
    }
  }
  rec(srcDir);
  return out;
}

function extractProgram(progDir) {
  const srcDir = join(progDir, 'source');
  const gtDir = join(progDir, 'ground_truth');
  mkdirSync(gtDir, { recursive: true });

  const files = listSourceFiles(srcDir);
  const astOut = {};
  const cfgOut = {};
  const callOut = {};
  const pdgOut = {};
  let parsed = 0;
  let failed = 0;

  for (const f of files) {
    const rel = f.slice(srcDir.length + 1);
    const text = readFileSync(f, 'utf8');
    const ext = extname(f);
    let ast;
    try {
      ast = parseSource(text, ext);
      parsed++;
    } catch (e) {
      failed++;
      astOut[rel] = { parse_error: String(e.message || e) };
      continue;
    }
    astOut[rel] = stripAst(ast);

    // assign fn ids + collect known names
    const knownNames = new Set();
    const fns = [];
    for (const [node, parent] of walk(ast)) {
      if (FN_TYPES.has(node.type)) {
        const nm = functionName(node, parent);
        const fnId = `${rel}::${nm}@${line(node)}`;
        node.__fnId = fnId;
        fns.push({ node, name: nm, fnId });
        if (nm !== '<anonymous>') knownNames.add(nm);
      }
    }
    cfgOut[rel] = fns.map((f0) => buildCfg(f0.node, f0.fnId));
    pdgOut[rel] = fns.map((f0) => buildPdg(f0.node, f0.fnId));
    callOut[rel] = buildCallGraph(ast, knownNames);
  }

  writeFileSync(join(gtDir, 'ast.json'), canonicalStringify(astOut));
  writeFileSync(join(gtDir, 'cfg.json'), canonicalStringify(cfgOut));
  writeFileSync(join(gtDir, 'callgraph.json'), canonicalStringify(callOut));
  writeFileSync(join(gtDir, 'pdg.json'), canonicalStringify(pdgOut));

  return { program: basename(progDir), files: files.length, parsed, failed };
}

function main() {
  const progs = readdirSync(PROGRAMS_DIR)
    .filter((d) => statSync(join(PROGRAMS_DIR, d)).isDirectory())
    .sort();
  const report = [];
  for (const p of progs) {
    report.push(extractProgram(join(PROGRAMS_DIR, p)));
  }
  for (const r of report) {
    process.stdout.write(
      `${r.program}: files=${r.files} parsed=${r.parsed} failed=${r.failed}\n`,
    );
  }
}

main();
