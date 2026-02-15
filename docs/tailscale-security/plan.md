# Tailscale-Only Access Security Plan

## Goal
Configure Mac Mini to only be accessible when connected via Tailscale network.

## Automated Setup
The security configuration is available as a standalone script at `infra/tailscale-setup.sh`. This script automatically:
- Enables macOS firewall with stealth mode
- Creates and loads pf rules for Tailscale-only access
- Makes configuration persistent across reboots
- Auto-detects your current Tailscale IP address

It's also integrated into the `infra/bootstrap-server.sh` script, where Tailscale is installed as the **last step** of the bootstrap process, and users are prompted to optionally run the security lockdown immediately after installation.

## Approach
1. Enable macOS Application Firewall
2. Configure packet filter (pf) rules to only allow Tailscale network (100.x.x.x/8)
3. Block all incoming connections except from Tailscale IPs
4. Test connectivity

## Tailscale Network Info
- Tailscale IP: 100.116.110.79
- Tailscale network range: 100.64.0.0/10 (CGNAT range used by Tailscale)
- Other devices:
  - iPhone: 100.95.135.16
  - PC: 100.72.53.112

## Implementation Steps
1. Enable macOS firewall in stealth mode
2. Create pf rules file to allow only Tailscale traffic
3. Load pf rules
4. Test connectivity from Tailscale devices
5. Verify non-Tailscale connections are blocked
