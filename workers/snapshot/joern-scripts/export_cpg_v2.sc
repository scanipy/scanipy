// R19-A: explicitly opt-in raw export, NOT a replacement for export_cpg.sc.
// Contract: docs/CONTRACT-BHMEA-JOERN-RAW-V2-2026-09-25.md.
// This exports observed facts only. No dispatch/binding/effect/purity proof.
import java.nio.ByteBuffer
import java.nio.charset.StandardCharsets.UTF_8
import java.nio.file.{Files, LinkOption, Path, Paths}
import java.security.MessageDigest
import java.util.jar.JarFile
import scala.jdk.CollectionConverters.*
import scala.util.control.NonFatal
import io.shiftleft.codepropertygraph.generated.GraphSchema

@main def main(): Unit = {
  def required(name: String): String = sys.env.getOrElse(name,
    throw new IllegalArgumentException(s"missing required environment key: $name"))
  def sha(path: Path): String = {
    val md = MessageDigest.getInstance("SHA-256")
    val in = Files.newInputStream(path)
    try {
      val buffer = new Array[Byte](65536)
      var count = in.read(buffer)
      while (count != -1) {
        md.update(buffer, 0, count)
        count = in.read(buffer)
      }
    } finally in.close()
    java.util.HexFormat.of().formatHex(md.digest())
  }
  def artifact(path: Path): ujson.Obj =
    ujson.Obj("path" -> path.toString, "sha256" -> sha(path))
  def tool(role: String, path: String, expected: String): ujson.Obj = {
    val jar = new JarFile(path)
    val version = try Option(jar.getManifest).flatMap(m =>
      Option(m.getMainAttributes.getValue("Implementation-Version"))).getOrElse(
      throw new IllegalArgumentException(s"missing jar version for $role"))
    finally jar.close()
    require(version == expected, s"unsupported runtime version for $role")
    val result = artifact(Paths.get(path))
    result("role") = ujson.Str(role)
    result("version") = ujson.Str(version)
    result
  }
  def native(value: Any): ujson.Value = value match {
    case s: String => ujson.Str(s)
    case i: Int => ujson.Num(i)
    case b: Boolean => ujson.Bool(b)
    case xs: scala.collection.Iterable[?] => ujson.Arr.from(xs.iterator.map(native))
    case xs: java.util.List[?] => ujson.Arr.from(xs.asScala.iterator.map(native))
    case xs: Array[?] => ujson.Arr.from(xs.iterator.map(native))
    case _ => throw new IllegalArgumentException("unsupported native property type")
  }
  def source(root: Path): ujson.Obj = {
    require(Files.isDirectory(root, LinkOption.NOFOLLOW_LINKS), "source root must be a directory")
    val walk = Files.walk(root)
    val entries = try walk.iterator().asScala.toVector finally walk.close()
    require(entries.forall(p => !Files.isSymbolicLink(p)), "source symlinks are unsupported")
    val files = entries.filterNot(p => Files.isDirectory(p, LinkOption.NOFOLLOW_LINKS))
    require(files.forall(p => Files.isRegularFile(p, LinkOption.NOFOLLOW_LINKS)),
      "source nonregular entries are unsupported")
    val ordered = files.map(p => (root.relativize(p).toString, p))
      .sortWith((a, b) => java.util.Arrays.compareUnsigned(a._1.getBytes(UTF_8), b._1.getBytes(UTF_8)) < 0)
    val md = MessageDigest.getInstance("SHA-256")
    md.update("scanipy-source-tree/1\u0000".getBytes(UTF_8))
    val records = ordered.map { case (name, path) =>
      val bytes = name.getBytes(UTF_8)
      val size = Files.size(path)
      val digest = sha(path)
      md.update(ByteBuffer.allocate(8).putLong(bytes.length.toLong).array())
      md.update(bytes)
      md.update(ByteBuffer.allocate(8).putLong(size).array())
      md.update(java.util.HexFormat.of().parseHex(digest))
      // ujson uses Double for numbers; reject sizes it cannot represent exactly.
      require(size <= 9007199254740991L, "source file size exceeds exact JSON integer range")
      ujson.Obj("path" -> name, "size" -> ujson.Num(size.toDouble), "sha256" -> digest)
    }
    ujson.Obj("root" -> root.toString, "tree_namespace" -> "scanipy-source-tree/1",
      "tree_sha256" -> java.util.HexFormat.of().formatHex(md.digest()),
      "files" -> ujson.Arr.from(records))
  }
  val output = Paths.get(required("SCANIPY_EXPORT_V2_JSON_PATH")).toAbsolutePath.normalize()
  require(!Files.exists(output, LinkOption.NOFOLLOW_LINKS), "output already exists")
  val cpgPath = Paths.get(required("SCANIPY_CPG_BIN_PATH")).toAbsolutePath.normalize()
  val scriptPath = Paths.get(required("SCANIPY_EXPORT_V2_SCRIPT_PATH")).toAbsolutePath.normalize()
  val sourceRoot = Paths.get(required("SCANIPY_EXPORT_V2_SOURCE_ROOT")).toAbsolutePath.normalize()
  val frontend = required("SCANIPY_EXPORT_V2_FRONTEND")
  val frontendArtifact = frontend match {
    case "javasrc" => "javasrc2cpg"
    case "pythonsrc" => "pysrc2cpg"
    case _ => throw new IllegalArgumentException("unsupported raw-v2 frontend")
  }
  val imageId = required("SCANIPY_EXPORT_V2_IMAGE_ID")
  require(imageId.matches("sha256:[0-9a-f]{64}"), "image ID must be caller-observed SHA256")
  val producer = ujson.Obj(
    "schema_version" -> 1,
    "image" -> ujson.Obj("kind" -> "docker-image-id", "reference" -> imageId,
      "observation" -> "caller-observed"),
    "tools" -> ujson.Arr(
      tool("joern-console", "/opt/joern/lib/io.joern.console-4.0.554.jar", "4.0.554"),
      tool("frontend", s"/opt/joern/frontends/$frontendArtifact/lib/io.joern.$frontendArtifact-4.0.554.jar", "4.0.554"),
      tool("cpg-domain", "/opt/joern/lib/io.shiftleft.codepropertygraph-domain-classes_3-1.7.65.jar", "1.7.65"),
      tool("flatgraph-core", "/opt/joern/lib/io.joern.flatgraph-core_3-0.1.31.jar", "0.1.31")),
    "script" -> artifact(scriptPath), "input_cpg" -> artifact(cpgPath),
    "source" -> source(sourceRoot), "frontend" -> frontend,
    "import_mode" -> "importCpg-default-overlays",
    "java_runtime_version" -> System.getProperty("java.runtime.version"),
    "java_tool_options" -> sys.env.getOrElse("JAVA_TOOL_OPTIONS", ""))

  def capabilities(rawStatus: String): ujson.Obj = {
    val raw = List("raw_nodes", "raw_edges", "typed_properties").map(k =>
      k -> ujson.Obj("status" -> rawStatus, "reason" ->
        (if (rawStatus == "completed") "enumerated pinned raw graph" else "raw export did not complete")))
    val unsupported = List("call_target_completeness", "actual_formal_binding",
      "return_result_binding", "effect_analysis", "purity_certification").map(k =>
      k -> ujson.Obj("status" -> "unsupported", "reason" -> "R19-A exports observations, not this derived proof"))
    ujson.Obj.from(raw ++ unsupported)
  }
  def publish(payload: ujson.Value): Unit = {
    val temporary = Files.createTempFile(output.getParent, ".raw-cpg-v2-", ".json")
    try {
      Files.writeString(temporary, ujson.write(payload) + "\n", UTF_8)
      Files.createLink(output, temporary) // Atomic no-clobber publication on the worker filesystem.
    } finally Files.deleteIfExists(temporary)
  }
  def envelope(status: String, ns: ujson.Value, es: ujson.Value, error: ujson.Value): ujson.Obj =
    ujson.Obj("format" -> "scanipy-joern-export", "format_version" -> 2,
      "status" -> status, "producer" -> producer, "capabilities" -> capabilities(status),
      "nodes" -> ns, "edges" -> es, "error" -> error)

  val payload = try {
    importCpg(cpgPath.toString)
    val metadataLanguages = cpg.metaData.language.l
    require(metadataLanguages == List(frontend.toUpperCase(java.util.Locale.ROOT)),
      "CPG metadata language does not match declared frontend")
    val nodesJson = cpg.all.l.sortBy(_.id).map { n =>
      val properties = n.propertiesMap.asScala.toSeq.sortBy(_._1).map { case (k, v) => k -> native(v) }
      val present = properties.map(_._1).toSet
      val nk = GraphSchema.getNodeKindByLabel(n.label)
      val missing = GraphSchema.getNodePropertyNames(n.label).toSeq.filter { key =>
        val pk = GraphSchema.getPropertyKindByName(key)
        GraphSchema.getNodePropertyFormalQuantity(nk, pk).getClass.getSimpleName == "QtyOne$" && !present(key)
      }.sorted
      ujson.Obj("id" -> n.id.toString, "kind" -> n.label, "properties" -> ujson.Obj.from(properties),
        "missing_properties" -> ujson.Arr.from(missing))
    }
    val edgesJson = cpg.graph.allEdges.map { e =>
      val properties = e.propertyMaybe match {
        case Some(value) =>
          val key = e.propertyName.getOrElse(throw new IllegalArgumentException("unnamed edge property"))
          ujson.Obj(key -> native(value))
        case None => ujson.Obj()
      }
      ujson.Obj("src" -> e.src.id.toString, "dst" -> e.dst.id.toString,
        "kind" -> e.label, "properties" -> properties)
    }.toVector.sortBy(e => (BigInt(e("src").str), BigInt(e("dst").str), e("kind").str, ujson.write(e("properties"))))
    envelope("completed", ujson.Arr.from(nodesJson), ujson.Arr.from(edgesJson), ujson.Null)
  } catch {
    case NonFatal(error) =>
      publish(envelope("failed", ujson.Null, ujson.Null,
        ujson.Obj("code" -> "raw-export-failed", "message" -> error.getClass.getSimpleName)))
      throw error
  }
  publish(payload)
  println("SCANIPY_RAW_V2_COMPLETED")
}
