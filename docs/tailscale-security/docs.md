# Tailscale-Only Access Documentation

## Overview
This configuration restricts all network access to the Mac Mini to only devices connected via Tailscale VPN.

## Quick Setup
Run the automated setup script:
```bash
cd /path/to/aqueduct
./infra/tailscale-setup.sh
```

The script will automatically configure firewall rules and make them persistent across reboots.

## How It Works

### Tailscale Network
Tailscale creates a private network using the CGNAT IP range 100.64.0.0/10. Each device gets a unique IP in this range that remains consistent.

### macOS Firewall Layers
1. **Application Firewall** - Controls which apps can accept incoming connections
2. **Packet Filter (pf)** - Lower-level firewall that can filter by IP range

### Security Strategy
- Allow all outbound traffic (you can browse internet, make API calls)
- Allow return traffic for connections you initiated
- Use pf to block ALL unsolicited incoming traffic except from 100.64.0.0/10 range
- Enable stealth mode to prevent port scanning
- Keep local loopback (127.0.0.1) open for local services

## Setup Commands

### 1. Enable macOS Firewall
```bash
# Enable firewall
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on

# Enable stealth mode (don't respond to ping/probe)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on

# Check status
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
```

### 2. Create pf Rules File
Create `/etc/pf.anchors/tailscale`:
```
# Allow all traffic on loopback interface
pass quick on lo0

# Allow all incoming traffic from Tailscale network (100.64.0.0/10)
pass in quick from 100.64.0.0/10

# Allow all outbound traffic and keep state for return traffic
pass out quick keep state

# Block all other unsolicited incoming traffic
block in log all
```

**How these rules work:**
- **Loopback**: Allows local services to communicate (127.0.0.1)
- **Tailscale**: Allows all incoming connections from Tailscale devices
- **Outbound + keep state**: Allows you to initiate connections AND automatically allows their return traffic
- **Block**: Blocks unsolicited incoming connections from non-Tailscale IPs

### 3. Load pf Rules
```bash
# Create the rules file
sudo tee /etc/pf.anchors/tailscale > /dev/null << 'EOF'
# Allow all traffic on loopback interface
pass quick on lo0

# Allow all incoming traffic from Tailscale network (100.64.0.0/10)
pass in quick from 100.64.0.0/10

# Allow all outbound traffic and keep state for return traffic
pass out quick keep state

# Block all other unsolicited incoming traffic
block in log all
EOF

# Add anchor to main pf config
echo "anchor \"tailscale\"" | sudo tee -a /etc/pf.conf
echo "load anchor \"tailscale\" from \"/etc/pf.anchors/tailscale\"" | sudo tee -a /etc/pf.conf

# Enable and load pf
sudo pfctl -e -f /etc/pf.conf
```

### 4. Make pf Persist After Reboot
Create a LaunchDaemon:
```bash
sudo tee /Library/LaunchDaemons/com.tailscale.pf.plist > /dev/null << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tailscale.pf</string>
    <key>ProgramArguments</key>
    <array>
        <string>/sbin/pfctl</string>
        <string>-e</string>
        <string>-f</string>
        <string>/etc/pf.conf</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
EOF

sudo launchctl load /Library/LaunchDaemons/com.tailscale.pf.plist
```

## Testing

### From Tailscale Device
```bash
# Should work
ssh freddie-mac-mini@100.116.110.79

# Or by hostname if MagicDNS is enabled
ssh freddies-mac-mini
```

### From Non-Tailscale Device
Connection should be refused or timeout.

## Troubleshooting

### Check pf Status
```bash
sudo pfctl -s info
sudo pfctl -s rules
```

### Temporarily Disable pf
```bash
sudo pfctl -d
```

### Re-enable pf
```bash
sudo pfctl -e -f /etc/pf.conf
```

### View Blocked Traffic
```bash
sudo pfctl -s state
```

## References
- [Tailscale CGNAT IP Range](https://tailscale.com/kb/1015/100.x-addresses)
- [macOS pf Documentation](https://www.openbsd.org/faq/pf/)
- [macOS Application Firewall](https://support.apple.com/guide/mac-help/block-connections-to-your-mac-with-a-firewall-mh34041/)
