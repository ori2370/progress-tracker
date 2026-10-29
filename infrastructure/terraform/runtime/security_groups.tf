resource "aws_security_group" "app" {
  name_prefix = "${var.project_name}-app-"
  description = "Application server; initially accessed through Systems Manager."
  vpc_id      = aws_vpc.main.id

  egress {
    description = "Outbound access for AWS services and package downloads."
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-app"
  }
}