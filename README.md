# rtc-reward-action

> Automatically award **RustChain (RTC)** tokens when a PR is merged.
> Turns any GitHub repository into a bounty platform — zero infrastructure needed.

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-rtc--reward--action-blue?logo=github)](https://github.com/marketplace/actions/rtc-reward-action)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Test Suite](https://github.com/FlintLeng/rtc-reward-action/workflows/Test%20Suite/badge.svg)](https://github.com/FlintLeng/rtc-reward-action/actions)

---

## Features

- ✅ **Configurable RTC amount** per merge
- ✅ **Wallet discovery** (PR body → `.rtc-wallet` file → GitHub username → fallback)
- ✅ **Balance check** — refuses to send if source wallet is low
- ✅ **PR comment** — posts TX confirmation directly on the merged PR
- ✅ **Dry-run mode** — test without spending real RTC
- ✅ **Zero dependencies** — pure Python stdlib, `ubuntu-latest` compatible
- ✅ **GitHub Marketplace ready** — proper YAML metadata, badges, versioning

---

## Quick Start

```yaml
# .github/workflows/rtc-reward.yml
name: RTC Reward

on:
  pull_request:
    types: [closed]

jobs:
  reward:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - uses: FlintLeng/rtc-reward-action@v2
        with:
          node-url: https://50.28.86.131
          amount: 5
          wallet-from: my-project-fund
          admin-key: ${{ secrets.RTC_ADMIN_KEY }}
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

**That's it.** When a PR merges, contributors earn RTC automatically.

---

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `node-url` | No | `https://50.28.86.131` | RustChain node URL |
| `amount` | No | `5` | RTC to award per merged PR |
| `wallet-from` | **Yes** | — | Source wallet name |
| `admin-key` | **Yes** | — | Admin key for source wallet (**store as secret!**) |
| `dry-run` | No | `false` | Simulate without sending real RTC |
| `github-token` | No | `${{ github.token }}` | Token for posting PR comments |
| `fallback-wallet` | No | — | Fallback if no wallet found |
| `min-balance` | No | — | Min balance in source wallet to trigger send |

## Outputs

| Output | Description |
|--------|-------------|
| `recipient-wallet` | Wallet that received RTC |
| `tx-id` | Transaction ID of the transfer |
| `amount-sent` | Amount of RTC sent |

---

## Wallet Discovery

Priority order:

1. **PR body** — look for `rtc-wallet: <name>` or raw wallet address anywhere
2. **`.rtc-wallet` file** — fetched from repo root via GitHub API
3. **PR author GitHub username** — used as wallet name directly
4. **`fallback-wallet` input** — explicit fallback

### Example PR body

```markdown
## What changed

Fixed the scheduler bug in `engine.py`.

rtc-wallet: alice_dev
```

---

## Dry-Run Mode

Set `dry-run: true` to simulate a reward without spending real RTC:

```yaml
- uses: FlintLeng/rtc-reward-action@v2
  with:
    dry-run: true   # ← test here
    ...
```

The action will post a comment confirming the dry-run and what would have happened.

---

## Security Notes

- Store your `admin-key` as a **GitHub Secret** — never hardcode it
- Use `dry-run: true` for initial setup
- The source wallet should have a limited balance — not your main holding wallet

---

## GitHub Marketplace

Published at: https://github.com/marketplace/actions/rtc-reward-action

Versioning: use `@v2` for the latest stable release, or pin to `@v2.x.x`.

---

## License

MIT — use freely in open source and commercial projects.
