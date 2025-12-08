# 🍎 Local Mac Runner - Setup Guide

## What This Does

✅ **Runs when your Mac opens** (login/wake)  
✅ **Automatically retries** until success for the day  
✅ **Smart state tracking** - won't run if already successful today  
✅ **Edge case handling** - opens/closes multiple times? No problem!  
✅ **Works locally** - No cloud, no proxies, no blocking!

## How It Works

```
Mac Opens → Script Runs → Check if solved today?
                              ↓
                         Not solved yet
                              ↓
                    Try to solve → Success?
                         ↓              ↓
                        Yes            No
                         ↓              ↓
                    Save state    Retry next time
                    Mark done     Mac opens
                    Don't run
                    again today
```

## Quick Setup (2 minutes)

### Step 1: Make setup script executable

```bash
cd /Users/techsaswata/Downloads/lc-automation
chmod +x setup_local.sh
```

### Step 2: Run setup

```bash
./setup_local.sh
```

That's it! ✅

## What Gets Installed

1. **local_runner.py** - Main script that runs
2. **~/Library/LaunchAgents/com.leetcode.daily.solver.plist** - Mac service config
3. **.daily_success.json** - Tracks today's success state

## Testing

### Test manually first:

```bash
python3 local_runner.py
```

You should see:
```
============================================================
LeetCode Daily Auto Solver - Local Mac Version
============================================================

[1/6] Fetching daily challenge...
✓ Problem: [Problem Name]
...
```

### Check logs:

```bash
# Output log
tail -f local_runner.log

# Error log
tail -f local_runner_error.log
```

### Check if service is running:

```bash
launchctl list | grep leetcode
```

Should show: `com.leetcode.daily.solver`

## Edge Cases Handled

### ✅ **Multiple Opens/Closes in a Day**
- Script checks `.daily_success.json`
- If already successful today → exits immediately
- If not successful → tries again

### ✅ **Failed Attempts**
- Marks as unsuccessful
- Will retry next time Mac opens
- Keeps trying until successful

### ✅ **New Day**
- Automatically detects new date
- Resets state
- Tries new problem

### ✅ **Mac Sleep/Wake**
- Runs on wake
- Quick check → exits if done
- Smart throttling (won't spam)

## State File Format

`.daily_success.json`:
```json
{
  "date": "2025-12-08",
  "success": true,
  "timestamp": "2025-12-08T07:15:30.123456"
}
```

## Customize Behavior

Edit `com.leetcode.daily.solver.plist`:

```xml
<!-- Run every hour (3600 seconds) -->
<key>StartInterval</key>
<integer>3600</integer>

<!-- Or run only at login/wake, remove StartInterval and use: -->
<key>RunAtLoad</key>
<true/>
```

## Manual Controls

### Stop service:
```bash
launchctl unload ~/Library/LaunchAgents/com.leetcode.daily.solver.plist
```

### Start service:
```bash
launchctl load ~/Library/LaunchAgents/com.leetcode.daily.solver.plist
```

### Force run now:
```bash
python3 local_runner.py
```

### Reset today's state:
```bash
rm .daily_success.json
```

## Troubleshooting

### Script not running?

1. Check if service is loaded:
   ```bash
   launchctl list | grep leetcode
   ```

2. Check logs:
   ```bash
   cat local_runner_error.log
   ```

3. Test manually:
   ```bash
   python3 local_runner.py
   ```

### "No module named 'requests'"?

Install dependencies:
```bash
pip3 install requests google-generativeai beautifulsoup4 lxml
```

### Getting LeetCode errors?

Update your credentials in `keys.md`:
- Fresh `LEETCODE_SESSION` cookie
- Fresh `csrftoken`

Then re-run:
```bash
./setup_local.sh
```

## Comparing with GitHub Actions

| Feature | GitHub Actions | Local Mac |
|---------|---------------|-----------|
| **Runs when** | Scheduled time | Mac opens |
| **Requires Mac on** | No | Yes |
| **Blocked by LeetCode** | Yes ❌ | No ✅ |
| **Needs proxy** | Yes ($49/mo) | No (FREE) |
| **Auto retry** | Fixed attempts | Until success ✅ |
| **State tracking** | No | Yes ✅ |
| **Cost** | Free | Free ✅ |

## Benefits

✅ **FREE** - No proxies needed  
✅ **Smart** - Tracks state, won't duplicate  
✅ **Reliable** - Runs from your IP (not blocked)  
✅ **Flexible** - Retries until success  
✅ **Simple** - One command setup

## Note

The GitHub Actions version will remain for manual triggers, but this local version is recommended for daily automatic solving!

