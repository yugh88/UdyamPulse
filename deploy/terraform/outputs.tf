output "resource_group" {
  value = azurerm_resource_group.main.name
}

output "aks_name" {
  value = azurerm_kubernetes_cluster.main.name
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "key_vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}

output "workload_identity_client_id" {
  description = "Put into the Helm value serviceAccount.annotations[azure.workload.identity/client-id]"
  value       = azurerm_user_assigned_identity.app.client_id
}

output "postgres_fqdn" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}
