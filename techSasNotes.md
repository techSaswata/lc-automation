# Technical Notes

## Manual GitHub Actions Workflow Execution

```bash
gh workflow run daily.yml
```

---

## File Structure & Purpose

| File | Purpose | Git Status |
|------|---------|------------|
| `daily.py` | Main production script | Tracked |
| `daily_local_test.py` | Local testing version of daily.py | `.gitignore` |
| `keys.md` | Environment variables storage | `.gitignore` |
| `test_lc_submit_endpoint.py` | LeetCode submit endpoint testing | `.gitignore` |

---

## ⚠️ Important Reminders

> **Token Expiration**: `LEETCODE_SESSION` and `CSRF_TOKEN` expire every **14 days** and must be updated regularly in GitHub Secrets and `keys.md`.

### Updating LEETCODE_SESSION and CSRF_TOKEN via CLI 

Go to the folder in local.. run.. 

```bash
gh secret set LEETCODE_SESSION --body " "
gh secret set LEETCODE_CSRF --body " "
```

(Note:Inverted commas will be there)

---

Thought and Made with ❤️ by techSas