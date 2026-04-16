#!/usr/bin/env python3
"""
RTC Reward Action — Awards RTC tokens for merged pull requests
Bounty: https://github.com/Scottcjn/rustchain-bounties/issues/2864
"""
import os, sys, json, re, urllib.request, urllib.error, urllib.parse

# ── Inputs ──────────────────────────────────────────────────────────────────
NODE_URL    = os.environ.get('INPUT_NODE-URL',    'https://50.28.86.131')
AMOUNT      = int(os.environ.get('INPUT_AMOUNT',  '5'))
WALLET_FROM = os.environ.get('INPUT_WALLET-FROM', '')
ADMIN_KEY   = os.environ.get('INPUT_ADMIN-KEY',    '')
DRY_RUN     = os.environ.get('INPUT_DRY-RUN',     'false').lower() == 'true'
GITHUB_TOKEN= os.environ.get('INPUT_GITHUB-TOKEN', os.environ.get('GITHUB_TOKEN', ''))
PAYLOAD_PATH= os.environ.get('GITHUB_EVENT_PATH',  '')

def log(msg):  print(f"[rtc-reward] {msg}")
def die(msg):  print(f"::error::{msg}", file=sys.stderr); sys.exit(1)

def api_post(endpoint, payload):
    url = f"{NODE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {ADMIN_KEY}'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e:
        die(f"API error {e.code}: {e.read().decode()}")

def extract_wallet(body):
    m = re.search(r'RTC[0-9a-f]{40,}', body, re.IGNORECASE)
    if m: return m.group(0)
    m = re.search(r'(?:wallet|address|rtc)[:\s]+([A-Za-z0-9_-]{3,32})', body, re.IGNORECASE)
    return m.group(1) if m else None

def get_balance(wallet):
    try:
        url = f"{NODE_URL.rstrip('/')}/wallet/balance?wallet={urllib.parse.quote(wallet)}"
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {ADMIN_KEY}'})
        with urllib.request.urlopen(req, timeout=10) as r: return json.loads(r.read()).get('balance', 0)
    except: return None

def post_comment(issue_url, body):
    data = json.dumps({'body': body}).encode()
    req = urllib.request.Request(
        issue_url + '/comments', data=data,
        headers={
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/vnd.github.v3+json',
        }, method='POST'
    )
    with urllib.request.urlopen(req, timeout=10) as r: return json.loads(r.read())

def main():
    log(f"Node={NODE_URL} Amount={AMOUNT} WALLET={WALLET_FROM} DryRun={DRY_RUN}")
    if not WALLET_FROM: die("wallet-from is required")
    if not ADMIN_KEY and not DRY_RUN: die("admin-key is required")
    if not PAYLOAD_PATH or not os.path.exists(PAYLOAD_PATH): die("GITHUB_EVENT_PATH not set")

    with open(PAYLOAD_PATH) as f: event = json.load(f)
    pr = event.get('pull_request', {})
    if pr.get('merged') is not True: log("Not merged — skip"); return

    wallet_to = extract_wallet(pr.get('body', '') or '')
    if not wallet_to: log("No wallet in PR — skip"); return
    log(f"Contributor wallet: {wallet_to}")

    status = "[DRY-RUN] Would send" if DRY_RUN else api_post('/wallet/send', {
        'from': WALLET_FROM, 'to': wallet_to, 'amount': AMOUNT, 'admin_key': ADMIN_KEY
    }) and "TX sent" or "TX failed"

    comment = f"## 🎉 PR Merged — RTC Reward\n\n**Recipient:** `{wallet_to}`  \n**Amount:** {AMOUNT} RTC  \n**Status:** ✅ {status}\n\n_Powered by [rtc-reward-action](https://github.com/FlintLeng/rtc-reward-action)_"
    try:
        issue_url = f"https://api.github.com/repos/{os.environ.get('GITHUB_REPOSITORY','')}/issues/{pr['number']}"
        post_comment(issue_url, comment); log("Comment posted ✅")
    except Exception as e: log(f"Comment failed: {e}")
    log("=== Done ===")

if __name__ == '__main__': main()
