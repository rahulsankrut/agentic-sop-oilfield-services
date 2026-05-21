# Provider pins for the governance module.
#
# google-beta is required because Model Armor (template + floor settings) and
# the Agent Platform / Agent Identity surfaces are still Preview as of 2026-05.
# Some typed resources only exist on the -beta provider; some don't exist at
# all yet and are wrapped here via `null_resource` + `local-exec` against the
# Preview gcloud verbs (see agent_identities.tf and gateway_policies.tf).
#
# When the typed resources GA, swap the null_resource shims for the typed
# equivalents — every shim has a `# TODO: replace with typed resource when GA`
# marker right above it.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.30.0, < 7.0.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.30.0, < 7.0.0"
    }
    null = {
      source  = "hashicorp/null"
      version = ">= 3.2.0"
    }
    local = {
      source  = "hashicorp/local"
      version = ">= 2.4.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
