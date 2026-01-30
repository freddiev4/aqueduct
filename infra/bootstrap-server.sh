#!/usr/bin/env bash
#
# Server Bootstrap Script
# =======================
# Comprehensive development environment setup for macOS and Linux
#
# Features:
#   - Cross-platform support (macOS and Linux)
#   - Docker installation with choice of Colima (recommended) or Docker Desktop on macOS
#   - Kubernetes tooling (kubectl, kind)
#   - ArgoCD CLI for GitOps workflows
#   - GitHub CLI (gh) for GitHub operations
#   - Atuin shell history tool for enhanced command history
#   - Claude Code CLI for AI-assisted development
#   - Claude agents, plugins, and skills from freddiev4/agents repo
#   - uv Python package manager for fast dependency management
#   - Bun JavaScript runtime for fast JS/TS execution
#   - Automatic Homebrew installation on macOS
#   - VirtualBox support for older Macs
#   - JSON version report generation
#
# Usage:
#   ./bootstrap-server.sh
#
# The script will:
#   1. Detect your OS and architecture
#   2. Install Homebrew (macOS only)
#   3. Install Docker (Colima/Docker Desktop on macOS, Docker Engine on Linux)
#   4. Install kind (Kubernetes in Docker - requires Docker)
#   5. Install kubectl (if not already installed by kind)
#   6. Install ArgoCD CLI for GitOps workflows
#   7. Install GitHub CLI for GitHub operations
#   8. Install Atuin shell history tool
#   9. Install Claude Code CLI for AI-assisted development
#  10. Install Claude agents, plugins, and skills from agents repo
#  11. Install uv Python package manager
#  12. Install Bun JavaScript runtime
#  13. Generate a timestamped JSON report of installed versions
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# Check if command exists
command_exists() {
    command -v "$1" &> /dev/null
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

# Install Homebrew (macOS only)
install_homebrew() {
    if [ "$(uname -s)" != "Darwin" ]; then
        return 0
    fi

    info "Checking Homebrew..."
    if ! command_exists brew; then
        info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Add Homebrew to PATH for current session
        if [[ -f "/opt/homebrew/bin/brew" ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [[ -f "/usr/local/bin/brew" ]]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
        info "✓ Homebrew installed"
    else
        info "✓ Homebrew found: $(brew --version | head -n 1)"
    fi
}

# Install kubectl
install_kubectl() {
    local os=$1
    local arch=$2

    info "Checking kubectl..."
    if command_exists kubectl; then
        local current_version=$(kubectl version --client --short 2>/dev/null | head -n 1 || echo "installed")
        info "✓ kubectl already installed: ${current_version}"

        # Check if it was installed by kind
        if command_exists kind; then
            info "  (kubectl may have been installed with kind)"
        fi
        return 0
    fi

    info "Installing kubectl..."
    if [ "$os" = "darwin" ]; then
        if command_exists brew; then
            brew install kubectl
        else
            error "Homebrew required for kubectl installation on macOS"
            return 1
        fi
    elif [ "$os" = "linux" ]; then
        # Install kubectl on Linux
        local kubectl_url="https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/${arch}/kubectl"
        curl -LO "$kubectl_url"
        chmod +x kubectl
        if [ -w /usr/local/bin ]; then
            mv kubectl /usr/local/bin/kubectl
        else
            sudo mv kubectl /usr/local/bin/kubectl
        fi
    fi

    if command_exists kubectl; then
        info "✓ kubectl installed successfully"
    else
        error "kubectl installation failed"
        return 1
    fi
}

# Install Colima (macOS Docker alternative)
install_colima() {
    info "Installing Colima..."

    if command_exists colima; then
        local current_version=$(colima version | grep 'colima version' | awk '{print $3}')
        info "✓ Colima found: version ${current_version}"

        # Check for updates
        if command_exists brew; then
            local latest_version=$(brew info colima | grep 'colima:' | awk '{print $3}')
            if [ "$current_version" != "$latest_version" ]; then
                warn "Update available: ${current_version} -> ${latest_version}"
                read -p "Would you like to upgrade? (y/N): " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    brew upgrade colima
                    info "✓ Colima upgraded"
                fi
            fi
        fi
        return 0
    fi

    # Install Colima via Homebrew
    if ! command_exists brew; then
        error "Homebrew is required to install Colima"
        return 1
    fi

    brew install colima
    info "✓ Colima installed"

    # Also ensure Docker CLI is installed
    if ! command_exists docker; then
        info "Installing Docker CLI..."
        brew install docker
        info "✓ Docker CLI installed"
    fi

    # Configure and start Colima
    local cpu=2
    local memory=4
    local disk=60

    info "Default Colima configuration: ${cpu} CPU, ${memory}GB RAM, ${disk}GB disk"
    read -p "Customize settings? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "CPU cores (default: ${cpu}): " cpu_input
        cpu=${cpu_input:-$cpu}

        read -p "Memory in GB (default: ${memory}): " mem_input
        memory=${mem_input:-$memory}

        read -p "Disk size in GB (default: ${disk}): " disk_input
        disk=${disk_input:-$disk}
    fi

    info "Starting Colima with ${cpu} CPU, ${memory}GB RAM, ${disk}GB disk..."
    colima start \
        --cpu "$cpu" \
        --memory "$memory" \
        --disk "$disk" \
        --arch x86_64 \
        --vm-type=qemu \
        --mount-type=sshfs \
        --dns=1.1.1.1 \
        --dns=8.8.8.8

    # Verify installation
    if docker ps &> /dev/null; then
        info "✓ Colima started successfully and Docker is accessible"
    else
        error "Colima started but Docker daemon is not accessible"
        return 1
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

# Install uv (Python package manager)
install_uv() {
    info "Installing uv (Python package manager)..."

    # Check if uv is already installed
    if command -v uv &> /dev/null; then
        local current_version=$(uv --version 2>/dev/null || echo "unknown")
        warn "uv is already installed (version: ${current_version})"
        read -p "Do you want to reinstall? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Skipping uv installation"
            return 0
        fi
    fi

    # Download and run the official installer
    info "Downloading and running official uv installer..."
    if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
        error "Failed to install uv"
        return 1
    fi

    # Verify installation
    if command -v uv &> /dev/null; then
        info "✓ uv installed successfully: $(uv --version 2>/dev/null)"
    else
        warn "uv may have been installed but is not in current PATH"
        warn "You may need to restart your shell or source your shell config"
    fi
}

# Install Bun (JavaScript runtime)
install_bun() {
    info "Installing Bun (JavaScript runtime)..."

    # Check if bun is already installed
    if command -v bun &> /dev/null; then
        local current_version=$(bun --version 2>/dev/null || echo "unknown")
        warn "Bun is already installed (version: ${current_version})"
        read -p "Do you want to reinstall? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Skipping Bun installation"
            return 0
        fi
    fi

    # Download and run the official installer
    info "Downloading and running official Bun installer..."
    if ! curl -fsSL https://bun.sh/install | bash; then
        error "Failed to install Bun"
        return 1
    fi

    # Verify installation
    if command -v bun &> /dev/null; then
        info "✓ Bun installed successfully: $(bun --version 2>/dev/null)"
    else
        warn "Bun may have been installed but is not in current PATH"
        warn "You may need to restart your shell or source your shell config"
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

# Install GitHub CLI
install_github_cli() {
    local os=$1
    local arch=$2

    info "Installing GitHub CLI (gh) for ${os}/${arch}..."

    # Check if gh is already installed
    if command_exists gh; then
        local current_version=$(gh --version 2>/dev/null | head -n1 || echo "unknown")
        warn "GitHub CLI is already installed (${current_version})"
        read -p "Do you want to reinstall? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Skipping GitHub CLI installation"
            return 0
        fi
    fi

    if [ "$os" = "darwin" ]; then
        # macOS - Install via Homebrew
        if ! command_exists brew; then
            error "Homebrew is required to install GitHub CLI on macOS"
            return 1
        fi
        info "Installing GitHub CLI via Homebrew..."
        brew install gh
    elif [ "$os" = "linux" ]; then
        # Linux - Check for package manager
        if command_exists apt-get; then
            # Debian/Ubuntu - Use official repository
            info "Installing GitHub CLI via apt (official repository)..."

            # Ensure wget is available
            if ! command_exists wget; then
                sudo apt update && sudo apt install wget -y
            fi

            # Set up the repository and install
            sudo mkdir -p -m 755 /etc/apt/keyrings
            local tmpfile=$(mktemp)
            wget -nv -O "$tmpfile" https://cli.github.com/packages/githubcli-archive-keyring.gpg
            cat "$tmpfile" | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
            sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
            rm -f "$tmpfile"

            sudo mkdir -p -m 755 /etc/apt/sources.list.d
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null

            sudo apt update
            sudo apt install gh -y
        elif command_exists dnf; then
            # Fedora/RHEL - Use official repository
            info "Installing GitHub CLI via dnf..."
            sudo dnf install -y 'dnf-command(config-manager)'
            sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
            sudo dnf install -y gh
        elif command_exists yum; then
            # Older RHEL/CentOS
            info "Installing GitHub CLI via yum..."
            sudo yum-config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
            sudo yum install -y gh
        else
            # Fallback - Download precompiled binary
            info "No supported package manager found, downloading precompiled binary..."

            # Get latest version from GitHub API
            local version=$(curl -s https://api.github.com/repos/cli/cli/releases/latest | grep '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')
            if [ -z "$version" ]; then
                error "Failed to fetch latest GitHub CLI version"
                return 1
            fi

            local gh_arch="$arch"
            if [ "$arch" = "amd64" ]; then
                gh_arch="amd64"
            elif [ "$arch" = "arm64" ]; then
                gh_arch="arm64"
            fi

            local gh_url="https://github.com/cli/cli/releases/download/v${version}/gh_${version}_linux_${gh_arch}.tar.gz"
            info "Downloading from ${gh_url}..."

            if ! curl -sL -o /tmp/gh.tar.gz "$gh_url"; then
                error "Failed to download GitHub CLI"
                return 1
            fi

            tar -xzf /tmp/gh.tar.gz -C /tmp
            if [ -w /usr/local/bin ]; then
                mv /tmp/gh_${version}_linux_${gh_arch}/bin/gh /usr/local/bin/gh
            else
                sudo mv /tmp/gh_${version}_linux_${gh_arch}/bin/gh /usr/local/bin/gh
            fi
            rm -rf /tmp/gh.tar.gz /tmp/gh_${version}_linux_${gh_arch}
        fi
    else
        error "GitHub CLI installation not supported for OS: ${os}"
        return 1
    fi

    # Verify installation
    if command_exists gh; then
        info "✓ GitHub CLI installed successfully: $(gh --version 2>/dev/null | head -n1)"
    else
        error "GitHub CLI installation failed"
        return 1
    fi
}

# Install Claude agents configuration from agents repo
install_claude_agents_config() {
    local agents_repo="git@github.com:freddiev4/agents.git"
    local clone_dir="/tmp/agents-config-$$"
    local claude_dir="$HOME/.claude"

    info "Installing Claude agents configuration..."

    # Check if git is available
    if ! command_exists git; then
        error "git is required to clone the agents repo"
        return 1
    fi

    # Clone the agents repo to a temp directory
    info "Cloning agents repo..."
    if ! git clone --depth 1 "$agents_repo" "$clone_dir" 2>/dev/null; then
        error "Failed to clone agents repo from $agents_repo"
        error "Make sure you have SSH access to the repository"
        return 1
    fi

    # Create ~/.claude if it doesn't exist
    mkdir -p "$claude_dir"

    # Copy .claude/agents directory
    if [ -d "$clone_dir/.claude/agents" ]; then
        info "Installing Claude agents..."
        mkdir -p "$claude_dir/agents"
        cp -r "$clone_dir/.claude/agents/"* "$claude_dir/agents/" 2>/dev/null || true
        info "✓ Agents installed to $claude_dir/agents/"
    fi

    # Copy .claude/hooks directory
    if [ -d "$clone_dir/.claude/hooks" ]; then
        info "Installing Claude hooks..."
        mkdir -p "$claude_dir/hooks"
        cp -r "$clone_dir/.claude/hooks/"* "$claude_dir/hooks/" 2>/dev/null || true
        info "✓ Hooks installed to $claude_dir/hooks/"
    fi

    # Handle settings.json - merge or install
    if [ -f "$clone_dir/.claude/settings.json" ]; then
        if [ -f "$claude_dir/settings.json" ]; then
            info "Backing up existing settings.json..."
            cp "$claude_dir/settings.json" "$claude_dir/settings.json.backup.$(date +%Y%m%d%H%M%S)"
        fi
        info "Installing Claude settings..."
        cp "$clone_dir/.claude/settings.json" "$claude_dir/settings.json"
        info "✓ Settings installed to $claude_dir/settings.json"
    fi

    # Copy plugins directory
    if [ -d "$clone_dir/plugins" ]; then
        info "Installing Claude plugins..."
        mkdir -p "$claude_dir/plugins"
        # Copy each plugin directory
        for plugin_dir in "$clone_dir/plugins"/*; do
            if [ -d "$plugin_dir" ]; then
                plugin_name=$(basename "$plugin_dir")
                cp -r "$plugin_dir" "$claude_dir/plugins/"
                info "  - Installed plugin: $plugin_name"
            fi
        done
        info "✓ Plugins installed to $claude_dir/plugins/"
    fi

    # Copy skills directory
    if [ -d "$clone_dir/skills" ]; then
        info "Installing Claude skills..."
        mkdir -p "$claude_dir/skills"
        # Copy each skill directory
        for skill_dir in "$clone_dir/skills"/*; do
            if [ -d "$skill_dir" ]; then
                skill_name=$(basename "$skill_dir")
                cp -r "$skill_dir" "$claude_dir/skills/"
                info "  - Installed skill: $skill_name"
            fi
        done
        info "✓ Skills installed to $claude_dir/skills/"
    fi

    # Clean up temp directory
    rm -rf "$clone_dir"

    info "✓ Claude agents configuration installed successfully"
}

# Install Atuin
install_atuin() {
    info "Installing Atuin shell history tool..."

    # Check if atuin is already installed
    if command -v atuin &> /dev/null; then
        local current_version=$(atuin --version 2>/dev/null | head -n1 || echo "unknown")
        warn "Atuin is already installed (version: ${current_version})"
        read -p "Do you want to reinstall? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Skipping Atuin installation"
            return 0
        fi
    fi

    # Download and run the official installer
    info "Downloading and running official Atuin installer..."
    if ! bash <(curl --proto '=https' --tlsv1.2 -sSf https://setup.atuin.sh); then
        error "Failed to install Atuin"
        return 1
    fi

    # Verify installation
    if command -v atuin &> /dev/null; then
        info "✓ Atuin installed successfully: $(atuin --version 2>/dev/null | head -n1)"
        info "  Run 'atuin init' in your shell config to enable it"
    else
        warn "Atuin may have been installed but is not in current PATH"
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

    # Check if docker is already installed and working
    if command -v docker &> /dev/null && docker ps &> /dev/null; then
        local current_version=$(docker --version 2>/dev/null || echo "unknown")
        info "✓ Docker is already installed and running (${current_version})"

        # Check what's providing Docker
        if command_exists colima && colima status 2>&1 | grep -q "colima is running"; then
            info "  Docker is provided by Colima"
        elif [ -d "/Applications/Docker.app" ]; then
            info "  Docker is provided by Docker Desktop"
        fi

        read -p "Do you want to reinstall/change Docker setup? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Keeping existing Docker installation"
            return 0
        fi
    fi

    if [ "$os" = "darwin" ]; then
        # macOS - Offer choice between Colima and Docker Desktop
        echo
        info "Choose Docker installation method:"
        echo "  1) Colima (Recommended - lightweight, faster, open source)"
        echo "  2) Docker Desktop (Official Docker GUI application)"
        echo
        read -p "Enter choice (1 or 2, default: 1): " docker_choice
        docker_choice=${docker_choice:-1}

        if [ "$docker_choice" = "1" ]; then
            info "Installing Docker via Colima..."
            install_colima
            return $?
        fi
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
    local homebrew_version="not installed"
    local virtualbox_version="not installed"
    local docker_version="not installed"
    local colima_version="not installed"
    local docker_provider="none"
    local kubectl_version="not installed"
    local kind_version="not installed"
    local argocd_version="not installed"
    local gh_version="not installed"
    local atuin_version="not installed"
    local claude_version="not installed"
    local uv_version="not installed"
    local bun_version="not installed"

    # Check for Homebrew (macOS only)
    if [ "$os" = "darwin" ] && command_exists brew; then
        homebrew_version=$(brew --version 2>/dev/null | head -n1 || echo "installed (version unknown)")
    fi

    # Check for VirtualBox (macOS only)
    if [ "$os" = "darwin" ] && [ -d "/Applications/VirtualBox.app" ]; then
        virtualbox_version=$(VBoxManage --version 2>/dev/null || echo "installed (version unknown)")
    fi

    # Check for Colima
    if command_exists colima; then
        colima_version=$(colima version 2>/dev/null | grep 'colima version' | awk '{print $3}' || echo "installed (version unknown)")
        if colima status 2>&1 | grep -q "colima is running"; then
            docker_provider="colima"
        fi
    fi

    if command_exists docker; then
        docker_version=$(docker --version 2>/dev/null | sed 's/Docker version //' | cut -d',' -f1 || echo "installed (version unknown)")

        # Determine Docker provider if not already set
        if [ "$docker_provider" = "none" ]; then
            if [ -d "/Applications/Docker.app" ] && pgrep -f "Docker.app" > /dev/null 2>&1; then
                docker_provider="docker-desktop"
            elif [ "$os" = "linux" ]; then
                docker_provider="docker-engine"
            else
                docker_provider="unknown"
            fi
        fi
    fi

    if command_exists kubectl; then
        kubectl_version=$(kubectl version --client --short 2>/dev/null | head -n1 | sed 's/Client Version: //' || echo "installed (version unknown)")
    fi

    if command_exists kind; then
        kind_version=$(kind version 2>/dev/null | grep -oP 'kind v\K[0-9.]+' || echo "installed (version unknown)")
    fi

    if command_exists argocd; then
        argocd_version=$(argocd version --client --short 2>/dev/null | head -n1 | sed 's/argocd: //' || echo "installed (version unknown)")
    fi

    if command_exists gh; then
        gh_version=$(gh --version 2>/dev/null | head -n1 | sed 's/gh version //' | cut -d' ' -f1 || echo "installed (version unknown)")
    fi

    if command_exists atuin; then
        atuin_version=$(atuin --version 2>/dev/null | head -n1 || echo "installed (version unknown)")
    fi

    if command_exists claude; then
        claude_version=$(claude --version 2>/dev/null | head -n1 || echo "installed (version unknown)")
    fi

    if command_exists uv; then
        uv_version=$(uv --version 2>/dev/null || echo "installed (version unknown)")
    fi

    if command_exists bun; then
        bun_version=$(bun --version 2>/dev/null || echo "installed (version unknown)")
    fi

    local claude_agents_count=0
    local claude_plugins_count=0
    local claude_skills_count=0

    if [ -d "$HOME/.claude/agents" ]; then
        claude_agents_count=$(find "$HOME/.claude/agents" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    fi
    if [ -d "$HOME/.claude/plugins" ]; then
        claude_plugins_count=$(find "$HOME/.claude/plugins" -maxdepth 1 -type d 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
    fi
    if [ -d "$HOME/.claude/skills" ]; then
        claude_skills_count=$(find "$HOME/.claude/skills" -maxdepth 1 -type d 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
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
    "homebrew": "${homebrew_version}",
    "virtualbox": "${virtualbox_version}",
    "docker": "${docker_version}",
    "docker_provider": "${docker_provider}",
    "colima": "${colima_version}",
    "kubectl": "${kubectl_version}",
    "kind": "${kind_version}",
    "argocd": "${argocd_version}",
    "gh": "${gh_version}",
    "atuin": "${atuin_version}",
    "claude": "${claude_version}",
    "uv": "${uv_version}",
    "bun": "${bun_version}",
    "claude_agents": ${claude_agents_count},
    "claude_plugins": ${claude_plugins_count},
    "claude_skills": ${claude_skills_count}
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
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}   Server Bootstrap Script             ${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo

    # Detect system
    OS=$(detect_os)
    ARCH=$(detect_arch)

    if [ "$OS" = "unknown" ] || [ "$ARCH" = "unknown" ]; then
        error "Unsupported OS or architecture: $(uname -s)/$(uname -m)"
        exit 1
    fi

    info "Detected system: ${OS}/${ARCH}"
    if [ "$OS" = "darwin" ]; then
        local mac_year=$(detect_mac_year)
        if [ "$mac_year" != "unknown" ]; then
            info "Mac model year: ${mac_year}"
        fi
    fi
    echo

    # Check for required tools
    if ! command_exists curl; then
        error "curl is required but not installed"
        exit 1
    fi

    # Install Homebrew first (macOS only)
    if [ "$OS" = "darwin" ]; then
        install_homebrew || warn "Homebrew installation failed, continuing..."
        echo
    fi

    # Install tools in dependency order
    info "Installing development tools..."
    echo

    # Docker first - required by kind
    install_docker "$OS" "$ARCH" || warn "Docker installation failed, continuing..."
    echo

    # kind second - may install kubectl as dependency
    install_kind "$OS" "$ARCH" || warn "kind installation failed, continuing..."
    echo

    # kubectl third - only if not already installed by kind
    install_kubectl "$OS" "$ARCH" || warn "kubectl installation failed, continuing..."
    echo

    install_argocd "$OS" "$ARCH" || warn "ArgoCD CLI installation failed, continuing..."
    echo

    install_github_cli "$OS" "$ARCH" || warn "GitHub CLI installation failed, continuing..."
    echo

    install_atuin || warn "Atuin installation failed, continuing..."
    echo

    install_claude_code || warn "Claude Code installation failed, continuing..."
    echo

    install_claude_agents_config || warn "Claude agents config installation failed, continuing..."
    echo

    install_uv || warn "uv installation failed, continuing..."
    echo

    install_bun || warn "Bun installation failed, continuing..."
    echo

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}   Bootstrap Complete!                 ${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo

    info "Installed tools:"
    if [ "$OS" = "darwin" ] && command_exists brew; then
        echo "  - homebrew: $(brew --version 2>/dev/null | head -n1)"
    fi
    if [ "$OS" = "darwin" ] && [ -d "/Applications/VirtualBox.app" ]; then
        echo "  - virtualbox: $(VBoxManage --version 2>/dev/null || echo 'installed')"
    fi
    if command_exists docker; then
        echo "  - docker: $(docker --version 2>/dev/null)"
        if command_exists colima && colima status 2>&1 | grep -q "colima is running"; then
            echo "    (via Colima: $(colima version 2>/dev/null | grep 'colima version' | awk '{print $3}'))"
        elif [ -d "/Applications/Docker.app" ]; then
            echo "    (via Docker Desktop)"
        fi
    fi
    if command_exists kubectl; then
        echo "  - kubectl: $(kubectl version --client --short 2>/dev/null | head -n1)"
    fi
    if command_exists kind; then
        echo "  - kind: $(kind version)"
    fi
    if command_exists argocd; then
        echo "  - argocd: $(argocd version --client --short 2>/dev/null | head -n1)"
    fi
    if command_exists gh; then
        echo "  - gh: $(gh --version 2>/dev/null | head -n1)"
    fi
    if command_exists atuin; then
        echo "  - atuin: $(atuin --version 2>/dev/null | head -n1)"
    fi
    if command_exists claude; then
        echo "  - claude: installed (run 'claude --version' to verify)"
        if [ -d "$HOME/.claude/agents" ]; then
            local agent_count=$(find "$HOME/.claude/agents" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
            echo "    agents: ${agent_count} installed"
        fi
        if [ -d "$HOME/.claude/plugins" ]; then
            local plugin_count=$(find "$HOME/.claude/plugins" -maxdepth 1 -type d 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
            echo "    plugins: ${plugin_count} installed"
        fi
        if [ -d "$HOME/.claude/skills" ]; then
            local skill_count=$(find "$HOME/.claude/skills" -maxdepth 1 -type d 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
            echo "    skills: ${skill_count} installed"
        fi
    fi
    if command_exists uv; then
        echo "  - uv: $(uv --version 2>/dev/null)"
    fi
    if command_exists bun; then
        echo "  - bun: $(bun --version 2>/dev/null)"
    fi
    echo

    # Write version report
    write_version_report "$OS" "$ARCH"
    echo

    echo -e "${BLUE}Useful commands:${NC}"
    if command_exists docker; then
        echo "  docker ps                        - List running containers"
        echo "  docker images                    - List images"
    fi
    if command_exists colima; then
        echo "  colima status                    - Check Colima status"
        echo "  colima list                      - List Colima instances"
    fi
    if command_exists kind; then
        echo "  kind create cluster              - Create a Kubernetes cluster"
    fi
    if command_exists kubectl; then
        echo "  kubectl cluster-info             - View cluster info"
    fi
    if command_exists argocd; then
        echo "  argocd --help                    - ArgoCD CLI help"
    fi
    if command_exists gh; then
        echo "  gh auth login                    - Authenticate with GitHub"
        echo "  gh repo clone <repo>             - Clone a repository"
        echo "  gh pr list                       - List pull requests"
    fi
    if command_exists atuin; then
        echo "  atuin search                     - Search shell history"
        echo "  atuin stats                      - View command statistics"
    fi
    if command_exists uv; then
        echo "  uv pip install <pkg>             - Install Python packages"
        echo "  uv venv                          - Create virtual environment"
    fi
    if command_exists bun; then
        echo "  bun run <script>                 - Run a script with Bun"
        echo "  bun install                      - Install dependencies"
    fi
    echo

    warn "You may need to restart your shell for changes to take effect"
}

# Run main function
main
