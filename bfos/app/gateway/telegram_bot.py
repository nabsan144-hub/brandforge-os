"""Optional Telegram control of an already-running, loopback Desktop instance.

Authorization is a chat allowlist plus the Desktop's local write capability.
Polling uses the asynchronous Application lifecycle, never run_polling inside
asyncio.run. No Cloud credentials or provider keys are sent to Telegram.
"""
import asyncio
import html
import ipaddress
import os
from urllib.parse import urlsplit

from modules.security import safe_text


class BrandForgeTelegramBot:
    def __init__(self, token: str, api_base: str = "http://127.0.0.1:8000"):
        if not token or len(token) < 20:
            raise ValueError("Invalid Telegram token")
        address = urlsplit(api_base)
        try:
            local = address.hostname == "localhost" or ipaddress.ip_address(address.hostname).is_loopback
        except ValueError:
            local = False
        if address.scheme not in ("http", "https") or not local or address.username or address.password or address.query or address.fragment or address.path not in ("", "/"):
            raise ValueError("Telegram must connect to a loopback Desktop URL, not a public Cloud endpoint")
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.allowed_chat_ids = {x.strip() for x in os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if x.strip()}

    def _allowed(self, update):
        message = getattr(update, "effective_message", None) or getattr(update, "message", None)
        return str(getattr(message, "chat_id", "")) in self.allowed_chat_ids

    def _guard(self, handler):
        async def guarded(update, context):
            message = getattr(update, "effective_message", None) or getattr(update, "message", None)
            if not self._allowed(update):
                if message is not None:
                    await message.reply_text("Not an authorized chat. Configure the allowlist on your own Desktop instance.")
                return
            await handler(update, context)
        return guarded

    async def _request(self, method, route, payload=None):
        import httpx
        async with httpx.AsyncClient(timeout=120, follow_redirects=False, trust_env=False) as client:
            headers = {}
            if method != "GET":
                session = await client.get(self.api_base + "/api/session")
                session.raise_for_status()
                capability = session.json().get("capability")
                if not isinstance(capability, str) or len(capability) < 40:
                    raise RuntimeError("The local app did not provide a write capability")
                headers["X-BrandForge-Token"] = capability
            response = await client.request(method, self.api_base + route, json=payload, headers=headers)
            if not response.is_success:
                raise RuntimeError(f"The local app could not complete this request (HTTP {response.status_code})")
            return response.json()

    def build_application(self):
        from telegram.ext import Application, CommandHandler, MessageHandler, filters
        app = Application.builder().token(self.token).build()
        guard = self._guard

        @guard
        async def help_command(update, context):
            await update.message.reply_text(
                "BrandForge OS Desktop\n/status — app status\n/campaigns — saved campaigns\n"
                "/campaign Product | Industry | Audience | Benefits\n/chat message — chat with your selected engine\n"
                "Ordinary messages also start a chat. Connected providers may have their own costs."
            )

        @guard
        async def status_command(update, context):
            try:
                data = await self._request("GET", "/health")
                await update.message.reply_text(f"Provider: {data.get('provider')}\nCampaigns: {data.get('campaigns')}\nTools: {data.get('tools_count')}")
            except Exception:
                await update.message.reply_text("Cannot reach the local app. Start BrandForge Desktop and check the configured local port.")

        @guard
        async def campaigns_command(update, context):
            try:
                data = await self._request("GET", "/api/campaigns")
                rows = data.get("campaigns", [])[:10]
                text = "Saved campaigns:\n" + "\n".join("• " + str(row.get("name", ""))[:100] for row in rows)
                await update.message.reply_text(text if rows else "No saved campaigns yet.")
            except Exception:
                await update.message.reply_text("Could not load campaigns from the local app.")

        @guard
        async def campaign_command(update, context):
            parts = [safe_text(part.strip(), 500) for part in " ".join(context.args or []).split("|", 3)]
            if len(parts) != 4 or any(not part for part in parts):
                await update.message.reply_text("Use: /campaign Product | Industry | Audience | Benefits")
                return
            product, industry, audience, benefits = parts
            if len(product) > 80 or len(industry) > 80 or len(audience) > 120:
                await update.message.reply_text("Keep product/industry within 80 characters and audience within 120.")
                return
            await update.message.reply_text("Creating a reviewable campaign draft. Generation time depends on your selected engine.")
            try:
                data = await self._request("POST", "/api/swarm/run", {"campaign_name": safe_text(product + " Launch", 80), "product_name": product, "industry": industry, "target_audience": audience, "key_benefits": benefits})
                await update.message.reply_text("<b>Draft saved:</b> " + html.escape(str(data.get("campaign_name", product))) + "\nOpen Desktop to review and export it.", parse_mode="HTML")
            except Exception:
                await update.message.reply_text("The local app did not confirm completion. Check Desktop history before retrying.")

        async def reply_to_chat(update, text):
            message = safe_text(text, 2000)
            if not message:
                await update.message.reply_text("Please enter a message.")
                return
            try:
                data = await self._request("POST", "/api/chat", {"message": message})
                await update.message.reply_text(str(data.get("brandforge_response") or "No response was returned.")[:4000])
            except Exception:
                await update.message.reply_text("The local app could not complete this chat. Check Desktop and the selected provider.")

        @guard
        async def chat_command(update, context):
            await reply_to_chat(update, " ".join(context.args or []))

        @guard
        async def message_handler(update, context):
            await reply_to_chat(update, update.message.text or "")

        for name, handler in [("start", help_command), ("help", help_command), ("status", status_command), ("campaigns", campaigns_command), ("campaign", campaign_command), ("chat", chat_command)]:
            app.add_handler(CommandHandler(name, handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        return app

    async def start(self, stop_event=None):
        if not self.allowed_chat_ids:
            raise RuntimeError("Set TELEGRAM_ALLOWED_CHAT_IDS before starting the gateway")
        app = self.build_application()
        stop_event = stop_event or asyncio.Event()
        async with app:
            await app.start()
            try:
                await app.updater.start_polling()
                await stop_event.wait()
            finally:
                if app.updater.running:
                    await app.updater.stop()
                await app.stop()


if __name__ == "__main__":
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_ALLOWED_CHAT_IDS in the local environment.")
    try:
        asyncio.run(BrandForgeTelegramBot(token).start())
    except KeyboardInterrupt:
        pass
