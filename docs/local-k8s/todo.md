# Local K8s - Implementation TODO

## Phase 1: Kind + Registry
- [x] Create `infra/kind/kind-config.yaml`
- [x] Create `infra/kind/setup-cluster.sh`
- [x] Create `infra/kind/teardown-cluster.sh`
- [x] Test cluster creation with registry

## Phase 2: Docker Image
- [x] Create `Dockerfile`
- [x] Test building image
- [x] Test pushing to localhost:5001
- [x] Verify workflows can import blocks from PYTHONPATH
- [x] Fix Pillow build deps (zlib1g-dev, libjpeg-dev, gcc)
- [x] Fix git safe.directory for hostPath-mounted repos
- [x] Guard block registration behind `__main__`

## Phase 3: Prefect Server via ArgoCD
- [x] Create `infra/k8s/apps/common/manifests/misc/prefect-namespace.yaml`
- [x] Update `infra/k8s/apps/app-of-apps/test.yaml`
- [x] Fix Helm values schema (uiConfig nesting)
- [x] Upgrade chart to 2026.2.5193506 (Prefect 3.6.16) to match client
- [x] Test ArgoCD deploys Prefect server
- [x] Verify UI accessible via port-forward

## Phase 4: Prefect Worker
- [x] Verify worker Helm chart deploys correctly
- [x] Verify worker connects to server
- [x] Create RBAC for worker to create K8s Jobs
- [x] Verify RBAC allows Job creation

## Phase 5: Workflow Deployments
- [x] Create `prefect.yaml`
- [x] Create work pool (auto-created by worker)
- [x] Configure base job template with hostPath mount + default image
- [x] Deploy workflows via `prefect deploy`
- [x] Test running GitHub workflow end-to-end

## Phase 6: Credentials
- [x] Register GitHub block via port-forward
- [x] Test GitHub workflow end-to-end (91 repos cloned to ~/aqueduct-backups)

## Phase 7: Automation
- [x] Create `Makefile`
- [ ] Test full `make cluster-up && make argocd-deploy && make setup` flow

## Phase 8: Documentation
- [x] Write docs/local-k8s/plan.md
- [x] Write docs/local-k8s/todo.md
- [x] Write docs/local-k8s/docs.md
- [ ] Update docs with lessons learned from testing
