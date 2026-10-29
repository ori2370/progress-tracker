output "vpc_id" {
  description = "VPC containing the application runtime."
  value       = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "Subnet used by the application server."
  value       = aws_subnet.public.id
}
output "instance_id" {
  description = "EC2 instance accessed through Systems Manager."
  value       = aws_instance.app.id
}

output "instance_public_ip" {
  description = "Public IPv4 address; inbound access is initially blocked."
  value       = aws_instance.app.public_ip
}

output "instance_ami_id" {
  description = "AMI selected for this deployment."
  value       = nonsensitive(aws_instance.app.ami)
}