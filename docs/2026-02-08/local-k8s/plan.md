# Local Kubernetes Deployment Plan

## Overview

Run Prefect server, workers, and workflow jobs inside a local Kind Kubernetes cluster with a local container registry. ArgoCD manages all deployments via GitOps.

## Architecture

```
Kind Cluster ("aqueduct")
├── argocd namespace
│   └── ArgoCD (manages everything via app-of-apps)
├── prefect namespace
│   ├── Prefect Server (Helm chart) + PostgreSQL
│   ├── Prefect Worker (Helm chart, polls kubernetes-pool)
│   └── Workflow Jobs (created by worker, hostPath mount for backups)
└── hostPath: /data/backups → host ~/aqueduct-backups

Local Registry (localhost:5001)
└── aqueduct-workflows:latest
```

## Key Decisions

1. **Single Docker image** for all workflows (shared dependencies)
2. **Official Prefect Helm charts** via ArgoCD remote chart support
3. **Prefect Blocks** for credentials (registered via port-forward)
4. **Direct hostPath mount** for backup data — no PV/PVC needed since all pods run on the same Kind node; supports concurrent workflow runs
5. **Kind local registry** on localhost:5001

## File Layout

```
Dockerfile                    # Single workflow image
prefect.yaml                  # Prefect deployment definitions
Makefile                      # Common operations
infra/kind/
  kind-config.yaml            # Cluster config
  setup-cluster.sh            # Create cluster + registry + ArgoCD
  teardown-cluster.sh         # Tear down everything
infra/k8s/apps/
  app-of-apps/test.yaml       # Modified: Prefect server + worker
  common/manifests/misc/
    prefect-namespace.yaml    # Namespace
```

## Known Limitations

- **Google Drive OAuth**: Token must be pre-generated on host
- **Base job template**: hostPath mount must be configured in the work pool after creation
- **hostPath is local-only**: wouldn't translate to a multi-node cluster
