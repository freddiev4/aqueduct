.PHONY: cluster-up cluster-down build push deploy port-forward-prefect port-forward-argocd \
       register-blocks create-work-pool set-image setup argocd-deploy argocd-password \
       logs-worker logs-server test-registry status

REGISTRY := localhost:5001
IMAGE := $(REGISTRY)/aqueduct-workflows
GIT_HASH := $(shell git rev-parse --short HEAD)
TIMESTAMP := $(shell date +%Y%m%d%H%M%S)
TAG := $(GIT_HASH)-$(TIMESTAMP)
PREFECT_API := http://localhost:4200/api

# === Cluster Lifecycle ===

cluster-up:
	./infra/kind/setup-cluster.sh

cluster-down:
	./infra/kind/teardown-cluster.sh

# === Image Build & Push ===

build:
	docker build -t $(IMAGE):$(TAG) -t $(IMAGE):latest .

push: build
	docker push $(IMAGE):$(TAG)
	docker push $(IMAGE):latest
	@echo "Pushed $(IMAGE):$(TAG)"

test-registry:
	@echo "Checking registry catalog..."
	@curl -s localhost:5001/v2/_catalog | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin),indent=2))"

# === ArgoCD ===

argocd-deploy:
	helm install app-of-apps ./infra/k8s/apps/app-of-apps -f ./infra/k8s/apps/app-of-apps/test.yaml -n argocd

argocd-password:
	@kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d && echo

# === Port Forwards ===

port-forward-prefect:
	kubectl --namespace prefect port-forward svc/prefect-server 4200:4200

port-forward-argocd:
	kubectl port-forward svc/argocd-server -n argocd 8080:443

# === Prefect Setup ===

create-work-pool:
	PREFECT_API_URL=$(PREFECT_API) prefect work-pool create kubernetes-pool --type kubernetes --set-as-default

register-blocks:
	PREFECT_API_URL=$(PREFECT_API) python blocks/github_block.py
	PREFECT_API_URL=$(PREFECT_API) python scripts/setup_reddit_block.py
	PREFECT_API_URL=$(PREFECT_API) python scripts/setup_amazon_block.py
	PREFECT_API_URL=$(PREFECT_API) python scripts/setup_google_drive_block.py

set-image:
	@echo "Setting work pool default image to $(IMAGE):$(TAG)..."
	@python3 -c "\
	import json, urllib.request; \
	pool = json.load(urllib.request.urlopen('$(PREFECT_API)/work_pools/kubernetes-pool')); \
	t = pool['base_job_template']; \
	t['variables']['properties']['image']['default'] = '$(IMAGE):$(TAG)'; \
	req = urllib.request.Request('$(PREFECT_API)/work_pools/kubernetes-pool', \
	    data=json.dumps({'base_job_template': t}).encode(), \
	    headers={'Content-Type': 'application/json'}, method='PATCH'); \
	urllib.request.urlopen(req); \
	print('Done: $(IMAGE):$(TAG)')"

deploy:
	PREFECT_API_URL=$(PREFECT_API) prefect deploy --all

# === Full Post-Cluster Setup ===

setup: push set-image register-blocks deploy
	@echo ""
	@echo "=== Aqueduct fully deployed to Kind cluster ==="
	@echo "Prefect UI: http://localhost:4200 (run 'make port-forward-prefect' first)"

# === Logs ===

logs-worker:
	kubectl logs -n prefect -l app.kubernetes.io/name=prefect-worker -f

logs-server:
	kubectl logs -n prefect -l app.kubernetes.io/name=prefect-server -f

# === Status ===

status:
	@echo "=== Cluster ==="
	@kubectl cluster-info 2>/dev/null || echo "Cluster not running"
	@echo ""
	@echo "=== Registry ==="
	@docker inspect -f '{{.State.Status}}' kind-registry 2>/dev/null || echo "Registry not running"
	@echo ""
	@echo "=== Prefect Pods ==="
	@kubectl get pods -n prefect 2>/dev/null || echo "No pods in prefect namespace"
	@echo ""
	@echo "=== ArgoCD Apps ==="
	@kubectl get applications -n argocd 2>/dev/null || echo "No ArgoCD apps"
