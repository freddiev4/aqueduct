# Local K8s - Implementation TODO

## Phase 1: Kind + Registry
- [x] Create `infra/kind/kind-config.yaml`
- [x] Create `infra/kind/setup-cluster.sh`
- [x] Create `infra/kind/teardown-cluster.sh`
- [ ] Test cluster creation with registry

## Phase 2: Docker Image
- [x] Create `Dockerfile`
- [ ] Test building image
- [ ] Test pushing to localhost:5001
- [ ] Verify workflows can import blocks from PYTHONPATH

## Phase 3: Prefect Server via ArgoCD
- [x] Create `infra/k8s/apps/common/manifests/misc/prefect-namespace.yaml`
- [x] Update `infra/k8s/apps/app-of-apps/test.yaml`
- [ ] Test ArgoCD deploys Prefect server
- [ ] Verify UI accessible via port-forward

## Phase 4: Prefect Worker
- [ ] Verify worker Helm chart deploys correctly
- [ ] Verify worker connects to server
- [ ] Verify RBAC allows Job creation

## Phase 5: Workflow Deployments
- [x] Create `prefect.yaml`
- [ ] Create work pool via CLI
- [ ] Configure base job template with hostPath mount
- [ ] Deploy workflows via `prefect deploy`
- [ ] Test running a workflow (e.g., example.py)

## Phase 6: Credentials
- [ ] Register blocks via port-forward
- [ ] Test a real workflow (GitHub) end-to-end

## Phase 7: Automation
- [x] Create `Makefile`
- [ ] Test full `make cluster-up && make argocd-deploy && make setup` flow

## Phase 8: Documentation
- [x] Write docs/local-k8s/plan.md
- [x] Write docs/local-k8s/todo.md
- [x] Write docs/local-k8s/docs.md
