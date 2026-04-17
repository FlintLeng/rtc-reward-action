#!/usr/bin/env python3
"""
rtc-reward-action — reward.py
Automatically awards RTC tokens when a PR is merged.
Supports wallet discovery from: PR body → .rtc-wallet file → PR author → fallback input.

Bounty: https://github.com/Scottcjn/rustchain-bounties/issues/2864
"""
from __future__ import annotations

import json
import os
import re
import sys
import ssl
import urllib.error
import urllib.request
import urllib.parse

# ── Inputs ──────────────────────────────────────────────────────────────────
NODE_URL     = os.environ.get("INPUT_NODE-URL",     "https://50.28.86.131").rstrip("/")
AMOUNT       = int(os.environ.get("INPUT_AMOUNT",   "5"))
WALLET_FROM  = os.environ.get("INPUT_WALLET-FROM",   "")
ADMIN_KEY    = os.environ.get("INPUT_ADMIN-KEY",     "")
DRY_RUN      = os.environ.get("INPUT_DRY-RUN",       "false").lower() in ("true", "1", "yes")
GH_TOKEN     = os.environ.get("INPUT-GITHUB-TOKEN",  os.environ.get("GITHUB_TOKEN", ""))
FALLBACK_WAL = os.environ.get("INPUT-FALLBACK-WALLET", "")
MIN_BALANCE  = os.environ.get("INPUT-MIN-BALANCE",   "")
EVENT_PATH   = os.environ.get("GITHUB_EVENT_PATH",   "")

# ── SSL context for self-signed node cert ──────────────────────────────────
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode    = ssl.CERT_NONE

# ── Wallet patterns (regex) ───────────────────────────────────────────────────
WALLET_PATTERNS = [
    r"rtc[-_]wallet\s*[:=]\s*([A-Za-z0-9_-]{3,64})",
    r"wallet\s*[:=]\s*([A-Za-z0-9_-]{3,64})",
    r"(?:pay|reward|send).*?([A-Za-z0-9_-]{3,64})",
    r"0x[a-fA-F0-9]{40}",    # raw hex address
    r"RTC[a-f0-9]{40,}",      # RTC prefix + hex
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(f"[rtc-reward] {msg}", flush=True)


def set_output(name: str, value: str) -> None:
    """Write GitHub Actions output. Uses GITHUB_OUTPUT env var (GHA v3+)."""
    path = os.environ.get("GITHUB_OUTPUT", "")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"::set-output name={name}::{value}", flush=True)


def die(msg: str) -> None:
    print(f"::error::{msg}", flush=True)
    sys.exit(1)


def api_get(path: str, params: dict | None = None) -> dict | None:
    """GET request to RustChain node."""
    url = f"{NODE_URL}/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        log(f"GET {url} → HTTP {e.code}: {body[:200]}")
        return None
    except Exception as e:
        log(f"GET {url} → {e}")
        return None


def api_post(path: str, payload: dict) -> dict | None:
    """POST request to RustChain node."""
    url  = f"{NODE_URL}/{path.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ADMIN_KEY}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        log(f"POST {url} → HTTP {e.code}: {body[:200]}")
        return None
    except Exception as e:
        log(f"POST {url} → {e}")
        return None


def gh_post(url: str, payload: dict) -> dict | None:
    """POST to GitHub API."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"token {GH_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/vnd.github.v3+json",
            "User-Agent": "FlintLeng/rtc-reward-action",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        log(f"GH POST {url} → HTTP {e.code}: {body[:200]}")
        return None
    except Exception as e:
        log(f"GH POST {url} → {e}")
        return None


# ── Wallet discovery ─────────────────────────────────────────────────────────

def find_wallet_in_text(text: str) -> str | None:
    """Extract first wallet address/name from free text."""
    if not text:
        return None
    for pattern in WALLET_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def find_wallet_in_file(repo_path: str = ".") -> str | None:
    """Read .rtc-wallet file from repo root."""
    wallet_file = os.path.join(repo_path, ".rtc-wallet")
    if not os.path.isfile(wallet_file):
        return None
    try:
        with open(wallet_file, encoding="utf-8") as f:
            content = f.read().strip()
        # Try bare wallet name
        if re.match(r"^[A-Za-z0-9_-]{3,64}$", content):
            return content
        # Try extracting from file content
        return find_wallet_in_text(content)
    except Exception as e:
        log(f"Could not read .rtc-wallet: {e}")
        return None


def discover_wallet(pr_body: str, pr_author: str, pr_number: str,
                    repo_owner: str, repo_name: str) -> str | None:
    """
    Wallet discovery priority:
    1. PR body text
    2. .rtc-wallet file (fetched via GitHub API if not in checkout)
    3. PR author GitHub username (used as wallet name)
    4. fallback-wallet input
    """
    # 1. PR body
    w = find_wallet_in_text(pr_body or "")
    if w:
        log(f"Wallet found in PR body: {w}")
        return w

    # 2. .rtc-wallet file via GitHub API
    if GH_TOKEN:
        url = (f"https://api.github.com/repos/{repo_owner}/{repo_name}"
               f"/contents/.rtc-wallet?ref=refs/heads/main")
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"token {GH_TOKEN}",
                "Accept": "application/vnd.github.v3.raw",
                "User-Agent": "FlintLeng/rtc-reward-action",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8").strip()
                w = find_wallet_in_text(content)
                if w:
                    log(f"Wallet found in .rtc-wallet file: {w}")
                    return w
        except urllib.error.HTTPError:
            pass
        except Exception as e:
            log(f".rtc-wallet fetch failed: {e}")

    # 3. PR author as wallet name
    if pr_author:
        log(f"Using PR author as wallet: {pr_author}")
        return pr_author

    # 4. Fallback
    if FALLBACK_WAL:
        log(f"Using fallback wallet: {FALLBACK_WAL}")
        return FALLBACK_WAL

    return None


# ── Balance check ─────────────────────────────────────────────────────────────

def check_balance(wallet: str) -> float | None:
    """Check wallet balance via RustChain node."""
    resp = api_get("/wallet/balance", {"wallet": wallet})
    if resp and "balance" in resp:
        try:
            return float(resp["balance"])
        except (ValueError, TypeError):
            pass
    # Try alternative endpoint
    resp2 = api_get(f"/wallet/{urllib.parse.quote(wallet)}/balance")
    if resp2 and "balance" in resp2:
        try:
            return float(resp2["balance"])
        except (ValueError, TypeError):
            pass
    return None


# ── Send RTC ─────────────────────────────────────────────────────────────────

def send_rtc(from_wallet: str, to_wallet: str, amount: int, admin_key: str) -> dict | None:
    """
    Send RTC via RustChain node.
    Node: https://50.28.86.131
    Uses /wallet/send endpoint with admin_key auth.
    """
    payload = {
        "from":      from_wallet,
        "to":        to_wallet,
        "amount":    amount,
        "admin_key": admin_key,
    }
    return api_post("/wallet/send", payload)


# ── Post PR comment ──────────────────────────────────────────────────────────

def post_pr_comment(repo_owner: str, repo_name: str, pr_number: int,
                    body: str) -> None:
    """Post a comment on the merged PR."""
    url = (f"https://api.github.com/repos/{repo_owner}/{repo_name}"
           f"/issues/{pr_number}/comments")
    gh_post(url, {"body": body})


# ── Build comment body ───────────────────────────────────────────────────────

def build_comment(wallet_to: str, amount: int, tx_id: str | None,
                  dry_run: bool, pr_title: str, pr_number: int,
                  repo_owner: str, repo_name: str) -> str:
    pr_url = f"https://github.com/{repo_owner}/{repo_name}/pull/{pr_number}"
    status  = "🎉 **DRY-RUN** (no RTC sent)" if dry_run else "✅ **Sent!**"
    tx_line = f"**TX ID:** `{tx_id}`" if tx_id else "**TX ID:** _pending_"

    return f"""## 🎉 PR Merged — RTC Reward {status}

**PR #{pr_number}:** [{pr_title}]({pr_url})
**Recipient:** `@{wallet_to}`
**Amount:** **{amount} RTC**
**TX ID:** `{tx_id or "N/A (dry-run)"}`

---

_Powered by [rtc-reward-action](https://github.com/FlintLeng/rtc-reward-action) · [Source](https://github.com/FlintLeng/rtc-reward-action)_
"""


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    log("=" * 60)
    log("rtc-reward-action v2 — starting")
    log(f"  Node URL : {NODE_URL}")
    log(f"  Amount    : {AMOUNT} RTC")
    log(f"  Sender    : {WALLET_FROM}")
    log(f"  Dry-run   : {DRY_RUN}")
    log("=" * 60)

    # ── Validate inputs ────────────────────────────────────────────────────
    if not WALLET_FROM:
        die("wallet-from is required — no sender wallet specified")
    if not ADMIN_KEY and not DRY_RUN:
        die("admin-key is required for live mode — use a secret!")

    # ── Load GitHub event ──────────────────────────────────────────────────
    if not EVENT_PATH or not os.path.isfile(EVENT_PATH):
        die("GITHUB_EVENT_PATH not set or file not found")

    with open(EVENT_PATH, encoding="utf-8") as f:
        event = json.load(f)

    pr = event.get("pull_request", {})
    if not pr:
        die("No pull_request in event payload")

    if not pr.get("merged"):
        log("PR not merged — skipping")
        return

    pr_title   = pr.get("title", "unknown")
    pr_number  = pr.get("number", "?")
    pr_body    = pr.get("body", "") or ""
    pr_author  = pr.get("user", {}).get("login", "") or ""
    repo_owner, repo_name = os.environ.get("GITHUB_REPOSITORY", "/").split("/", 1)

    log(f"Merged PR #{pr_number} by @{pr_author}: {pr_title[:60]}")

    # ── Discover wallet ────────────────────────────────────────────────────
    wallet_to = discover_wallet(pr_body, pr_author, str(pr_number), repo_owner, repo_name)
    if not wallet_to:
        die(f"No wallet found for PR #{pr_number} — add a wallet to the PR body or create a .rtc-wallet file")

    # ── Output recipient wallet ────────────────────────────────────────────
    set_output("recipient_wallet", wallet_to)
    set_output("amount_sent",     str(AMOUNT))
    set_output("tx_id",           "")

    # ── Balance check ─────────────────────────────────────────────────────
    if not DRY_RUN:
        bal = check_balance(WALLET_FROM)
        if bal is not None:
            threshold = float(MIN_BALANCE) if MIN_BALANCE else (AMOUNT + 1)
            if bal < threshold:
                die(f"Insufficient balance in {WALLET_FROM}: {bal} < {threshold} RTC required")

    # ── Send RTC ───────────────────────────────────────────────────────────
    tx_id = ""
    if DRY_RUN:
        log(f"[DRY-RUN] Would send {AMOUNT} RTC from {WALLET_FROM} → {wallet_to}")
        status_text = "dry-run (no RTC sent)"
    else:
        result = send_rtc(WALLET_FROM, wallet_to, AMOUNT, ADMIN_KEY)
        if result:
            tx_id = result.get("tx_id") or result.get("id") or result.get("hash") or "ok"
            log(f"TX sent: {tx_id}")
            set_output("tx_id", tx_id)
            status_text = f"sent (TX: {tx_id})"
        else:
            die(f"Failed to send RTC to {wallet_to} — check admin_key and balance")

    # ── Post PR comment ─────────────────────────────────────────────────────
    comment = build_comment(wallet_to, AMOUNT, tx_id, DRY_RUN,
                            pr_title, pr_number, repo_owner, repo_name)
    try:
        post_pr_comment(repo_owner, repo_name, pr_number, comment)
        log("PR comment posted ✅")
    except Exception as e:
        log(f"PR comment failed (non-fatal): {e}")

    log(f"Done — {AMOUNT} RTC {status_text} to {wallet_to}")


if __name__ == "__main__":
    main()
