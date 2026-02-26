"""Entrypoint for the Telegram subscription gate bot."""

from __future__ import annotations

import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot.config import Config, load_config
from bot.handlers import setup_handlers


def build_app(config: Config) -> web.Application:
    """Create aiohttp app and bind aiogram webhook handlers."""
    bot = Bot(token=config.bot_token)
    dispatcher = Dispatcher()
    setup_handlers(dispatcher, config.required_chats)

    webhook_path = f"/webhook/{config.webhook_secret}"
    webhook_url = f"{config.webhook_base_url}{webhook_path}"

    async def on_startup() -> None:
        await bot.set_webhook(
            webhook_url,
            allowed_updates=dispatcher.resolve_used_update_types(),
            drop_pending_updates=False,
        )
        logging.info("Webhook set to %s", webhook_url)

    async def on_shutdown() -> None:
        await bot.delete_webhook(drop_pending_updates=False)
        logging.info("Webhook deleted")

    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)

    app = web.Application()

    async def healthcheck(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app.router.add_get("/health", healthcheck)

    request_handler = SimpleRequestHandler(dispatcher=dispatcher, bot=bot)
    request_handler.register(app, path=webhook_path)
    setup_application(app, dispatcher, bot=bot)
    return app


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config()
    app = build_app(config)
    web.run_app(app, host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    main()
