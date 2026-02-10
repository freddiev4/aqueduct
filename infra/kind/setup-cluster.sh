#!/bin/bash
set -euo pipefail

# Aqueduct Kind Cluster Setup
# Creates a Kind cluster with local container registry, ArgoCD, and backup storage
# Based on: https://kind.sigs.k8s.io/docs/user/local-registry/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTER_NAME="aqueduct"
REG_NAME="kind-registry"
REG_PORT="5001"
BACKUP_DIR="${HOME}/aqueduct-backups"

echo "=== Aqueduct Kind Cluster Setup ==="

# 1. Create local registry container (if not already running)
if [ "$(docker inspect -f '{{.State.Running}}' "${REG_NAME}" 2>/dev/null || true)" != 'true' ]; then
  echo "[1/7] Creating local registry on localhost:${REG_PORT}..."
  docker run -d --restart=always -p "127.0.0.1:${REG_PORT}:5000" --network bridge --name "${REG_NAME}" registry:2
else
  echo "[1/7] Local registry already running on localhost:${REG_PORT}"
fi

# 2. Create backup directory on host
echo "[2/7] Ensuring backup directory exists at ${BACKUP_DIR}..."
mkdir -p "${BACKUP_DIR}"

# 3. Create Kind cluster
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  echo "[3/7] Kind cluster '${CLUSTER_NAME}' already exists"
else
  echo "[3/7] Creating Kind cluster '${CLUSTER_NAME}'..."
  # Template the config with the resolved backup directory path
  RESOLVED_CONFIG=$(mktemp)
  sed "s|AQUEDUCT_BACKUPS_DIR|${BACKUP_DIR}|g" "${SCRIPT_DIR}/kind-config.yaml" > "${RESOLVED_CONFIG}"
  kind create cluster --name "${CLUSTER_NAME}" --config="${RESOLVED_CONFIG}"
  rm -f "${RESOLVED_CONFIG}"
fi

# 4. Configure containerd on each node to use the local registry
echo "[4/7] Configuring containerd registry on cluster nodes..."
REGISTRY_DIR="/etc/containerd/certs.d/localhost:${REG_PORT}"
for node in $(kind get nodes --name "${CLUSTER_NAME}"); do
  docker exec "${node}" mkdir -p "${REGISTRY_DIR}"
  cat <<EOF | docker exec -i "${node}" cp /dev/stdin "${REGISTRY_DIR}/hosts.toml"
[host."http://${REG_NAME}:5000"]
EOF
done

# 5. Connect registry to Kind network (if not already connected)
echo "[5/7] Connecting registry to Kind network..."
if [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${REG_NAME}" 2>/dev/null)" = 'null' ] || \
   [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${REG_NAME}" 2>/dev/null)" = '' ]; then
  docker network connect "kind" "${REG_NAME}" || true
else
  echo "  Registry already connected to Kind network"
fi

# 6. Document the local registry via ConfigMap
echo "[6/7] Creating local-registry-hosting ConfigMap..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REG_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

# 7. Install ArgoCD
echo "[7/7] Installing ArgoCD..."
kubectl create namespace argocd 2>/dev/null || true
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
echo "  Waiting for ArgoCD to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Cluster:  ${CLUSTER_NAME}"
echo "Registry: localhost:${REG_PORT}"
echo "Backups:  ${BACKUP_DIR} (host) -> /data/backups (node)"
echo ""
echo "Next steps:"
echo "  1. Deploy app-of-apps:  make argocd-deploy"
echo "  2. Port-forward Prefect: make port-forward-prefect"
echo "  3. Build & push image:   make push"
echo "  4. Full setup:           make setup"
echo ""
echo "ArgoCD UI:"
echo "  kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo "  Password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
