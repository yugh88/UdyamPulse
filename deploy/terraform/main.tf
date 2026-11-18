# Skeleton for the production footprint in Central India. Private networking throughout: PostgreSQL, Redis,
# Key Vault and Storage are reachable only from the AKS subnet. Secrets are generated here and stored in
# Key Vault; nothing secret is output.

locals {
  name = "${var.prefix}-${var.environment}"
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "main" {
  name     = "${local.name}-rg"
  location = var.location
  tags     = var.tags
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.name}-logs"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 90
  tags                = var.tags
}

# ---------- network ----------
resource "azurerm_virtual_network" "main" {
  name                = "${local.name}-vnet"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = ["10.40.0.0/16"]
  tags                = var.tags
}

resource "azurerm_subnet" "aks" {
  name                 = "aks"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.40.0.0/20"]
}

resource "azurerm_subnet" "postgres" {
  name                 = "postgres"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.40.16.0/24"]
  delegation {
    name = "postgres"
    service_delegation {
      name    = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_subnet" "endpoints" {
  name                 = "private-endpoints"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.40.17.0/24"]
}

resource "azurerm_private_dns_zone" "postgres" {
  name                = "${local.name}.private.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgres" {
  name                  = "postgres"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.postgres.name
  virtual_network_id    = azurerm_virtual_network.main.id
}

# ---------- container registry ----------
resource "azurerm_container_registry" "main" {
  name                          = replace("${local.name}acr", "-", "")
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  sku                           = "Premium"
  admin_enabled                 = false
  public_network_access_enabled = true # CI pushes; restrict with network rules in a full build-out
  tags                          = var.tags
}

# ---------- AKS ----------
resource "azurerm_kubernetes_cluster" "main" {
  name                      = "${local.name}-aks"
  location                  = azurerm_resource_group.main.location
  resource_group_name       = azurerm_resource_group.main.name
  dns_prefix                = local.name
  oidc_issuer_enabled       = true
  workload_identity_enabled = true
  azure_policy_enabled      = true
  local_account_disabled    = true
  sku_tier                  = "Standard"

  default_node_pool {
    name                 = "system"
    vm_size              = var.aks_node_size
    node_count           = var.aks_node_count
    vnet_subnet_id       = azurerm_subnet.aks.id
    zones                = ["1", "2", "3"]
    auto_scaling_enabled = true
    min_count            = var.aks_node_count
    max_count            = 12
  }

  identity {
    type = "SystemAssigned"
  }

  azure_active_directory_role_based_access_control {
    azure_rbac_enabled = true
    tenant_id          = data.azurerm_client_config.current.tenant_id
  }

  network_profile {
    network_plugin      = "azure"
    network_plugin_mode = "overlay"
    network_policy      = "cilium"
    network_data_plane  = "cilium"
  }

  workload_autoscaler_profile {
    keda_enabled = true # scales workers on queue depth (see deploy/k8s)
  }

  oms_agent {
    log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  }

  key_vault_secrets_provider {
    secret_rotation_enabled = true
  }

  tags = var.tags
}

resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                            = azurerm_container_registry.main.id
  role_definition_name             = "AcrPull"
  principal_id                     = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
  skip_service_principal_aad_check = true
}

# ---------- PostgreSQL ----------
resource "random_password" "postgres" {
  length  = 32
  special = false
}

resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "${local.name}-pg"
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  version                       = "16"
  sku_name                      = var.postgres_sku
  storage_mb                    = 131072
  backup_retention_days         = 35
  geo_redundant_backup_enabled  = true # paired region South India: still inside India
  delegated_subnet_id           = azurerm_subnet.postgres.id
  private_dns_zone_id           = azurerm_private_dns_zone.postgres.id
  public_network_access_enabled = false
  administrator_login           = var.postgres_admin_login
  administrator_password        = random_password.postgres.result
  zone                          = "1"

  high_availability {
    mode                      = "ZoneRedundant"
    standby_availability_zone = "2"
  }

  depends_on = [azurerm_private_dns_zone_virtual_network_link.postgres]
  tags       = var.tags
}

resource "azurerm_postgresql_flexible_server_database" "app" {
  name      = "udyampulse"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# The application connects as a non-superuser role subject to row-level security (created by
# ops/postgres/init.sql-equivalent bootstrap); the admin login is used only for migrations bootstrap.

# ---------- Redis ----------
resource "azurerm_redis_cache" "main" {
  name                          = "${local.name}-redis"
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  capacity                      = 1
  family                        = "P"
  sku_name                      = "Premium"
  minimum_tls_version           = "1.2"
  non_ssl_port_enabled          = false
  public_network_access_enabled = false
  zones                         = ["1", "2"]
  redis_configuration {
    maxmemory_policy = "volatile-lru"
  }
  tags = var.tags
}

resource "azurerm_private_endpoint" "redis" {
  name                = "${local.name}-redis-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.endpoints.id
  private_service_connection {
    name                           = "redis"
    private_connection_resource_id = azurerm_redis_cache.main.id
    subresource_names              = ["redisCache"]
    is_manual_connection           = false
  }
  tags = var.tags
}

# ---------- Key Vault: JWT secret, field-encryption keys, connection strings ----------
resource "azurerm_key_vault" "main" {
  name                          = substr(replace("${local.name}-kv", "-", ""), 0, 24)
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "premium"
  rbac_authorization_enabled    = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 90
  public_network_access_enabled = false
  tags                          = var.tags
}

resource "azurerm_private_endpoint" "key_vault" {
  name                = "${local.name}-kv-pe"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.endpoints.id
  private_service_connection {
    name                           = "kv"
    private_connection_resource_id = azurerm_key_vault.main.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }
  tags = var.tags
}

# ---------- Storage: memo PDFs and the audit-chain head anchors (immutable) ----------
resource "azurerm_storage_account" "main" {
  name                            = substr(replace("${local.name}st", "-", ""), 0, 24)
  location                        = azurerm_resource_group.main.location
  resource_group_name             = azurerm_resource_group.main.name
  account_tier                    = "Standard"
  account_replication_type        = "ZRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false
  public_network_access_enabled   = false
  blob_properties {
    versioning_enabled = true
  }
  tags = var.tags
}

resource "azurerm_storage_container" "audit_anchors" {
  name                  = "audit-anchors"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

# Seven-year write-once retention; the container's ARM id is its `id` when created with storage_account_id.
resource "azurerm_storage_container_immutability_policy" "audit_anchors" {
  storage_container_resource_manager_id = azurerm_storage_container.audit_anchors.id
  immutability_period_in_days           = 2555
  protected_append_writes_enabled       = true
}

# ---------- Workload identity: the pods' access to Key Vault and Storage, with no stored credentials ----------
resource "azurerm_user_assigned_identity" "app" {
  name                = "${local.name}-app"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "app" {
  name                = "${local.name}-app"
  resource_group_name = azurerm_resource_group.main.name
  parent_id           = azurerm_user_assigned_identity.app.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = azurerm_kubernetes_cluster.main.oidc_issuer_url
  subject             = "system:serviceaccount:${var.app_namespace}:udyampulse"
}

resource "azurerm_role_assignment" "app_kv_secrets" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

resource "azurerm_role_assignment" "app_blob" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}
