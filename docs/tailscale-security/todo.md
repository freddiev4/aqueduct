# Tailscale Security Setup Todo

## Setup Tasks
- [ ] Enable macOS Application Firewall
- [ ] Enable stealth mode
- [ ] Create pf rules file at /etc/pf.anchors/tailscale
- [ ] Update /etc/pf.conf to load Tailscale anchor
- [ ] Enable and load pf
- [ ] Create LaunchDaemon for pf persistence
- [ ] Test SSH access from Tailscale device
- [ ] Test that non-Tailscale connections are blocked
- [ ] Verify pf rules are active after reboot

## Verification
- [ ] Confirm firewall is enabled: `sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate`
- [ ] Confirm pf is enabled: `sudo pfctl -s info`
- [ ] Confirm pf rules are loaded: `sudo pfctl -s rules`
- [ ] Test connectivity from iPhone (Tailscale)
- [ ] Test connectivity from PC (Tailscale)
- [ ] Test that public IP is blocked
