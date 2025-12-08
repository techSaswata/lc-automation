# 🔥 Setup ScraperAPI Proxy (FREE!)

## Step 1: Sign Up for ScraperAPI (FREE)

1. Go to: https://www.scraperapi.com/
2. Click **"Start Free Trial"**
3. Sign up with your email
4. No credit card required for free tier!
5. **Free tier gives:** 1,000 requests/month (plenty for daily LeetCode)

## Step 2: Get Your API Key

1. After signing up, go to: https://dashboard.scraperapi.com/
2. Copy your **API Key** (looks like: `abc123def456...`)

## Step 3: Add to GitHub Secrets

Run this command (replace `YOUR_API_KEY` with actual key):

```bash
cd /Users/techsaswata/Downloads/lc-automation
echo "YOUR_SCRAPERAPI_KEY" | gh secret set PROXY_API_KEY
```

**Example:**
```bash
echo "abc123def456ghi789" | gh secret set PROXY_API_KEY
```

## Step 4: Test It!

```bash
gh workflow run daily.yml
```

Check logs:
```bash
sleep 40 && gh run list --limit 1
```

## ✅ What to Expect

With proxy, you should see:
```
Using proxy...
✓ Problem: [Problem Name]
✓ Code generated
Using proxy for submission...
✓ Submission ID: 123456
Result: Accepted
✓ Saved as leetcode-Dec08-25.java
Email sent successfully!
```

## 💰 Cost

- **Free tier:** 1,000 requests/month
- **Your usage:** ~60 requests/month (2 per day)
- **Cost:** $0/month ✅

## 🔄 If Free Tier Runs Out

You'll get 1000 requests which resets monthly. If you somehow run out:

1. Create new account with different email
2. Or upgrade to paid ($29/month for 100k requests - overkill for your use)

## 🎯 Current Status

**Without proxy:** ❌ GitHub Actions blocked by LeetCode  
**With proxy:** ✅ Should work perfectly!

## 📝 Notes

- Script automatically detects if `PROXY_API_KEY` is set
- If not set, runs without proxy (will likely fail)
- Proxy adds ~1-2 seconds delay per request
- Your free quota is plenty (uses ~2% per month)

