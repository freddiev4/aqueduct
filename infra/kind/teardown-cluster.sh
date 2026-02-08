#!/bin/bash
set -euo pipefail

# Aqueduct Kind Cluster Teardown
CLUSTER_NAME="aqueduct"
REG_NAME="kind-registry"
BACKUP_DIR="${HOME}/aqueduct-backups"

echo "=== Aqueduct Kind Cluster Teardown ==="

# Delete Kind cluster
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  echo "Deleting Kind cluster '${CLUSTER_NAME}'..."
  kind delete cluster --name "${CLUSTER_NAME}"
else
  echo "Kind cluster '${CLUSTER_NAME}' does not exist"
fi

# Remove registry container
if [ "$(docker inspect -f '{{.State.Running}}' "${REG_NAME}" 2>/dev/null || true)" = 'true' ]; then
  echo "Removing registry container '${REG_NAME}'..."
  docker rm -f "${REG_NAME}"
else
  echo "Registry container '${REG_NAME}' not running"
fi

# Ask about backup data
if [ -d "${BACKUP_DIR}" ]; then
  echo ""
  read -p "Delete backup data at ${BACKUP_DIR}? [y/N] " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "${BACKUP_DIR}"
    echo "Backup data deleted"
  else
    echo "Backup data preserved at ${BACKUP_DIR}"
  fi
fi

echo ""
echo "=== Teardown Complete ==="
