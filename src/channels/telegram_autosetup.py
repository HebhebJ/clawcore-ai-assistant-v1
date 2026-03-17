import logging
import subprocess
import time

import httpx

from src.core.config import (
    TelegramAutoSetupSettings,
    TelegramSettings,
    load_telegram_auto_setup_settings,
    load_telegram_settings,
)

logger = logging.getLogger(__name__)


class TelegramAutoSetup:
    def __init__(
        self,
        telegram_settings: TelegramSettings | None = None,
        auto_settings: TelegramAutoSetupSettings | None = None,
    ) -> None:
        self.telegram_settings = telegram_settings or load_telegram_settings()
        self.auto_settings = auto_settings or load_telegram_auto_setup_settings()
        self._ngrok_process: subprocess.Popen | None = None
        self.public_base_url: str = ""

    def startup(self) -> dict:
        if not self.auto_settings.enabled:
            return {"enabled": False, "ran": False, "reason": "disabled"}
        if not self.telegram_settings.bot_token:
            return {"enabled": True, "ran": False, "reason": "missing_bot_token"}

        try:
            self.public_base_url = self._resolve_public_base_url().rstrip("/")
            if not self.public_base_url:
                return {"enabled": True, "ran": False, "reason": "missing_public_url"}
            self._set_webhook(self.public_base_url)
            return {"enabled": True, "ran": True, "public_base_url": self.public_base_url}
        except Exception as exc:  # noqa: BLE001
            logger.warning("telegram auto setup failed: %s", exc)
            return {"enabled": True, "ran": False, "reason": str(exc)}

    def shutdown(self) -> None:
        if self._ngrok_process and self._ngrok_process.poll() is None:
            self._ngrok_process.terminate()
            try:
                self._ngrok_process.wait(timeout=3)
            except Exception:  # noqa: BLE001
                self._ngrok_process.kill()
        self._ngrok_process = None

    def _resolve_public_base_url(self) -> str:
        if self.auto_settings.public_base_url:
            return self.auto_settings.public_base_url
        if not self.auto_settings.auto_ngrok:
            return ""
        self._start_ngrok()
        return self._wait_for_ngrok_url()

    def _start_ngrok(self) -> None:
        if self._ngrok_process and self._ngrok_process.poll() is None:
            return

        cmd = [
            self.auto_settings.ngrok_path,
            "http",
            str(self.auto_settings.local_port),
        ]
        if self.auto_settings.ngrok_authtoken:
            cmd += ["--authtoken", self.auto_settings.ngrok_authtoken]

        logger.info("starting ngrok for telegram webhook: %s", " ".join(cmd))
        self._ngrok_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _wait_for_ngrok_url(self) -> str:
        deadline = time.time() + self.auto_settings.startup_timeout_seconds
        last_error = ""
        while time.time() < deadline:
            try:
                with httpx.Client(timeout=2.0) as client:
                    response = client.get("http://127.0.0.1:4040/api/tunnels")
                    response.raise_for_status()
                    tunnels = response.json().get("tunnels", [])
                for tunnel in tunnels:
                    public_url = str(tunnel.get("public_url", "")).strip()
                    if public_url.startswith("https://"):
                        return public_url
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
            time.sleep(0.4)

        raise RuntimeError(f"ngrok did not provide an https tunnel in time: {last_error}")

    def _set_webhook(self, public_base_url: str) -> None:
        secret = self.telegram_settings.webhook_secret
        webhook_url = f"{public_base_url.rstrip('/')}/webhook/telegram"
        api_url = f"https://api.telegram.org/bot{self.telegram_settings.bot_token}/setWebhook"
        payload = {"url": webhook_url}
        if secret:
            payload["secret_token"] = secret
        with httpx.Client(timeout=self.telegram_settings.timeout_seconds) as client:
            response = client.post(api_url, data=payload)
            response.raise_for_status()
            data = response.json()
        if not bool(data.get("ok")):
            raise RuntimeError(f"telegram setWebhook failed: {data}")
        logger.info("telegram webhook configured url=%s", webhook_url)
