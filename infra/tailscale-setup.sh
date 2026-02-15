#!/bin/bash
set -e

echo "🔒 Setting up Tailscale-only access for this Mac..."
echo ""

# Step 0: Check if SSH is enabled
echo "Step 0: Checking if Remote Login (SSH) is enabled..."
if sudo systemsetup -getremotelogin 2>/dev/null | grep -q "Remote Login: On"; then
    echo "✅ Remote Login (SSH) is enabled"
else
    echo "⚠️  Remote Login (SSH) is currently disabled"
    read -p "Would you like to enable it now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemsetup -setremotelogin on
        echo "✅ Remote Login (SSH) enabled"
    else
        echo "⚠️  Skipping SSH enablement - you won't be able to SSH to this Mac"
        echo "   To enable later: System Settings → General → Sharing → Remote Login"
    fi
fi
echo ""

# Step 1: Enable macOS Firewall
echo "Step 1: Enabling macOS Application Firewall..."
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on
echo "✅ Firewall enabled with stealth mode"
echo ""

# Step 2: Create pf rules
echo "Step 2: Creating packet filter rules..."
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
echo "✅ Created /etc/pf.anchors/tailscale"
echo ""

# Step 3: Update main pf config if not already done
echo "Step 3: Updating pf configuration..."
if ! grep -q 'anchor "tailscale"' /etc/pf.conf 2>/dev/null; then
    echo 'anchor "tailscale"' | sudo tee -a /etc/pf.conf > /dev/null
    echo 'load anchor "tailscale" from "/etc/pf.anchors/tailscale"' | sudo tee -a /etc/pf.conf > /dev/null
    echo "✅ Updated /etc/pf.conf"
else
    echo "✅ pf.conf already configured"
fi
echo ""

# Step 4: Enable and load pf
echo "Step 4: Enabling packet filter..."
sudo pfctl -e -f /etc/pf.conf 2>/dev/null || true
echo "✅ Packet filter enabled and rules loaded"
echo ""

# Step 5: Create LaunchDaemon for persistence
echo "Step 5: Creating LaunchDaemon for persistence..."
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

sudo launchctl load /Library/LaunchDaemons/com.tailscale.pf.plist 2>/dev/null || true
echo "✅ LaunchDaemon created and loaded"
echo ""

# Step 6: Verify
echo "Step 6: Verifying configuration..."
echo ""
echo "Firewall status:"
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate
echo ""
echo "Packet filter status:"
sudo pfctl -s info 2>/dev/null | head -n 5
echo ""
echo "Active pf rules:"
sudo pfctl -s rules | grep -A 2 "anchor \"tailscale\""
echo ""

echo "✅ Setup complete!"
echo ""

# Get current Tailscale IP
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")

echo "⚠️  IMPORTANT: Your Mac is now only accessible via Tailscale!"
echo "   Tailscale IP: $TAILSCALE_IP"
echo "   To connect: ssh <user>@$TAILSCALE_IP"
echo ""
echo "To disable: sudo pfctl -d"
echo "To re-enable: sudo pfctl -e -f /etc/pf.conf"
