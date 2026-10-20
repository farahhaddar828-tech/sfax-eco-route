variable "region" {
  description = "Paris is the closest AWS region to Tunisia"
  type        = string
  default     = "eu-west-3"
}

variable "instance_type" {
  description = "k3s + Postgres + n8n + API need ~2-4 GB RAM. t3.micro (free tier, 1 GB) is too small."
  type        = string
  default     = "t3.medium"
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "admin_cidr" {
  description = "Your IP in CIDR form (e.g. 41.226.x.x/32) - SSH and the k8s API are only open to it"
  type        = string
}

variable "budget_email" {
  description = "Receives an alert when the monthly AWS spend forecast passes the limit"
  type        = string
}

variable "monthly_budget_usd" {
  type    = number
  default = 20
}
