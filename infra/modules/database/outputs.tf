output "db_instance_id" {
  value = aws_db_instance.scanipy.identifier
}

output "db_endpoint" {
  description = "host:port — non-sensitive; the credential is in Secrets Manager, not here"
  value       = "${aws_db_instance.scanipy.address}:${aws_db_instance.scanipy.port}"
}

output "security_group_id" {
  value = aws_security_group.database.id
}

output "db_subnet_group_name" {
  value = aws_db_subnet_group.scanipy.name
}
