# Terraform AWS Infrastructure — Agent Governance Guidelines

This project provisions AWS infrastructure using Terraform, managed via GitHub Actions CI/CD with remote state in S3 and DynamoDB locking. It follows a modular structure with reusable modules for VPC, EKS, RDS, and IAM. All changes are reviewed via `terraform plan` in CI before apply.

## 1. State & Locking

- **Remote State Mandatory**: All Terraform configurations MUST use S3 remote backend with DynamoDB locking. Local `terraform.tfstate` files committed to the repository are a 🔴 Critical finding — they may expose secrets and cause state conflicts.
- **State Isolation per Environment**: `dev`, `staging`, and `prod` MUST use separate S3 state keys and separate DynamoDB lock tables. Sharing state between environments is a 🔴 Critical finding.
- **No Manual Apply in Production**: Production applies MUST only occur via the CI/CD pipeline after a peer-reviewed `terraform plan` output. Direct `terraform apply` from a developer machine against production is a 🔴 Critical operational finding.

## 2. Provider & Module Versioning

- **Pin Provider Versions**: All providers MUST specify an exact or tightly bounded version constraint (`= 5.x.x` or `~> 5.0` with upper-bound reasoning). Unconstrained `>= x` is a 🟠 High finding.
- **Pin Module Sources**: External modules from Terraform Registry MUST pin to an exact version tag (`version = "x.y.z"`). No floating `latest` references.
- **Terraform Version Pinning**: The `required_version` constraint MUST be set in each root module. CI runners must use the same version via `.terraform-version` or `tfenv`.

## 3. Security & IAM

- **Least-Privilege IAM**: IAM policies MUST NOT use `"Action": "*"` or `"Resource": "*"` without an inline justification comment explaining why broad permissions are required. These are 🟠 High findings pending justification.
- **No Hardcoded Credentials**: AWS credentials, API keys, and database passwords MUST NOT appear in `.tf` files, `terraform.tfvars`, or CI/CD YAML. Use `sensitive = true` for variable declarations and inject via CI secrets.
- **Encryption at Rest**: S3 buckets MUST declare `server_side_encryption_configuration`. RDS instances MUST set `storage_encrypted = true`. Missing encryption is a 🟠 High finding.
- **VPC Endpoints**: Services communicating within AWS MUST use VPC endpoints where available (S3, DynamoDB, ECR). Traffic routed over public internet between AWS services is a 🟡 Medium finding.

## 4. Code Quality & Structure

- **Module Boundaries**: Reusable infrastructure components MUST be extracted into `modules/` with their own `variables.tf`, `outputs.tf`, and `README.md`. Monolithic root modules exceeding 300 lines are a 🟡 Medium finding.
- **Variable Descriptions**: Every `variable` block MUST include a `description` field. Variables without descriptions are a 🟢 Low finding — they reduce automated documentation quality.
- **Output Sensitive Values**: Any output that exposes a secret, password, or private key MUST be marked `sensitive = true`.

## 5. CI/CD Pipeline Standards

- **Plan Before Apply**: CI must run `terraform plan -out=tfplan` and surface the plan output as a PR comment before any `terraform apply` step.
- **Drift Detection**: A scheduled weekly `terraform plan` job must run against production and alert on any detected drift between state and actual infrastructure.
