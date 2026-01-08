#!/usr/bin/env bash

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print colored messages
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "darwin";;
        *)          echo "unknown";;
    esac
}

# Detect architecture
detect_arch() {
    case "$(uname -m)" in
        x86_64|amd64)   echo "amd64";;
        arm64|aarch64)  echo "arm64";;
        *)              echo "unknown";;
    esac
}

# Install kind
install_kind() {
    local os=$1
    local arch=$2
    local version="v0.31.0"
    local kind_url="https://kind.sigs.k8s.io/dl/${version}/kind-${os}-${arch}"

    info "Installing kind ${version} for ${os}/${arch}..."

    # Check if kind is already installed
    if command -v kind &> /dev/null; then
        local current_version=$(kind version 2>/dev/null | grep -oP 'kind v\K[0-9.]+' || echo "unknown")
        warn "kind is already installed (version: ${current_version})"
        read -p "Do you want to reinstall? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Skipping kind installation"
            return 0
        fi
    fi

    # Download kind
    info "Downloading from ${kind_url}..."
    if ! curl -Lo /tmp/kind "${kind_url}"; then
        error "Failed to download kind"
        return 1
    fi

    # Make executable
    chmod +x /tmp/kind

    # Move to bin directory
    if [ -w /usr/local/bin ]; then
        mv /tmp/kind /usr/local/bin/kind
        info "Installed kind to /usr/local/bin/kind"
    else
        warn "/usr/local/bin is not writable, need sudo permissions"
        sudo mv /tmp/kind /usr/local/bin/kind
        info "Installed kind to /usr/local/bin/kind (with sudo)"
    fi

    # Verify installation
    if command -v kind &> /dev/null; then
        info "✓ kind installed successfully: $(kind version)"
    else
        error "kind installation failed"
        return 1
    fi
}

# Install Claude Code
install_claude_code() {
    info "Installing Claude Code CLI..."

    # Check if claude is already installed
    if command -v claude &> /dev/null; then
        local current_version=$(claude --version 2>/dev/null || echo "unknown")
        warn "Claude Code is already installed (version: ${current_version})"
        read -p "Do you want to reinstall? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Skipping Claude Code installation"
            return 0
        fi
    fi

    # Download and run the official installer
    info "Downloading and running official Claude Code installer..."
    if ! curl -fsSL https://claude.ai/install.sh | bash; then
        error "Failed to install Claude Code"
        return 1
    fi

    # Verify installation
    if command -v claude &> /dev/null; then
        info "✓ Claude Code installed successfully"
    else
        warn "Claude Code may have been installed but is not in current PATH"
        warn "You may need to restart your shell or source your shell config"
    fi
}

# Install ArgoCD CLI
install_argocd() {
    local os=$1
    local arch=$2

    info "Installing ArgoCD CLI for ${os}/${arch}..."

    # Check if argocd is already installed
    if command -v argocd &> /dev/null; then
        local current_version=$(argocd version --client --short 2>/dev/null | head -n1 || echo "unknown")
        warn "ArgoCD CLI is already installed (version: ${current_version})"
        read -p "Do you want to reinstall? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Skipping ArgoCD CLI installation"
            return 0
        fi
    fi

    # Get latest version from GitHub API
    info "Fetching latest ArgoCD version..."
    local version
    version=$(curl -s https://api.github.com/repos/argoproj/argo-cd/releases/latest | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')

    if [ -z "$version" ]; then
        error "Failed to fetch latest ArgoCD version"
        return 1
    fi

    info "Latest version: ${version}"

    # Construct download URL
    local binary_name="argocd-${os}-${arch}"
    local argocd_url="https://github.com/argoproj/argo-cd/releases/download/${version}/${binary_name}"

    # Download ArgoCD CLI
    info "Downloading from ${argocd_url}..."
    if ! curl -sSL -o /tmp/argocd "${argocd_url}"; then
        error "Failed to download ArgoCD CLI"
        return 1
    fi

    # Install with proper permissions
    if [ -w /usr/local/bin ]; then
        install -m 555 /tmp/argocd /usr/local/bin/argocd
        info "Installed argocd to /usr/local/bin/argocd"
    else
        warn "/usr/local/bin is not writable, need sudo permissions"
        sudo install -m 555 /tmp/argocd /usr/local/bin/argocd
        info "Installed argocd to /usr/local/bin/argocd (with sudo)"
    fi

    # Clean up
    rm -f /tmp/argocd

    # Verify installation
    if command -v argocd &> /dev/null; then
        info "✓ ArgoCD CLI installed successfully: $(argocd version --client --short 2>/dev/null | head -n1)"
    else
        error "ArgoCD CLI installation failed"
        return 1
    fi
}

# Write version report to JSON file
write_version_report() {
    local os=$1
    local arch=$2

    # Generate UTC timestamp for filename (ISO 8601 format, filename-safe)
    local timestamp=$(date -u +"%Y-%m-%dT%H-%M-%SZ")
    local report_file="server-initialization-${timestamp}.json"

    info "Writing version report to ${report_file}..."

    # Collect version information
    local kind_version="not installed"
    local argocd_version="not installed"
    local claude_version="not installed"

    if command -v kind &> /dev/null; then
        kind_version=$(kind version 2>/dev/null | grep -oP 'kind v\K[0-9.]+' || echo "installed (version unknown)")
    fi

    if command -v argocd &> /dev/null; then
        argocd_version=$(argocd version --client --short 2>/dev/null | head -n1 | sed 's/argocd: //' || echo "installed (version unknown)")
    fi

    if command -v claude &> /dev/null; then
        claude_version=$(claude --version 2>/dev/null | head -n1 || echo "installed (version unknown)")
    fi

    # Get full system info
    local hostname=$(hostname)
    local kernel=$(uname -r)
    local full_os=$(uname -s)

    # Create JSON report
    cat > "$report_file" <<EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "hostname": "${hostname}",
  "system": {
    "os": "${full_os}",
    "kernel": "${kernel}",
    "architecture": "${arch}",
    "detected_os": "${os}"
  },
  "tools": {
    "kind": "${kind_version}",
    "argocd": "${argocd_version}",
    "claude": "${claude_version}"
  }
}
EOF

    if [ -f "$report_file" ]; then
        info "✓ Version report written to ${report_file}"
    else
        error "Failed to write version report"
        return 1
    fi
}

# Main installation function
main() {
    info "Server Bootstrap Script"
    info "======================="
    echo

    # Detect system
    OS=$(detect_os)
    ARCH=$(detect_arch)

    if [ "$OS" = "unknown" ] || [ "$ARCH" = "unknown" ]; then
        error "Unsupported OS or architecture: $(uname -s)/$(uname -m)"
        exit 1
    fi

    info "Detected system: ${OS}/${ARCH}"
    echo

    # Check for required tools
    if ! command -v curl &> /dev/null; then
        error "curl is required but not installed"
        exit 1
    fi

    # Install tools
    info "Installing tools..."
    echo

    install_kind "$OS" "$ARCH" || warn "kind installation failed, continuing..."
    echo

    install_argocd "$OS" "$ARCH" || warn "ArgoCD CLI installation failed, continuing..."
    echo

    install_claude_code || warn "Claude Code installation failed, continuing..."
    echo

    info "======================="
    info "Bootstrap complete!"
    echo
    info "Installed tools:"
    if command -v kind &> /dev/null; then
        echo "  - kind: $(kind version)"
    fi
    if command -v argocd &> /dev/null; then
        echo "  - argocd: $(argocd version --client --short 2>/dev/null | head -n1)"
    fi
    if command -v claude &> /dev/null; then
        echo "  - claude: installed (run 'claude --version' to verify)"
    fi
    echo

    # Write version report
    write_version_report "$OS" "$ARCH"
    echo

    info "You may need to restart your shell for changes to take effect"
}

# Run main function
main
