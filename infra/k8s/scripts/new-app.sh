#!/bin/bash
#
# Script to create new Kubernetes applications
#
# Usage:
#   ./new-app.sh <app-name>                                    # Create local Helm chart
#   ./new-app.sh --remote <name> <repo-name> <repo-url> <ver>  # Add remote Helm chart
#
# Examples:
#   ./new-app.sh my-api
#   ./new-app.sh --remote redis bitnami https://charts.bitnami.com/bitnami 17.0.0
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")"
APPS_DIR="$K8S_DIR/apps"
TEMPLATE_DIR="$APPS_DIR/example-app"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}!${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] <app-name>

Create a new Kubernetes application from template.

Options:
    --remote    Add a remote Helm chart reference instead of creating local chart
    --help      Show this help message

Examples:
    # Create a new local Helm chart from template
    $(basename "$0") my-api

    # Add a remote Helm chart (e.g., from Bitnami)
    $(basename "$0") --remote redis bitnami https://charts.bitnami.com/bitnami 17.0.0

    # Add Prometheus stack
    $(basename "$0") --remote prometheus-stack prometheus-community https://prometheus-community.github.io/helm-charts 45.0.0
EOF
    exit 1
}

create_local_app() {
    local app_name="$1"
    local app_dir="$APPS_DIR/$app_name"

    if [ -d "$app_dir" ]; then
        print_error "Directory already exists: $app_dir"
        exit 1
    fi

    if [ ! -d "$TEMPLATE_DIR" ]; then
        print_error "Template directory not found: $TEMPLATE_DIR"
        exit 1
    fi

    echo "Creating new application: $app_name"
    echo ""

    # Copy template
    cp -r "$TEMPLATE_DIR" "$app_dir"
    print_success "Copied template to $app_dir"

    # Update Chart.yaml
    sed -i.bak "s/example-app/$app_name/g" "$app_dir/Chart.yaml"
    rm -f "$app_dir/Chart.yaml.bak"
    print_success "Updated Chart.yaml"

    # Update values.yaml
    sed -i.bak "s/example-app/$app_name/g" "$app_dir/values.yaml"
    rm -f "$app_dir/values.yaml.bak"
    print_success "Updated values.yaml"

    # Update values-test.yaml
    sed -i.bak "s/example-app/$app_name/g" "$app_dir/values-test.yaml"
    rm -f "$app_dir/values-test.yaml.bak"
    print_success "Updated values-test.yaml"

    echo ""
    print_success "Application created at: $app_dir"
    echo ""
    echo "Next steps:"
    echo "  1. Edit $app_dir/values.yaml with your configuration"
    echo "  2. Update templates as needed"
    echo "  3. Add to app-of-apps/prod.yaml or test.yaml:"
    echo ""
    echo "     apps:"
    echo "       - name: $app_name"
    echo "         path: infra/k8s/apps/$app_name"
    echo "         namespace: default"
    echo ""
}

create_remote_app() {
    local app_name="$1"
    local repo_name="$2"
    local repo_url="$3"
    local chart_version="$4"
    local ref_file="$APPS_DIR/common/remote-helm-repos/$app_name.yaml"

    if [ -z "$app_name" ] || [ -z "$repo_name" ] || [ -z "$repo_url" ] || [ -z "$chart_version" ]; then
        print_error "Missing arguments for remote chart"
        echo ""
        echo "Usage: $(basename "$0") --remote <chart-name> <repo-name> <repo-url> <version>"
        exit 1
    fi

    echo "Adding remote Helm chart reference: $app_name"
    echo ""

    # Create reference file
    cat > "$ref_file" << EOF
# Remote Helm chart: $app_name
# Repository: $repo_name ($repo_url)
# Version: $chart_version
#
# Add the following to app-of-apps/prod.yaml or test.yaml:
#
# repos:
#   - name: $repo_name
#     url: $repo_url
#
# apps:
#   - name: $app_name
#     chart: $app_name
#     repoURL: $repo_url
#     targetRevision: "$chart_version"
#     namespace: default
#     values: |
#       # Add your values here
#       # Example:
#       # replicaCount: 2
EOF

    print_success "Created reference file: $ref_file"
    echo ""
    echo "Add the following to your app-of-apps values file (prod.yaml or test.yaml):"
    echo ""
    echo "repos:"
    echo "  - name: $repo_name"
    echo "    url: $repo_url"
    echo ""
    echo "apps:"
    echo "  - name: $app_name"
    echo "    chart: $app_name"
    echo "    repoURL: $repo_url"
    echo "    targetRevision: \"$chart_version\""
    echo "    namespace: default"
    echo "    values: |"
    echo "      # Add your values here"
    echo ""
}

# Parse arguments
if [ $# -eq 0 ]; then
    usage
fi

case "$1" in
    --help|-h)
        usage
        ;;
    --remote)
        shift
        create_remote_app "$@"
        ;;
    -*)
        print_error "Unknown option: $1"
        usage
        ;;
    *)
        if [ -z "$1" ]; then
            print_error "App name is required"
            usage
        fi
        create_local_app "$1"
        ;;
esac
