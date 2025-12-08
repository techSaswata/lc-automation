#!/bin/bash
# Setup script for LeetCode Daily Auto Solver - Local Mac Version

echo "🚀 Setting up LeetCode Daily Auto Solver..."
echo ""

# Load credentials from keys.md
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check Python3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python3 first."
    exit 1
fi

echo "✓ Python3 found"

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip3 install requests google-generativeai beautifulsoup4 lxml --quiet
echo "✓ Dependencies installed"

# Read credentials from keys.md
echo ""
echo "📝 Reading credentials from keys.md..."

# Extract values (you'll need to update keys.md format or manually set these)
GEMINI_KEY=$(grep "AIzaSy" keys.md | head -1 | cut -d':' -f2- | tr -d ' "')
CSRF=$(grep "csrf:" keys.md | cut -d':' -f2 | tr -d ' ')
SESSION=$(grep "LEETCODE_SESSION:" keys.md | cut -d':' -f2- | tr -d ' ')
EMAIL_USER=$(grep "EMAIL_USER:" keys.md | cut -d':' -f2 | tr -d ' ')
EMAIL_PASS=$(grep "EMAIL_PASS:" keys.md | cut -d':' -f2 | tr -d ' ')
EMAIL_TO=$(grep "EMAIL_TO:" keys.md | cut -d':' -f2 | tr -d ' ')

# Create the plist with actual values
PLIST_FILE="$HOME/Library/LaunchAgents/com.leetcode.daily.solver.plist"

cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.leetcode.daily.solver</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>$(which python3)</string>
        <string>$SCRIPT_DIR/local_runner.py</string>
    </array>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>LEETCODE_SESSION</key>
        <string>$SESSION</string>
        <key>LEETCODE_CSRF</key>
        <string>$CSRF</string>
        <key>GEMINI_API_KEY</key>
        <string>$GEMINI_KEY</string>
        <key>EMAIL_USER</key>
        <string>$EMAIL_USER</string>
        <key>EMAIL_PASS</key>
        <string>$EMAIL_PASS</string>
        <key>EMAIL_TO</key>
        <string>$EMAIL_TO</string>
    </dict>
    
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/local_runner.log</string>
    
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/local_runner_error.log</string>
    
    <key>StartInterval</key>
    <integer>3600</integer>
</dict>
</plist>
EOF

echo "✓ Created launchd plist at: $PLIST_FILE"

# Make runner executable
chmod +x local_runner.py

# Load the service
launchctl unload "$PLIST_FILE" 2>/dev/null
launchctl load "$PLIST_FILE"

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 How it works:"
echo "  • Runs automatically when Mac opens/wakes"
echo "  • Runs every hour to check if today's problem is solved"
echo "  • If not solved yet, attempts to solve"
echo "  • Once successful, won't run again until next day"
echo "  • Saves state in .daily_success.json"
echo ""
echo "📊 Check logs:"
echo "  • Output: $SCRIPT_DIR/local_runner.log"
echo "  • Errors: $SCRIPT_DIR/local_runner_error.log"
echo ""
echo "🧪 Test it now:"
echo "  python3 local_runner.py"
echo ""
echo "🛑 To disable:"
echo "  launchctl unload $PLIST_FILE"
echo ""

