# rtc-reward-action

> GitHub Action to automatically award **RTC tokens** when a pull request is merged. Any open-source project can add one YAML file and instantly start rewarding contributors with crypto.

---

## ✨ Features

- ✅ Configurable RTC amount per merge
- ✅ Reads contributor wallet from PR body (format: `RTC...` or `wallet: name`)
- ✅ Posts confirmation comment on PR after transfer
- ✅ Dry-run mode for testing
- ✅ GitHub Marketplace ready

---

## 🚀 Quick Start

### 1. Add the Action

Create `.github/workflows/rtc-reward.yml`:

```yaml
name: RTC Reward

on:
  pull_request:
    types: [closed]

jobs:
  reward:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: FlintLeng/rtc-reward-action@v1
        with:
          node-url: https://50.28.86.131
          amount: 5
          wallet-from: ${{ secrets.RTC_WALLET }}
          admin-key: ${{ secrets.RTC_ADMIN_KEY }}
```

### 2. Add Secrets

In your repo's **Settings → Secrets**, add:
- `RTC_WALLET` — sender wallet name
- `RTC_ADMIN_KEY` — admin key for signing transactions

### 3. Contributors Add Their Wallet

Contributors add their wallet address in the PR body:

```markdown
## RTC Wallet
RTC1234567890abcdef1234567890abcdef12345678
```

Or simply:

```
wallet: mywalletname
```

---

## 📋 Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `node-url` | ✅ | `https://50.28.86.131` | RustChain node URL |
| `amount` | ✅ | `5` | RTC amount per merge |
| `wallet-from` | ✅ | — | Sender wallet name |
| `admin-key` | ✅ | — | Admin key for signing |
| `dry-run` | ❌ | `false` | Test mode (no actual TX) |
| `github-token` | ❌ | `github.token` | GitHub token |

---

## 🧪 Dry Run Mode

Test without spending real tokens:

```yaml
- uses: FlintLeng/rtc-reward-action@v1
  with:
    node-url: https://50.28.86.131
    amount: 5
    wallet-from: test-wallet
    admin-key: test-key
    dry-run: true
```

---

## 📖 How It Works

```
PR Merged
    ↓
Extract wallet from PR body
    ↓
Call RustChain node API /wallet/send
    ↓
Post confirmation comment on PR
```

### API Endpoint

```
POST /wallet/send
{
  "from": "project-wallet",
  "to": "contributor-wallet",
  "amount": 5,
  "admin_key": "..."
}
```

---

## 🏗️ Architecture

```
.github/workflows/rtc-reward.yml
    └── rtc-reward-action/
        ├── action.yml      # Action metadata
        └── src/
            └── reward.py   # Python entrypoint
```

---

## 🛡️ Security Notes

- Admin key is stored as a GitHub Secret — never exposed in logs
- Only `merged == true` triggers the action
- Dry-run mode available for testing

---

## 📦 Publish to GitHub Marketplace

1. Create a release: `git tag v1.0.0 && git push --tags`
2. Go to repo → Releases → Draft a new release
3. Publish to GitHub Marketplace

---

## 🤝 License

MIT — free to use and modify.
