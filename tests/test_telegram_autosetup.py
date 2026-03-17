import unittest
from unittest.mock import patch

from src.channels.telegram_autosetup import TelegramAutoSetup
from src.core.config import TelegramAutoSetupSettings, TelegramSettings


class TelegramAutoSetupTests(unittest.TestCase):
    def test_disabled_auto_setup_does_nothing(self):
        setup = TelegramAutoSetup(
            telegram_settings=TelegramSettings(bot_token="token"),
            auto_settings=TelegramAutoSetupSettings(enabled=False),
        )
        info = setup.startup()
        self.assertFalse(info["ran"])
        self.assertEqual(info["reason"], "disabled")

    def test_enabled_requires_bot_token(self):
        setup = TelegramAutoSetup(
            telegram_settings=TelegramSettings(bot_token=""),
            auto_settings=TelegramAutoSetupSettings(enabled=True, public_base_url="https://x.example"),
        )
        info = setup.startup()
        self.assertFalse(info["ran"])
        self.assertEqual(info["reason"], "missing_bot_token")

    def test_enabled_with_public_url_sets_webhook(self):
        setup = TelegramAutoSetup(
            telegram_settings=TelegramSettings(bot_token="token", webhook_secret="sec"),
            auto_settings=TelegramAutoSetupSettings(enabled=True, public_base_url="https://x.example"),
        )
        calls: list[str] = []

        def _capture_set(url: str) -> None:
            calls.append(url)

        with patch.object(setup, "_set_webhook", side_effect=_capture_set):
            info = setup.startup()

        self.assertTrue(info["ran"])
        self.assertEqual(info["public_base_url"], "https://x.example")
        self.assertEqual(calls, ["https://x.example"])


if __name__ == "__main__":
    unittest.main()

