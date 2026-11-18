terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.30"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  # Remote state in the bank's own storage account (Central India), e.g.:
  # backend "azurerm" { resource_group_name = "tfstate-rg"  storage_account_name = "...", container_name = "tfstate", key = "udyampulse.tfstate" }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = false
    }
  }
}
