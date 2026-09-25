import io.shiftleft.codepropertygraph.generated.GraphSchema

@main def main(): Unit = {
  val ns = GraphSchema.nodeLabels.toSeq.sorted.map { label =>
    val nk = GraphSchema.getNodeKindByLabel(label)
    val ps = GraphSchema.getNodePropertyNames(label).toSeq.sorted.map { p =>
      val pk = GraphSchema.getPropertyKindByName(p)
      p -> ujson.Obj("type" -> GraphSchema.getNodePropertyFormalType(nk, pk).getClass.getSimpleName.stripSuffix("$"),
                     "quantity" -> GraphSchema.getNodePropertyFormalQuantity(nk, pk).getClass.getSimpleName.stripSuffix("$"))
    }
    label -> ujson.Obj.from(ps)
  }
  val es = GraphSchema.edgeLabels.toSeq.sorted.map { label =>
    label -> GraphSchema.getEdgePropertyName(label).map(ujson.Str(_)).getOrElse(ujson.Null)
  }
  val payload = ujson.Obj("domain_version" -> "1.7.65", "nodes" -> ujson.Obj.from(ns), "edges" -> ujson.Obj.from(es))
  java.nio.file.Files.writeString(java.nio.file.Paths.get("/job/schema-catalog-stable.json"), ujson.write(payload, indent = 2) + "\n")
  println("SCHEMA_CATALOG_OK=" + ns.size)
}
