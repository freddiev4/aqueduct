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

# Detect Mac model year (returns year or "unknown")
detect_mac_year() {
    if [ "$(uname -s)" != "Darwin" ]; then
        echo "unknown"
        return
    fi

    # Try to get model year from system_profiler
    local model_info=$(system_profiler SPHardwareDataType 2>/dev/null | grep "Model Name\|Model Identifier")

    # Extract year from Model Identifier (e.g., "MacBookPro13,3" where 13 could indicate year)
    # Or look for year in Model Name (e.g., "Mac mini (Late 2014)")
    local year=$(echo "$model_info" | grep -oE '(Early|Late|Mid)?[[:space:]]?20[0-9]{2}' | grep -oE '20[0-9]{2}' | head -n1)

    if [ -n "$year" ]; then
        echo "$year"
    else
        # Fallback: try to estimate from Model Identifier
        # This is less reliable but can work for some models
        echo "unknown"
    fi
}

# Install VirtualBox (for older Macs that need it for Docker)
install_virtualbox() {
    local arch=$1
    local version="7.2.4"
    local build="170995"

    info "Installing VirtualBox ${version} for macOS..."

    # Check if VirtualBox is already installed
    if [ -d "/Applications/VirtualBox.app" ]; then
        warn "VirtualBox is already installed"
        read -p "Do you want to reinstall? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Skipping VirtualBox installation"
            return 0
        fi
    fi

    # Determine download URL based on architecture
    local vbox_url
    if [ "$arch" = "arm64" ]; then
        vbox_url="https://download.virtualbox.org/virtualbox/${version}/VirtualBox-${version}-${build}-macOSArm64.dmg"
        info "Downloading VirtualBox for Apple Silicon..."
    else
        vbox_url="https://download.virtualbox.org/virtualbox/${version}/VirtualBox-${version}-${build}-OSX.dmg"
        info "Downloading VirtualBox for Intel..."
    fi

    # Download VirtualBox DMG
    if ! curl -L -o /tmp/VirtualBox.dmg "$vbox_url"; then
        error "Failed to download VirtualBox"
        return 1
    fi

    # Mount the DMG
    info "Mounting VirtualBox.dmg..."
    if ! sudo hdiutil attach /tmp/VirtualBox.dmg; then
        error "Failed to mount VirtualBox.dmg"
        rm -f /tmp/VirtualBox.dmg
        return 1
    fi

    # Install VirtualBox (the DMG contains a .pkg file)
    info "Installing VirtualBox (this may take a moment)..."
    local vbox_pkg=$(find /Volumes/VirtualBox -name "*.pkg" | head -n1)
    if [ -n "$vbox_pkg" ]; then
        if ! sudo installer -pkg "$vbox_pkg" -target /; then
            error "VirtualBox installation failed"
            sudo hdiutil detach /Volumes/VirtualBox 2>/dev/null
            rm -f /tmp/VirtualBox.dmg
            return 1
        fi
    else
        error "Could not find VirtualBox installer package"
        sudo hdiutil detach /Volumes/VirtualBox 2>/dev/null
        rm -f /tmp/VirtualBox.dmg
        return 1
    fi

    # Unmount and clean up
    info "Cleaning up..."
    sudo hdiutil detach /Volumes/VirtualBox
    rm -f /tmp/VirtualBox.dmg

    info "✓ VirtualBox installed successfully"
    warn "You may need to approve VirtualBox kernel extensions in System Preferences > Security & Privacy"
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

# Install Docker
install_docker() {
    local os=$1
    local arch=$2

    info "Installing Docker for ${os}/${arch}..."

    # Check if docker is already installed
    if command -v docker &> /dev/null; then
        local current_version=$(docker --version 2>/dev/null || echo "unknown")
        warn "Docker is already installed (${current_version})"
        read -p "Do you want to reinstall? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Skipping Docker installation"
            return 0
        fi
    fi

    if [ "$os" = "darwin" ]; then
        # macOS - Check if we need VirtualBox for older Macs
        local mac_year=$(detect_mac_year)
        info "Detected Mac year: ${mac_year}"

        # For Macs pre-2016, Docker Desktop may not work well - install VirtualBox
        if [ "$mac_year" != "unknown" ] && [ "$mac_year" -lt 2016 ]; then
            warn "Detected Mac from ${mac_year} (pre-2016)"
            warn "Modern Docker Desktop requires macOS 11+ which may not be available on older Macs"
            warn "Installing VirtualBox first (required for Docker Toolbox on older systems)"
            echo
            install_virtualbox "$arch" || warn "VirtualBox installation failed"
            echo
            warn "Note: You may need to use Docker Toolbox instead of Docker Desktop on this Mac"
            warn "Docker Desktop installation will continue but may not work on older macOS versions"
            echo
        fi

        # macOS - Install Docker Desktop
        info "Installing Docker Desktop for macOS..."

        # Determine download URL based on architecture
        local docker_url
        if [ "$arch" = "arm64" ]; then
            docker_url="https://desktop.docker.com/mac/main/arm64/Docker.dmg"
            info "Downloading Docker Desktop for Apple Silicon..."
        else
            docker_url="https://desktop.docker.com/mac/main/amd64/Docker.dmg"
            info "Downloading Docker Desktop for Intel..."
        fi

        # Download Docker.dmg
        if ! curl -L -o /tmp/Docker.dmg "$docker_url"; then
            error "Failed to download Docker Desktop"
            return 1
        fi

        # Mount the DMG
        info "Mounting Docker.dmg..."
        if ! sudo hdiutil attach /tmp/Docker.dmg; then
            error "Failed to mount Docker.dmg"
            rm -f /tmp/Docker.dmg
            return 1
        fi

        # Run the installer
        info "Running Docker installer (this may take a moment)..."
        if ! sudo /Volumes/Docker/Docker.app/Contents/MacOS/install --accept-license; then
            error "Docker installation failed"
            sudo hdiutil detach /Volumes/Docker 2>/dev/null
            rm -f /tmp/Docker.dmg
            return 1
        fi

        # Unmount and clean up
        info "Cleaning up..."
        sudo hdiutil detach /Volumes/Docker
        rm -f /tmp/Docker.dmg

        info "✓ Docker Desktop installed successfully to /Applications/Docker.app"
        warn "You may need to start Docker Desktop manually from Applications"

    elif [ "$os" = "linux" ]; then
        # Linux - Install Docker Engine using convenience script
        info "Installing Docker Engine for Linux using convenience script..."

        # Download the convenience script
        if ! curl -fsSL https://get.docker.com -o /tmp/get-docker.sh; then
            error "Failed to download Docker installation script"
            return 1
        fi

        # Run the installation script
        info "Running Docker installation script (requires sudo)..."
        if ! sudo sh /tmp/get-docker.sh; then
            error "Docker installation failed"
            rm -f /tmp/get-docker.sh
            return 1
        fi

        # Clean up
        rm -f /tmp/get-docker.sh

        # Add current user to docker group if not root
        if [ "$USER" != "root" ] && [ -n "$USER" ]; then
            info "Adding user $USER to docker group..."
            sudo usermod -aG docker "$USER"
            warn "You'll need to log out and back in for docker group membership to take effect"
        fi

        # Verify installation
        if command -v docker &> /dev/null; then
            info "✓ Docker Engine installed successfully: $(docker --version)"
        else
            error "Docker installation completed but docker command not found"
            return 1
        fi
    else
        error "Docker installation not supported for OS: ${os}"
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
    local virtualbox_version="not installed"
    local docker_version="not installed"
    local kind_version="not installed"
    local argocd_version="not installed"
    local claude_version="not installed"

    # Check for VirtualBox (macOS only)
    if [ "$os" = "darwin" ] && [ -d "/Applications/VirtualBox.app" ]; then
        virtualbox_version=$(VBoxManage --version 2>/dev/null || echo "installed (version unknown)")
    fi

    if command -v docker &> /dev/null; then
        docker_version=$(docker --version 2>/dev/null | sed 's/Docker version //' | cut -d',' -f1 || echo "installed (version unknown)")
    fi

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
    local mac_year="n/a"
    if [ "$os" = "darwin" ]; then
        mac_year=$(detect_mac_year)
    fi

    # Create JSON report
    cat > "$report_file" <<EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "hostname": "${hostname}",
  "system": {
    "os": "${full_os}",
    "kernel": "${kernel}",
    "architecture": "${arch}",
    "detected_os": "${os}",
    "mac_year": "${mac_year}"
  },
  "tools": {
    "virtualbox": "${virtualbox_version}",
    "docker": "${docker_version}",
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

    install_docker "$OS" "$ARCH" || warn "Docker installation failed, continuing..."
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
    if [ -d "/Applications/VirtualBox.app" ]; then
        echo "  - virtualbox: $(VBoxManage --version 2>/dev/null || echo 'installed')"
    fi
    if command -v docker &> /dev/null; then
        echo "  - docker: $(docker --version 2>/dev/null)"
    fi
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
