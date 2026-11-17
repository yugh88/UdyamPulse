variable "prefix" {
  description = "Short name used in every resource name"
  type        = string
  default     = "udyampulse"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "location" {
  description = "Azure region. RBI and DPDP data residency: only Indian regions are accepted."
  type        = string
  default     = "centralindia"
  validation {
    condition     = contains(["centralindia", "southindia", "westindia"], var.location)
    error_message = "Data residency: location must be an Indian Azure region (centralindia, southindia, westindia)."
  }
}

variable "aks_node_count" {
  type    = number
  default = 3
}

variable "aks_node_size" {
  type    = string
  default = "Standard_D4s_v5"
}

variable "postgres_sku" {
  type    = string
  default = "GP_Standard_D4ds_v5"
}

variable "postgres_admin_login" {
  type    = string
  default = "udyamadmin"
}

variable "app_namespace" {
  description = "Kubernetes namespace of the Helm release (for the workload identity federation)"
  type        = string
  default     = "udyampulse"
}

variable "tags" {
  type = map(string)
  default = {
    workload       = "udyampulse"
    data_class     = "confidential"
    data_residency = "india"
  }
}
