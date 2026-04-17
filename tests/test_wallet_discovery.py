"""Unit tests for wallet discovery logic."""
import pytest
import sys, os

# Patch env before import
os.environ["INPUT_NODE-URL"]     = "https://50.28.86.131"
os.environ["INPUT_AMOUNT"]      = "5"
os.environ["INPUT_WALLET-FROM"] = "test-sender"
os.environ["INPUT_ADMIN-KEY"]   = "test-key"
os.environ["INPUT_DRY-RUN"]     = "false"
os.environ["INPUT-GITHUB-TOKEN"] = ""
os.environ["INPUT-FALLBACK-WALLET"] = ""
os.environ["GITHUB_EVENT_PATH"]  = ""
os.environ["GITHUB_OUTPUT"]      = ""

# Import only the discovery helpers
import importlib.util, tempfile, pathlib

spec = importlib.util.spec_from_file_location(
    "reward", "/tmp/rtc-action/src/reward.py"
)
mod   = importlib.util.module_from_spec(spec)
# stub out the stdlib-heavy parts we don't need
sys.modules["urllib.error"]   = __import__("urllib.request")
sys.modules["urllib.parse"]   = __import__("urllib.request")
mod.ssl = __import__("ssl")
mod.ssl.create_default_context = lambda: None
mod.SSL_CTX = None

# Only load the pure functions
exec(open("/tmp/rtc-action/src/reward.py").read().split("def api_get")[0], mod.__dict__)

find_wallet_in_text = mod.find_wallet_in_text
find_wallet_in_file = mod.find_wallet_in_file

class TestFindWalletInText:
    """Test find_wallet_in_text() with various patterns."""

    def test_plain_wallet_name(self):
        assert find_wallet_in_text("rtc-wallet: alice_dev") == "alice_dev"
        assert find_wallet_in_text("wallet: bob-test")      == "bob-test"

    def test_wallet_in_sentence(self):
        assert find_wallet_in_text("Send to wallet: my-wallet") == "my-wallet"
        assert find_wallet_in_text("reward for you: rtc-user_1") == "rtc-user_1"

    def test_wallet_in_markdown_block(self):
        body = """
        ## PR Description
        rtc-wallet: contributor
        Some text here.
        """
        assert find_wallet_in_text(body) == "contributor"

    def test_hex_address(self):
        assert find_wallet_in_text("0x71C7656EC7ab88b098defB751B7401B5") == \
               "0x71C7656EC7ab88b098defB751B7401B5"

    def test_rtc_prefix_hex(self):
        assert find_wallet_in_text("RTC" + "a"*40) == "RTC" + "a"*40

    def test_no_wallet(self):
        assert find_wallet_in_text("This PR fixes a bug.") is None
        assert find_wallet_in_text("") is None
        assert find_wallet_in_text("short") is None  # too short


class TestFindWalletInFile:
    """Test find_wallet_in_file()."""

    def test_bare_wallet_name(self, tmp_path):
        f = tmp_path / ".rtc-wallet"
        f.write_text("alice_dev\n")
        assert find_wallet_in_file(str(tmp_path)) == "alice_dev"

    def test_kv_format(self, tmp_path):
        f = tmp_path / ".rtc-wallet"
        f.write_text("wallet=my-wallet-42\n")
        assert find_wallet_in_file(str(tmp_path)) == "my-wallet-42"

    def test_missing_file(self, tmp_path):
        assert find_wallet_in_file(str(tmp_path)) is None
