variable "github_oidc_subject" {
  description = "Exact GitHub OIDC subject allowed to assume the publishing role."
  type        = string

  default = "repo:ori2370@102467907/progress-tracker@1436853736:ref:refs/heads/main"
}