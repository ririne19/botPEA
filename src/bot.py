import logging

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config import TELEGRAM_BOT_TOKEN
from src.database.db import init_db
from src.handlers.conversation import handle_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        "👋 Bonjour ! Je suis ton assistant PEA personnel.\n\n"
        "Tu peux me dire des choses comme :\n"
        "• « Je veux investir »\n"
        "• « Parle-moi du risque de ASML »\n"
        "• « J'ai acheté 2 parts de LTUG à 120€ »\n"
        "• « Montre-moi mon portefeuille »\n\n"
        "Je suis là pour t'accompagner dans tes décisions d'investissement 📈"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Erreur : %s", context.error)


def main() -> None:
    init_db()

    assert TELEGRAM_BOT_TOKEN is not None, "TELEGRAM_BOT_TOKEN manquant dans .env"

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("🤖 Bot démarré en mode polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()