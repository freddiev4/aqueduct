# Kubernetes & ArgoCD Infrastructure

GitOps-based Kubernetes deployment using ArgoCD and Helm charts. Works with both cloud-managed Kubernetes (EKS, GKE, AKS) and local clusters (Kind, Minikube).

## Directory Structure

```
k8s/
├── apps/
│   ├── app-of-apps/           # Parent application managing all others
│   │   ├── Chart.yaml
│   │   ├── templates/
│   │   │   └── helm-apps.yaml # Template creating ArgoCD Applications
│   │   ├── prod.yaml          # Production environment config
│   │   └── test.yaml          # Test environment config
│   │
│   ├── common/                # Shared configurations
│   │   ├── manifests/
│   │   │   ├── misc/          # Storage classes, certificates, etc.
│   │   │   └── secrets/       # Sealed secrets (encrypted)
│   │   ├── remote-helm-repos/ # External Helm chart references
│   │   ├── prod-manifests/    # Production-specific configs
│   │   └── test-manifests/    # Test-specific configs
│   │
│   └── example-app/           # Template for new applications
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-test.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── ingress.yaml
│           ├── serviceaccount.yaml
│           ├── configmap.yaml
│           ├── secrets.yaml
│           └── servicemonitor.yaml
├── scripts/
│   └── new-app.sh             # Script to scaffold new apps
└── README.md
```

---

## Quick Start

### Local Development with Kind

```bash
# Create a Kind cluster with ingress support
cat <<EOF | kind create cluster --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
EOF

# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ArgoCD to be ready
kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd
```

### Deploy the App-of-Apps

For production:
```bash
helm install app-of-apps ./apps/app-of-apps -f ./apps/app-of-apps/prod.yaml -n argocd
```

For test/local:
```bash
helm install app-of-apps ./apps/app-of-apps -f ./apps/app-of-apps/test.yaml -n argocd
```

---

## Administration Guide

### ArgoCD CLI Setup

```bash
# Install ArgoCD CLI (macOS)
brew install argocd

# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d && echo

# Port forward to access ArgoCD
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Login via CLI
argocd login localhost:8080 --username admin --password <password> --insecure
```

### Common ArgoCD Commands

```bash
# List all applications
argocd app list

# Get application status
argocd app get <app-name>

# Sync an application (deploy changes)
argocd app sync <app-name>

# Force sync (ignore differences)
argocd app sync <app-name> --force

# View application logs
argocd app logs <app-name>

# View application history
argocd app history <app-name>

# Rollback to previous version
argocd app rollback <app-name> <history-id>

# Delete an application
argocd app delete <app-name>

# Refresh application (re-read from git)
argocd app get <app-name> --refresh
```

### Common kubectl Commands

```bash
# View all resources in a namespace
kubectl get all -n <namespace>

# View pods and their status
kubectl get pods -n <namespace>
kubectl get pods -n <namespace> -o wide  # with node info

# View pod logs
kubectl logs <pod-name> -n <namespace>
kubectl logs <pod-name> -n <namespace> -f  # follow logs
kubectl logs <pod-name> -n <namespace> --previous  # previous container

# Describe a resource (troubleshooting)
kubectl describe pod <pod-name> -n <namespace>
kubectl describe deployment <deployment-name> -n <namespace>

# Execute command in a pod
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh

# Port forward to a service
kubectl port-forward svc/<service-name> -n <namespace> <local-port>:<service-port>

# View events (useful for debugging)
kubectl get events -n <namespace> --sort-by='.lastTimestamp'

# View resource usage
kubectl top pods -n <namespace>
kubectl top nodes
```

### Debugging Deployments

```bash
# Check why pods aren't starting
kubectl describe pod <pod-name> -n <namespace>

# Check deployment rollout status
kubectl rollout status deployment/<deployment-name> -n <namespace>

# View deployment history
kubectl rollout history deployment/<deployment-name> -n <namespace>

# Rollback a deployment
kubectl rollout undo deployment/<deployment-name> -n <namespace>

# Scale a deployment
kubectl scale deployment/<deployment-name> --replicas=3 -n <namespace>
```

---

## How the Templates Work

### App-of-Apps Pattern

The `app-of-apps` is a Helm chart that generates ArgoCD Application resources. When deployed, it creates child Applications that ArgoCD then manages.

**Flow:**
1. `helm-apps.yaml` template iterates over `.Values.apps` in prod.yaml/test.yaml
2. For each app, it creates an ArgoCD `Application` resource
3. ArgoCD watches these Applications and syncs them from their source (git or helm repo)

**helm-apps.yaml key sections:**

```yaml
# For remote Helm charts (e.g., prometheus, nginx):
{{- if hasKey $app "chart" }}
chart: {{ $app.chart }}
repoURL: {{ $app.repoURL }}
targetRevision: {{ $app.targetRevision }}

# For git-based Helm charts (your own apps):
{{- else }}
path: {{ $app.path }}
repoURL: {{ $app.repoURL | default "git@github.com:your-org/repo.git" }}
```

### Application Helm Charts

Each app (like `example-app`) is a standard Helm chart:

- **Chart.yaml**: Metadata (name, version)
- **values.yaml**: Default configuration values
- **values-test.yaml**: Test environment overrides
- **templates/**: Kubernetes manifests with Helm templating

**Template syntax:**
```yaml
# Reference a value
{{ .Values.name }}

# Conditional rendering
{{- if .Values.ingress.enabled }}
...
{{- end }}

# Iterate over a map
{{- range $key, $value := .Values.env }}
- name: {{ $key }}
  value: {{ $value | quote }}
{{- end }}

# Include with indentation
{{- toYaml .Values.resources | nindent 8 }}
```

### Adding to App-of-Apps

**For a local Helm chart:**
```yaml
apps:
  - name: my-service
    path: infra/k8s/apps/my-service    # Path in git repo
    namespace: default
    # valueFile: values-test.yaml      # Optional: override values file
```

**For a remote Helm chart:**
```yaml
repos:
  - name: bitnami
    url: https://charts.bitnami.com/bitnami

apps:
  - name: redis
    chart: redis                        # Chart name
    repoURL: https://charts.bitnami.com/bitnami
    targetRevision: "17.0.0"           # Chart version
    namespace: default
    values: |                          # Inline values
      replica:
        replicaCount: 3
```

---

## Adding a New Application

### Option 1: Use the Script

```bash
# Create a new local app from template
./scripts/new-app.sh my-new-service

# Add a remote helm chart reference
./scripts/new-app.sh --remote redis bitnami https://charts.bitnami.com/bitnami 17.0.0
```

### Option 2: Manual

1. Copy `apps/example-app` to `apps/your-app-name`
2. Update `Chart.yaml` with your app name
3. Configure `values.yaml` with your app settings
4. Add the app to `app-of-apps/prod.yaml` and/or `test.yaml`

---

## Managing Secrets

Use [kubeseal](https://github.com/bitnami-labs/sealed-secrets) for encrypting secrets:

```bash
# Install sealed-secrets controller
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets -n kube-system

# Seal a secret
kubectl create secret generic my-secret --dry-run=client -o yaml \
  --from-literal=API_KEY=secret-value | kubeseal --format yaml > sealed-secret.yaml
```

---

## Environment Configuration

| File | Purpose |
|------|---------|
| `prod.yaml` | Production: full monitoring, HA, production secrets |
| `test.yaml` | Test/staging: reduced resources, test configs |
| `values.yaml` | App defaults |
| `values-test.yaml` | Per-app test overrides |

---

## Troubleshooting

### ArgoCD Application Stuck

```bash
# Check sync status
argocd app get <app-name>

# View sync errors
kubectl get application <app-name> -n argocd -o yaml

# Force refresh
argocd app get <app-name> --refresh --hard-refresh
```

### Pods Not Starting

```bash
# Check pod events
kubectl describe pod <pod-name> -n <namespace>

# Common issues:
# - ImagePullBackOff: Wrong image or no credentials
# - CrashLoopBackOff: App crashing, check logs
# - Pending: No nodes available or resource constraints
```

### Helm Template Errors

```bash
# Test template rendering locally
helm template ./apps/my-app -f ./apps/my-app/values.yaml

# With debug output
helm template ./apps/my-app --debug
```
