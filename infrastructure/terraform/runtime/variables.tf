variable "project_name" {
  description = "Prefix used for resource names."
  type        = string
  default     = "progress-tracker"
}

variable "vpc_cidr" {
  description = "Private IPv4 range for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidr" {
  description = "Private IPv4 range for the public subnet."
  type        = string
  default     = "10.20.1.0/24"
}

variable "instance_type" {
  description = "EC2 instance type for the application server."
  type        = string
  default     = "t3.small"
}

variable "ecr_repository_name" {
  description = "Existing ECR repository containing application images."
  type        = string
  default     = "progress-tracker"
}