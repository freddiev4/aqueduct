# Infrastructure Bootstrap Script

Automated installation script for setting up development tools on new servers and workstations.

## Overview

`bootstrap-server.sh` installs essential development and DevOps tools with a single command. It automatically detects your operating system and architecture, then installs the appropriate binaries.

## Installed Tools

The script installs the following tools:

| Tool | macOS | Linux | Purpose |
|------|-------|-------|---------|
| **Homebrew** | ✓ | - | Package manager (installed first on macOS) |
| **Docker** | Colima or Docker Desktop | Docker Engine | Container runtime |
| **kubectl** | ✓ | ✓ | Kubernetes CLI |
| **kind** | ✓ | ✓ | Kubernetes in Docker (local clusters) |
| **ArgoCD CLI** | ✓ | ✓ | GitOps deployment tool |
| **GitHub CLI (gh)** | ✓ | ✓ | GitHub operations from command line |
| **Atuin** | ✓ | ✓ | Enhanced shell history with sync |
| **Claude Code** | ✓ | ✓ | AI-powered development assistant |
| **Claude Agents/Plugins** | ✓ | ✓ | Custom Claude Code configurations |
| **uv** | ✓ | ✓ | Fast Python package manager |
| **Bun** | ✓ | ✓ | Fast JavaScript runtime and package manager |
| **Rust** | ✓ | ✓ | Rust toolchain (rustup, rustc, cargo) |
| **mas** | ✓ | - | Mac App Store CLI |
| **Tailscale** | ✓ | ✓ | VPN for secure remote access (installed last) |
| **VirtualBox** | ✓ (pre-2016 Macs) | - | VM hypervisor (for older Macs) |

## Quick Start

### Basic Usage

```bash
# Make the script executable (if not already)
chmod +x infra/bootstrap-server.sh

# Run the script
./infra/bootstrap-server.sh
```

### Remote Installation

You can run the script directly from the repository:

```bash
curl -fsSL https://raw.githubusercontent.com/your-username/aqueduct/main/infra/bootstrap-server.sh | bash
```

## Requirements

- **Operating System**: macOS or Linux
- **Architecture**: x86_64 (AMD64) or ARM64 (Apple Silicon, aarch64)
- **curl**: Must be installed
- **sudo**: Required for installing to `/usr/local/bin` and Docker setup

## Features

### Automatic Detection
- Detects your OS (macOS/Linux) and architecture (AMD64/ARM64)
- Downloads the correct binaries for your system
- Detects Mac model year (for pre-2016 compatibility checks)

### Smart Installation
- Checks if tools are already installed
- Prompts before reinstalling existing tools
- Continues if individual installations fail
- Handles permissions automatically (requests sudo when needed)
- Installs tools in dependency order (Homebrew → Docker → kind → kubectl → ArgoCD → GitHub CLI → Atuin → Claude Code → Claude Config → uv → Bun → Rust → mas → Tailscale)

### Homebrew Installation (macOS)
- Automatically installs Homebrew if not present
- Configures PATH for both Intel and Apple Silicon Macs
- Used as the package manager for Colima and kubectl on macOS

### Docker Installation
- **macOS**: Choice between Colima (recommended) or Docker Desktop
- **Linux**: Installs Docker Engine (lightweight, no GUI required)
- Automatically adds Linux users to the `docker` group

### Colima (macOS - Recommended)
Colima is a lightweight Docker alternative for macOS:
- Open source and free (no licensing restrictions)
- Faster startup and lower resource usage than Docker Desktop
- Configurable resources (CPU, memory, disk) during setup
- Default configuration: 2 CPU, 4GB RAM, 60GB disk
- Uses QEMU virtualization with SSHFS mounts

### VirtualBox Installation (Pre-2016 Macs)
The script automatically detects Mac model year:
- **Pre-2016 Macs**: Installs VirtualBox first (required for Docker Toolbox on older systems)
- **2016+ Macs**: Skips VirtualBox (Docker Desktop uses native macOS virtualization)

**Note**: Macs older than 2016 may not support modern Docker Desktop (requires macOS 11+). On these systems, you may need to use Docker Toolbox instead.

### GitHub CLI (gh)
- Interact with GitHub from the command line
- Create/view pull requests and issues
- Clone repositories, manage releases, and more
- After installation, run `gh auth login` to authenticate

### Atuin Shell History
- Enhanced shell history with fuzzy search
- Optional sync across machines
- After installation, run `atuin init` to enable in your shell

### Claude Code Configuration
The script installs Claude Code and automatically syncs:
- **Custom agents** from the freddiev4/agents repository
- **Plugins** for extended functionality
- **Skills** for specialized tasks
- **Settings** for Claude Code preferences

A `sync-claude-settings` shell command is added to your configuration to easily update these settings later.

### uv Python Package Manager
- Ultra-fast Python package installer and resolver
- Drop-in replacement for pip and pip-tools
- 10-100x faster than pip
- After installation, use `uv pip install` instead of `pip install`

### Bun JavaScript Runtime
- Fast all-in-one JavaScript runtime (Node.js alternative)
- Built-in bundler, test runner, and package manager
- Drop-in replacement for npm, yarn, and pnpm
- Significantly faster than Node.js for many tasks

### Rust Toolchain
- Complete Rust development environment via rustup
- Includes rustc (Rust compiler) and cargo (build tool and package manager)
- Automatically installs the stable toolchain
- Easy updates via `rustup update`

### mas (Mac App Store CLI)
- Install Mac App Store apps from the command line
- List installed apps and search for new ones
- The script installs Reeder 5 (app ID: 1186187538) automatically
- **Note**: For macOS 12 and older, installs a compatible version via special handling

### Tailscale VPN
**Installed last as the final setup step**

Tailscale provides secure remote access to your server:
- Creates a private network across all your devices
- Works through firewalls and NAT without configuration
- Each device gets a stable private IP (100.x.x.x range)
- Optional security lockdown to make server **only** accessible via Tailscale

After installation, the script prompts you to:
1. Connect to your Tailscale network (`tailscale up`)
2. Optionally run the security lockdown script (`~/aqueduct/infra/tailscale-setup.sh`)

**Security Lockdown**: When enabled, uses macOS firewall and packet filter (pf) to block all incoming connections except from Tailscale IPs. The script automatically detects your current Tailscale IP and ensures your server is only accessible when connected to your Tailscale VPN.

### Version Report
After installation completes, the script generates a JSON report:

```bash
server-initialization-2026-01-08T15-30-45Z.json
```

Example output (Linux):
```json
{
  "timestamp": "2026-01-08T15:30:45Z",
  "hostname": "my-server",
  "system": {
    "os": "Linux",
    "kernel": "5.15.0-generic",
    "architecture": "amd64",
    "detected_os": "linux",
    "mac_year": "n/a"
  },
  "tools": {
    "homebrew": "not installed",
    "virtualbox": "not installed",
    "docker": "25.0.0",
    "docker_provider": "docker-engine",
    "colima": "not installed",
    "kubectl": "v1.29.0",
    "kind": "0.31.0",
    "argocd": "v2.9.3",
    "gh": "gh version 2.40.1",
    "atuin": "18.0.0",
    "claude": "1.2.3",
    "uv": "uv 0.1.0",
    "bun": "1.0.25",
    "rust": "1.78.0",
    "cargo": "1.78.0",
    "mas": "not installed",
    "tailscale": "1.94.2",
    "tailscale_ip": "100.116.110.79",
    "claude_agents": 5,
    "claude_plugins": 3,
    "claude_skills": 4
  }
}
```

Example output (macOS with Colima):
```json
{
  "timestamp": "2026-01-08T15:30:45Z",
  "hostname": "mac-mini",
  "system": {
    "os": "Darwin",
    "kernel": "23.0.0",
    "architecture": "arm64",
    "detected_os": "darwin",
    "mac_year": "2023"
  },
  "tools": {
    "homebrew": "Homebrew 4.2.0",
    "virtualbox": "not installed",
    "docker": "24.0.7",
    "docker_provider": "colima",
    "colima": "0.6.8",
    "kubectl": "v1.29.0",
    "kind": "0.31.0",
    "argocd": "v2.9.3",
    "gh": "gh version 2.40.1",
    "atuin": "18.0.0",
    "claude": "1.2.3",
    "uv": "uv 0.1.0",
    "bun": "1.0.25",
    "rust": "1.78.0",
    "cargo": "1.78.0",
    "mas": "1.8.6",
    "tailscale": "1.94.2",
    "tailscale_ip": "100.116.110.79",
    "claude_agents": 5,
    "claude_plugins": 3,
    "claude_skills": 4
  }
}
```

## Post-Installation

### Docker (Linux)
After installing Docker on Linux, you'll need to log out and back in for docker group membership to take effect. Alternatively, run:
```bash
newgrp docker
```

### Colima (macOS)
Colima should start automatically after installation. To manage Colima:
```bash
colima status          # Check if running
colima start           # Start Colima
colima stop            # Stop Colima
colima list            # List instances
```

### Docker Desktop (macOS)
If you chose Docker Desktop, you may need to start it manually from Applications after installation.

### Atuin
After installation, add Atuin to your shell configuration:
```bash
# For bash (add to ~/.bashrc)
eval "$(atuin init bash)"

# For zsh (add to ~/.zshrc)
eval "$(atuin init zsh)"
```

Then restart your shell or source the config file.

### GitHub CLI
Authenticate with GitHub before using:
```bash
gh auth login
```

Follow the prompts to authenticate via web browser or token.

### Claude Code
On first use, Claude Code will prompt you to log in:
```bash
claude
```

The script automatically installs custom agents, plugins, and skills. To update them later:
```bash
sync-claude-settings
```

### uv Python Package Manager
Use uv as a faster alternative to pip:
```bash
# Install packages
uv pip install requests

# Create virtual environment
uv venv

# Install from requirements.txt
uv pip install -r requirements.txt
```

### Bun
Use bun for JavaScript/TypeScript projects:
```bash
# Run a script
bun run script.ts

# Install dependencies
bun install

# Create a new project
bun init
```

### Rust
The Rust toolchain is ready to use immediately after installation:
```bash
# Verify installation
rustc --version
cargo --version

# Create a new project
cargo new my_project
cd my_project

# Build and run
cargo build
cargo run

# Update Rust
rustup update
```

The Rust environment is automatically added to your PATH via `~/.cargo/env`.

### mas (Mac App Store CLI)
List and install Mac App Store apps:
```bash
# List installed apps
mas list

# Search for apps
mas search "App Name"

# Install an app by ID
mas install 1186187538
```

### Tailscale
After installation, connect to your Tailscale network:
```bash
# Connect to Tailscale
tailscale up

# Check status
tailscale status

# View your Tailscale IP
tailscale ip
```

#### Tailscale Security Lockdown
To make your server **only** accessible via Tailscale:

1. **Ensure you're connected to Tailscale first**:
   ```bash
   tailscale status
   ```

2. **Run the security setup script**:
   ```bash
   cd ~/aqueduct/infra
   sudo ./tailscale-setup.sh
   ```

This will:
- Enable macOS Application Firewall with stealth mode
- Configure packet filter (pf) to only allow Tailscale IPs (100.64.0.0/10)
- Block all other incoming connections from local network and internet
- Auto-detect and display your current Tailscale IP address
- Make the rules persist across reboots

**⚠️ WARNING**: After running the security script, you will **ONLY** be able to access this server via Tailscale. Make sure Tailscale is working before proceeding!

To disable security lockdown:
```bash
sudo pfctl -d  # Disable packet filter
```

To re-enable:
```bash
sudo pfctl -e -f /etc/pf.conf
```

## Troubleshooting

### Permission Denied Errors
If you encounter permission errors, ensure you have sudo privileges:
```bash
sudo -v
```

### Docker Not Starting (macOS with Colima)
If Docker commands fail after Colima installation:
```bash
# Check Colima status
colima status

# Start Colima if not running
colima start

# Verify Docker is accessible
docker ps
```

### Docker Not Starting (macOS with Docker Desktop)
Open Docker Desktop from Applications to initialize it:
```bash
open /Applications/Docker.app
```

### Tools Not in PATH
If installed tools aren't found after installation, try:
```bash
# Reload shell configuration
source ~/.bashrc  # or ~/.zshrc for zsh

# Or restart your terminal
```

### Version Report Not Generated
Ensure you have write permissions in the directory where you run the script.

### VirtualBox Kernel Extensions (macOS)
After installing VirtualBox on macOS, you may need to approve kernel extensions:
1. Open **System Preferences** > **Security & Privacy**
2. Click the lock icon and authenticate
3. Click **Allow** next to the VirtualBox kernel extension message
4. Restart your Mac if prompted

### Old Mac Compatibility
If you have a Mac older than 2016:
- Modern Docker Desktop may not work (requires macOS 11+)
- The script will install VirtualBox automatically
- Consider using Docker Toolbox (deprecated but works on older systems)
- Check Docker Toolbox documentation for setup instructions

## Supported Platforms

### macOS
- **Modern Macs** (2016+): macOS 11 (Big Sur) or later
- **Older Macs** (pre-2016): Requires VirtualBox; Docker Desktop may not be compatible
- Intel (x86_64) and Apple Silicon (ARM64)

### Linux
- Ubuntu 18.04+
- Debian 10+
- CentOS 7+
- Fedora 30+
- RHEL 7+
- Other distributions with systemd

## Security Notes

- The script uses official installation methods from each tool's documentation
- Docker for Linux uses the official convenience script from `get.docker.com`
- All downloads use HTTPS
- The script accepts Docker Desktop license automatically with `--accept-license`

## Uninstallation

To remove installed tools:

**Colima (macOS)**:
```bash
colima stop
colima delete
brew uninstall colima
brew uninstall docker  # Docker CLI
```

**Docker Desktop (macOS)**:
```bash
sudo /Applications/Docker.app/Contents/MacOS/uninstall
rm -rf /Applications/Docker.app
```

**Docker Engine (Linux)**:
```bash
sudo apt-get purge docker-ce docker-ce-cli containerd.io  # Ubuntu/Debian
sudo yum remove docker-ce docker-ce-cli containerd.io     # CentOS/RHEL
```

**VirtualBox (macOS)**:
```bash
# Run the VirtualBox uninstaller
sudo /Library/Application\ Support/VirtualBox/LaunchDaemons/VirtualBoxStartup.sh uninstall
# Remove the application
sudo rm -rf /Applications/VirtualBox.app
```

**Other Tools**:
```bash
# Kubernetes tools
sudo rm /usr/local/bin/kind
sudo rm /usr/local/bin/kubectl
sudo rm /usr/local/bin/argocd

# GitHub CLI
brew uninstall gh  # macOS
sudo apt remove gh  # Linux

# Atuin - remove binary and shell integration
rm -rf ~/.atuin
# Remove the eval "$(atuin init ...)" line from your shell config

# Claude Code has built-in uninstall
claude uninstall

# Claude settings
rm -rf ~/.claude/agents ~/.claude/plugins ~/.claude/skills
# Remove sync-claude-settings function from your shell config

# uv
rm -rf ~/.cargo/bin/uv ~/.local/bin/uv

# Bun
rm -rf ~/.bun

# Rust
rustup self uninstall

# mas
brew uninstall mas  # macOS

# Tailscale (macOS)
brew uninstall --cask tailscale
sudo rm -rf /Applications/Tailscale.app

# Tailscale (Linux)
sudo apt remove tailscale  # Ubuntu/Debian
sudo yum remove tailscale  # CentOS/RHEL

# Remove Tailscale security configuration (if applied)
sudo pfctl -d  # Disable packet filter
sudo rm /etc/pf.anchors/tailscale
sudo rm /Library/LaunchDaemons/com.tailscale.pf.plist
# Edit /etc/pf.conf and remove the tailscale anchor lines
```

## Contributing

To add new tools to the bootstrap script:

1. Create a new `install_<toolname>()` function
2. Add the function call in `main()`
3. Update `write_version_report()` to include the new tool
4. Update this README

## License

This script is part of the Aqueduct project.
