# Local Kubernetes Deployment

Run Aqueduct's Prefect workflows on a local Kind cluster with a local container registry.

## Prerequisites

- Docker (Colima or Docker Desktop)
- [kind](https://kind.sigs.k8s.io/) (installed by `infra/bootstrap-server.sh`)
- [kubectl](https://kubernetes.io/docs/tasks/tools/) (installed by `infra/bootstrap-server.sh`)
- [Helm](https://helm.sh/docs/intro/install/) (`brew install helm`)
- [ArgoCD CLI](https://argo-cd.readthedocs.io/en/stable/cli_installation/) (installed by `infra/bootstrap-server.sh`)

## Quick Start

```bash
# 1. Create the Kind cluster + local registry + ArgoCD
make cluster-up

# 2. Deploy Prefect server + worker via ArgoCD
make argocd-deploy

# 3. Wait for Prefect pods to be ready
kubectl wait --for=condition=ready --timeout=300s pod -l app.kubernetes.io/name=prefect-server -n prefect

# 4. In a separate terminal, port-forward the Prefect UI
make port-forward-prefect

# 5. Build image, create work pool, register blocks, deploy workflows
make setup
```

Prefect UI: http://localhost:4200
ArgoCD UI: https://localhost:8080 (run `make port-forward-argocd`)

## Architecture

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Kind cluster | Docker containers | Kubernetes runtime |
| Local registry | `localhost:5001` | Container image storage |
| ArgoCD | `argocd` namespace | GitOps deployment management |
| Prefect Server | `prefect` namespace | Workflow orchestration + UI |
| PostgreSQL | `prefect` namespace | Prefect metadata storage |
| Prefect Worker | `prefect` namespace | Polls work pool, creates Jobs |
| Workflow Jobs | `prefect` namespace | Actual workflow execution pods |

### Data Flow

1. Workflow code is built into `localhost:5001/aqueduct-workflows:latest`
2. Deployments are registered with Prefect server via `prefect deploy`
3. When triggered, Prefect worker creates a K8s Job using the image
4. The Job pod mounts `/data/backups` via hostPath (configured in the work pool base job template)
5. Backup data flows: Pod → hostPath mount → Kind node `/data/backups` → Host `~/aqueduct-backups`

### Credentials

Credentials are managed via Prefect Blocks (stored in PostgreSQL inside the cluster). To register blocks:

```bash
# Port-forward must be running
make register-blocks
```

This runs the block registration scripts against the Prefect API at `localhost:4200`.

## Common Operations

### Makefile Targets

```bash
make cluster-up          # Create Kind cluster + registry + ArgoCD
make cluster-down        # Tear down everything
make build               # Build Docker image
make push                # Build + push to local registry
make deploy              # Deploy all workflows to Prefect
make setup               # Full setup (push + work-pool + blocks + deploy)
make port-forward-prefect # Access Prefect UI at localhost:4200
make port-forward-argocd  # Access ArgoCD UI at localhost:8080
make register-blocks     # Register credential blocks
make create-work-pool    # Create kubernetes-pool work pool
make argocd-deploy       # Install app-of-apps Helm chart
make argocd-password     # Get ArgoCD admin password
make logs-server         # Tail Prefect server logs
make logs-worker         # Tail Prefect worker logs
make status              # Show cluster, registry, pods status
make test-registry       # Check what's in the local registry
```

### Updating Workflow Code

After modifying workflow files:

```bash
# Rebuild and push the image
make push

# Re-deploy to Prefect (if entrypoints changed)
make deploy
```

If only the code inside a flow changed (not entrypoints/names), just `make push` is enough — the next Job will pull the latest image.

### Adding a New Workflow

1. Create the workflow file in `workflows/`
2. Add a deployment entry to `prefect.yaml`
3. `make push && make deploy`

### Accessing Backup Data

Backup data written by workflow pods is available on the host at:

```
~/aqueduct-backups/
├── github/
├── reddit/
├── youtube/
└── ...
```

## Troubleshooting

### Pods stuck in ImagePullBackOff

The registry might not be connected to the Kind network:
```bash
docker network connect kind kind-registry
```

### Prefect worker can't connect to server

Check the server is running and the service exists:
```bash
kubectl get svc -n prefect
kubectl logs -n prefect -l app.kubernetes.io/name=prefect-worker
```

### Work pool not found

Create it manually:
```bash
make create-work-pool
```

### ArgoCD app not syncing

Check ArgoCD app status:
```bash
argocd app list
argocd app get prefect-server
argocd app sync prefect-server
```

### Registry not reachable

Verify the registry is running:
```bash
docker ps | grep kind-registry
curl localhost:5001/v2/_catalog
```

### Pod can't access backup directory

Ensure the Kind node has the mount:
```bash
docker exec aqueduct-control-plane ls /data/backups
```

Check that `~/aqueduct-backups` exists on the host.

## References

- [Kind local registry docs](https://kind.sigs.k8s.io/docs/user/local-registry/)
- [Prefect Helm charts](https://github.com/PrefectHQ/prefect-helm)
- [Prefect Kubernetes deployment guide](https://docs.prefect.io/v3/how-to-guides/deployment_infra/kubernetes)
- [Prefect server + worker tutorial](https://docs.prefect.io/v3/tutorials/server-and-worker)
