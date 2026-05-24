// Command derive produces tool-derived ground-truth CPG artifacts for one
// corpus item and writes ast.json, cfg.json, callgraph.json, and pdg.json into
// the item's ground_truth/ directory.
//
// Ground truth is *derived*, never hand-labelled (DOC-CMP-CORP-CPG-go §3.3):
//   - AST       : go/parser + go/ast node-kind counts and top-level decls.
//   - CFG        : golang.org/x/tools/go/ssa basic blocks per function (the
//     canonical reproducible CFG for Go).
//   - call graph : golang.org/x/tools/go/callgraph/cha (Class Hierarchy
//     Analysis) — the recall-safe over-approximation for dynamic
//     dispatch, matching the Stage-C soundness direction (INV-6,
//     call-edge recall floor >= 85%).
//   - PDG        : intra-function SSA def-use (data dependence) edges from the
//     SSA value graph — a reproducible dependence-edge baseline.
//
// Pin: Go toolchain and x/tools versions are recorded in methodology.md and
// tools/go.mod. Re-running this command on the same source under the same pins
// reproduces byte-identical JSON (keys are sorted; edges are sorted).
package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"golang.org/x/tools/go/callgraph/cha"
	"golang.org/x/tools/go/packages"
	"golang.org/x/tools/go/ssa"
	"golang.org/x/tools/go/ssa/ssautil"
)

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: derive <item-source-dir>")
		os.Exit(2)
	}
	srcDir := os.Args[1]
	outDir := filepath.Join(filepath.Dir(srcDir), "ground_truth")
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		die(err)
	}

	fset := token.NewFileSet()
	if err := deriveAST(fset, srcDir, outDir); err != nil {
		die(err)
	}
	if err := deriveSSA(srcDir, outDir); err != nil {
		die(err)
	}
	fmt.Printf("derived ground truth for %s\n", srcDir)
}

// astFileSummary is the per-file AST ground truth: counts of each node kind and
// the names of top-level declarations. Deterministic and reproducible.
type astFileSummary struct {
	File       string         `json:"file"`
	NodeKinds  map[string]int `json:"node_kinds"`
	TopLevel   []string       `json:"top_level_decls"`
	FuncDecls  []string       `json:"func_decls"`
	TypeDecls  []string       `json:"type_decls"`
	TotalNodes int            `json:"total_nodes"`
}

func deriveAST(fset *token.FileSet, srcDir, outDir string) error {
	entries, err := os.ReadDir(srcDir)
	if err != nil {
		return err
	}
	var summaries []astFileSummary
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".go") {
			continue
		}
		path := filepath.Join(srcDir, e.Name())
		f, err := parser.ParseFile(fset, path, nil, parser.ParseComments)
		if err != nil {
			return err
		}
		sum := astFileSummary{
			File:      e.Name(),
			NodeKinds: map[string]int{},
		}
		ast.Inspect(f, func(n ast.Node) bool {
			if n == nil {
				return false
			}
			kind := strings.TrimPrefix(fmt.Sprintf("%T", n), "*ast.")
			sum.NodeKinds[kind]++
			sum.TotalNodes++
			return true
		})
		for _, decl := range f.Decls {
			switch d := decl.(type) {
			case *ast.FuncDecl:
				name := d.Name.Name
				if d.Recv != nil && len(d.Recv.List) > 0 {
					name = recvTypeName(d.Recv.List[0].Type) + "." + name
				}
				sum.FuncDecls = append(sum.FuncDecls, name)
				sum.TopLevel = append(sum.TopLevel, name)
			case *ast.GenDecl:
				for _, spec := range d.Specs {
					if ts, ok := spec.(*ast.TypeSpec); ok {
						sum.TypeDecls = append(sum.TypeDecls, ts.Name.Name)
						sum.TopLevel = append(sum.TopLevel, ts.Name.Name)
					}
				}
			}
		}
		sort.Strings(sum.FuncDecls)
		sort.Strings(sum.TypeDecls)
		sort.Strings(sum.TopLevel)
		summaries = append(summaries, sum)
	}
	sort.Slice(summaries, func(i, j int) bool { return summaries[i].File < summaries[j].File })
	return writeJSON(filepath.Join(outDir, "ast.json"), map[string]any{
		"deriver": "go/parser+go/ast",
		"files":   summaries,
	})
}

func recvTypeName(e ast.Expr) string {
	switch t := e.(type) {
	case *ast.StarExpr:
		return "*" + recvTypeName(t.X)
	case *ast.Ident:
		return t.Name
	case *ast.IndexExpr:
		return recvTypeName(t.X)
	case *ast.IndexListExpr:
		return recvTypeName(t.X)
	}
	return "?"
}

// blockSummary is one SSA basic block: its index and successor indices.
type blockSummary struct {
	Index   int   `json:"index"`
	Succs   []int `json:"succs"`
	NumInst int   `json:"num_instructions"`
}

// cfgFuncSummary is the CFG ground truth for one function.
type cfgFuncSummary struct {
	Func   string         `json:"func"`
	Blocks []blockSummary `json:"blocks"`
}

// callEdge is one ground-truth call edge: caller -> callee (by SSA func name).
type callEdge struct {
	Caller  string `json:"caller"`
	Callee  string `json:"callee"`
	Dynamic bool   `json:"dynamic"`
}

// pdgEdge is one intra-function data-dependence edge (def -> use).
type pdgEdge struct {
	Func string `json:"func"`
	Def  string `json:"def"`
	Use  string `json:"use"`
}

func deriveSSA(srcDir, outDir string) error {
	cfg := &packages.Config{
		Mode: packages.LoadAllSyntax,
		Dir:  srcDir,
	}
	pkgs, err := packages.Load(cfg, ".")
	if err != nil {
		return err
	}
	if packages.PrintErrors(pkgs) > 0 {
		return fmt.Errorf("packages contain load errors")
	}
	prog, _ := ssautil.AllPackages(pkgs, ssa.InstantiateGenerics)
	prog.Build()

	cfgFuncs := []cfgFuncSummary{}
	pdgEdges := []pdgEdge{}
	funcs := ssautil.AllFunctions(prog)
	var ordered []*ssa.Function
	for fn := range funcs {
		if fn.Pkg == nil || fn.Blocks == nil {
			continue
		}
		// Only functions defined in the loaded packages (skip stdlib).
		if !isLocal(pkgs, fn) {
			continue
		}
		ordered = append(ordered, fn)
	}
	sort.Slice(ordered, func(i, j int) bool { return ordered[i].String() < ordered[j].String() })

	for _, fn := range ordered {
		cs := cfgFuncSummary{Func: fn.String()}
		for _, b := range fn.Blocks {
			bs := blockSummary{Index: b.Index, NumInst: len(b.Instrs)}
			for _, s := range b.Succs {
				bs.Succs = append(bs.Succs, s.Index)
			}
			sort.Ints(bs.Succs)
			cs.Blocks = append(cs.Blocks, bs)
		}
		cfgFuncs = append(cfgFuncs, cs)

		// PDG: def-use data dependence within the function.
		for _, b := range fn.Blocks {
			for _, instr := range b.Instrs {
				v, ok := instr.(ssa.Value)
				if !ok {
					continue
				}
				refs := v.Referrers()
				if refs == nil {
					continue
				}
				for _, r := range *refs {
					rv, ok := r.(ssa.Value)
					name := r.String()
					if ok {
						name = rv.Name() + "=" + r.String()
					}
					pdgEdges = append(pdgEdges, pdgEdge{
						Func: fn.String(),
						Def:  v.Name(),
						Use:  name,
					})
				}
			}
		}
	}
	sort.Slice(pdgEdges, func(i, j int) bool {
		if pdgEdges[i].Func != pdgEdges[j].Func {
			return pdgEdges[i].Func < pdgEdges[j].Func
		}
		if pdgEdges[i].Def != pdgEdges[j].Def {
			return pdgEdges[i].Def < pdgEdges[j].Def
		}
		return pdgEdges[i].Use < pdgEdges[j].Use
	})

	if err := writeJSON(filepath.Join(outDir, "cfg.json"), map[string]any{
		"deriver": "x/tools/go/ssa",
		"funcs":   cfgFuncs,
	}); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(outDir, "pdg.json"), map[string]any{
		"deriver": "x/tools/go/ssa def-use (intra-procedural data dependence)",
		"edges":   pdgEdges,
	}); err != nil {
		return err
	}

	// Call graph via CHA (recall-safe over-approximation).
	cg := cha.CallGraph(prog)
	edges := []callEdge{}
	seen := map[string]bool{}
	for fn, node := range cg.Nodes {
		if fn == nil || !isLocal(pkgs, fn) {
			continue
		}
		for _, e := range node.Out {
			if e.Callee.Func == nil {
				continue
			}
			// Record edges whose callee is local, OR whose call site is a
			// dynamic dispatch (interface/func-value) regardless of callee pkg.
			dyn := e.Site != nil && e.Site.Common().IsInvoke()
			calleeLocal := isLocal(pkgs, e.Callee.Func)
			if !calleeLocal && !dyn {
				continue
			}
			ce := callEdge{
				Caller:  fn.String(),
				Callee:  e.Callee.Func.String(),
				Dynamic: dyn,
			}
			key := ce.Caller + "##" + ce.Callee + fmt.Sprintf("##%v", ce.Dynamic)
			if seen[key] {
				continue
			}
			seen[key] = true
			edges = append(edges, ce)
		}
	}
	sort.Slice(edges, func(i, j int) bool {
		if edges[i].Caller != edges[j].Caller {
			return edges[i].Caller < edges[j].Caller
		}
		return edges[i].Callee < edges[j].Callee
	})
	return writeJSON(filepath.Join(outDir, "callgraph.json"), map[string]any{
		"deriver": "x/tools/go/callgraph/cha",
		"edges":   edges,
	})
}

func isLocal(pkgs []*packages.Package, fn *ssa.Function) bool {
	pkg := fn.Pkg
	// Generic instantiations / wrappers may have a nil Pkg or a synthetic one;
	// fall back to the originating generic function's package (go1.22 ssa).
	if pkg == nil && fn.Origin() != nil {
		pkg = fn.Origin().Pkg
	}
	if pkg == nil {
		return false
	}
	path := pkg.Pkg.Path()
	for _, p := range pkgs {
		if p.PkgPath == path {
			return true
		}
	}
	return false
}

func writeJSON(path string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}

func die(err error) {
	fmt.Fprintln(os.Stderr, "derive: "+err.Error())
	os.Exit(1)
}
