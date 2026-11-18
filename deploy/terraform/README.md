# Terraform (Azure, Central India)

Skeleton of the production footprint. `location` only accepts Indian regions (`centralindia`, `southindia`,
`westindia`); anything else fails at plan time, before any resource is touched.

| Resource | Notes |
|---|---|
| AKS | Workload identity + OIDC issuer, Entra ID RBAC, local accounts off, Azure CNI overlay with Cilium network policy, 3 zones, KEDA add-on, Key Vault CSI driver, Container Insights |
| PostgreSQL Flexible Server 16 | Private (delegated subnet, no public access), zone-redundant HA, 35-day backups, geo-backup to South India |
| Azure Cache for Redis Premium | TLS 1.2 only, no public access, private endpoint, zone redundant |
| Key Vault Premium | RBAC, purge protection, private endpoint: JWT secret, field-encryption keys, connection strings |
| Storage (ZRS) | Memo PDFs; `audit-anchors` container with a 7-year immutability policy for the audit-chain head hash |
| Container Registry Premium | Admin user off; AKS pulls with its kubelet identity |
| User-assigned identity | Federated with the Helm release's service account: Key Vault and Blob access without stored credentials |

```bash
terraform init
terraform plan -out plan.tfplan     # review
terraform apply plan.tfplan
```

Validated with `terraform fmt -check` and `terraform validate` (azurerm ~> 4.30). This skeleton has not been
applied to a live subscription; sizing follows docs/CAPACITY.md.
