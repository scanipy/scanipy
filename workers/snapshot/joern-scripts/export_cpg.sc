// export_cpg.sc — CMP-SNAP-05 CLAR-SNAP-05 fixed in-image CPGQL export script.
//
// *** UNVERIFIED AGAINST A REAL JOERN INSTALL ***
// No `joern` binary exists in the build sandbox this script was authored in
// (see analysis/cpg_ingest/joern_frontend.py + mapper.py module docstrings,
// and tests/cpg_ingest_fixtures.py). This is a best-effort,
// plausible CPGQL/Scala script built from Joern's well-documented DSL step
// names (`importCpg`, `cpg.all`, `.astChildren`, `.cfgNext`, `.label`,
// `.code`, `.name`, `.methodFullName`, `.fullName`, `.lineNumber`,
// `.columnNumber`, `.file.name`, low-level `.property(key)` generic
// accessors) and Joern's actual CDG/REACHING_DEF step names
// (`.controlledBy`/`.controls`, `.reachingDefIn`/`.reachingDefOut`). It MUST
// be diffed against a real `joern --script export_cpg.sc` run (Wave-2/Wave-4
// rehearsal, plan "Wave 4 — local rehearsal") before this is trusted in
// production, and every API assumption below is called out explicitly so
// that diff is fast to do.
//
// Design contract (CLAR-SNAP-05, mirrored in mapper.py's module docstring —
// keep both in sync if this script changes):
//   - Parameterized via TWO env vars (never CLI flags — JOERN_ARGV_ALLOWLIST
//     in tools/worker/secure_subprocess.py has --script but no generic
//     --param/--key=value flag, and widening that allowlist is out of this
//     component's scope, RULE-9):
//       SCANIPY_CPG_BIN_PATH   — path to the already-parsed cpg.bin to load
//       SCANIPY_EXPORT_JSON_PATH — path to write the flat JSON export to
//   - Output shape: {"nodes": [...], "edges": [...]} — a single JSON object,
//     UTF-8, written in one shot (no streaming) so joern_frontend.py's
//     `export_json_path.read_text()` sees a complete file or none at all.
//   - Node "id" is emitted as a STRING (`.id.toString`), never a raw Joern
//     Long — dodges the 2**53 JSON-safe-integer boundary a big Long id could
//     cross (mapper.py's RawJoernNode schema assumption #1).
//   - Every node object carries only: id, label, code, name, methodFullName,
//     fullName, filename, lineNumber, columnNumber — the exact
//     RawJoernNode/RawJoernEdge fields mapper.py's map_export() reads.
//     methodFullName/fullName/filename are OMITTED (not emitted as empty
//     strings) when the underlying Joern property is absent for that node's
//     type — mapper.py's `.get(...)` accessors already treat a missing key
//     the same as an empty one, so this keeps the export payload small
//     without changing mapper.py's observed behaviour.
//   - Edge "kind" is emitted VERBATIM as one of AST/CFG/CDG/REACHING_DEF —
//     the collapsing of CDG+REACHING_DEF into the CPGEdge.kind "PDG" value
//     is mapper.py's job (EDGE_KIND_MAP), not this script's. Any OTHER edge
//     kind Joern might expose (CALL, DDG, DOMINATE, ...) is intentionally
//     NOT emitted here yet — widening this is a CLAR-SNAP-05 follow-up
//     (mapper.py raises UnknownEdgeKindError fail-closed if it ever sees one
//     anyway, so omitting them here is the conservative default, not a
//     silent-drop hazard).

import scala.util.Try

@main def main(): Unit = {
  val cpgBinPath   = sys.env.getOrElse(
    "SCANIPY_CPG_BIN_PATH",
    throw new RuntimeException("SCANIPY_CPG_BIN_PATH not set (CLAR-SNAP-05 contract)")
  )
  val exportJsonPath = sys.env.getOrElse(
    "SCANIPY_EXPORT_JSON_PATH",
    throw new RuntimeException("SCANIPY_EXPORT_JSON_PATH not set (CLAR-SNAP-05 contract)")
  )

  importCpg(cpgBinPath)

  // --- JSON string escaping (minimal, hand-rolled — no external JSON lib
  //     assumed available in the Joern shell classpath). ---
  def jsonStr(s: String): String = {
    val escaped = s
      .replace("\\", "\\\\")
      .replace("\"", "\\\"")
      .replace("\n", "\\n")
      .replace("\r", "\\r")
      .replace("\t", "\\t")
    "\"" + escaped + "\""
  }
  def jsonIntOpt(o: Option[Integer]): String = o.map(_.toString).getOrElse("null")
  def jsonField(key: String, value: String): String = jsonStr(key) + ":" + value

  // Generic, node-type-agnostic property reader — every Joern StoredNode
  // exposes low-level `.property(key)` / `.propertyOption(key)` accessors on
  // top of the typed DSL (ASSUMPTION: exact method name may be
  // `.propertyOption` vs `.property(...).headOption`-style depending on the
  // Joern/OverflowDB version pinned in workers/pins.json — diff at Wave-4).
  def propOpt(n: nodes.StoredNode, key: String): Option[String] =
    Try(n.propertyOption(key)).toOption.flatten.map(_.toString).filter(_.nonEmpty)

  val allNodes = cpg.all.l

  val nodeJson = allNodes.map { n =>
    val fields = scala.collection.mutable.ArrayBuffer[String]()
    fields += jsonField("id", jsonStr(n.id.toString))
    fields += jsonField("label", jsonStr(n.label))
    propOpt(n, "CODE").foreach(v => fields += jsonField("code", jsonStr(v)))
    propOpt(n, "NAME").foreach(v => fields += jsonField("name", jsonStr(v)))
    propOpt(n, "METHOD_FULL_NAME").foreach(v => fields += jsonField("methodFullName", jsonStr(v)))
    propOpt(n, "FULL_NAME").foreach(v => fields += jsonField("fullName", jsonStr(v)))
    // .file.name: ASSUMPTION — the generic AstNode -> File traversal exists
    // on every node reachable here; wrapped in Try so a node type without it
    // (e.g. a META_DATA node) just omits "filename" rather than aborting the
    // whole export.
    Try(n.asInstanceOf[nodes.AstNode].file.name.headOption).toOption.flatten
      .foreach(v => fields += jsonField("filename", jsonStr(v)))
    Try(n.asInstanceOf[nodes.AstNode].lineNumber).toOption.flatten
      .foreach(v => fields += jsonField("lineNumber", v.toString))
    Try(n.asInstanceOf[nodes.AstNode].columnNumber).toOption.flatten
      .foreach(v => fields += jsonField("columnNumber", v.toString))
    "{" + fields.mkString(",") + "}"
  }

  // --- Edges: AST / CFG / CDG / REACHING_DEF only (script header note). ---
  // ASSUMPTION: `.astChildren`/`.cfgNext` are the standard Joern DSL steps;
  // CDG is exposed via control-dependence (`.controls`) and REACHING_DEF via
  // dataflow def-use (`.reachingDefOut`) steps on AstNode/CfgNode subtypes —
  // exact step names to confirm against the pinned Joern version at Wave-4.
  def astEdges(n: nodes.AstNode): List[String] =
    n.astChildren.l.map(c => (n.id.toString, c.id.toString, "AST"))
      .map { case (s, d, k) => "{" + jsonField("src", jsonStr(s)) + "," + jsonField("dst", jsonStr(d)) + "," + jsonField("kind", jsonStr(k)) + "}" }

  def cfgEdges(n: nodes.CfgNode): List[String] =
    Try(n.cfgNext.l).getOrElse(Nil).map(c => (n.id.toString, c.id.toString, "CFG"))
      .map { case (s, d, k) => "{" + jsonField("src", jsonStr(s)) + "," + jsonField("dst", jsonStr(d)) + "," + jsonField("kind", jsonStr(k)) + "}" }

  def cdgEdges(n: nodes.CfgNode): List[String] =
    Try(n.controls.collectAll[nodes.CfgNode].l).getOrElse(Nil).map(c => (n.id.toString, c.id.toString, "CDG"))
      .map { case (s, d, k) => "{" + jsonField("src", jsonStr(s)) + "," + jsonField("dst", jsonStr(d)) + "," + jsonField("kind", jsonStr(k)) + "}" }

  def reachingDefEdges(n: nodes.CfgNode): List[String] =
    Try(n.reachingDefOut.l).getOrElse(Nil).map(c => (n.id.toString, c.id.toString, "REACHING_DEF"))
      .map { case (s, d, k) => "{" + jsonField("src", jsonStr(s)) + "," + jsonField("dst", jsonStr(d)) + "," + jsonField("kind", jsonStr(k)) + "}" }

  val astNodes = allNodes.collect { case n: nodes.AstNode => n }
  val cfgNodes = allNodes.collect { case n: nodes.CfgNode => n }

  val edgeJson =
    astNodes.flatMap(astEdges) ++
    cfgNodes.flatMap(cfgEdges) ++
    cfgNodes.flatMap(cdgEdges) ++
    cfgNodes.flatMap(reachingDefEdges)

  val payload = "{" +
    jsonField("nodes", "[" + nodeJson.mkString(",") + "]") + "," +
    jsonField("edges", "[" + edgeJson.mkString(",") + "]") +
  "}"

  // Plain JDK IO (no extra library assumed on the Joern-shell classpath) —
  // single-shot write so a reader never observes a partial file.
  java.nio.file.Files.write(
    java.nio.file.Paths.get(exportJsonPath),
    payload.getBytes(java.nio.charset.StandardCharsets.UTF_8)
  )
}
