from telegram import Update
from telegram.ext import ContextTypes
from src.database.db import save_message, get_conversation_history
from src.services.groq_service import get_groq_response

SYSTEM_PROMPT = """Tu es un assistant personnel spécialisé dans la gestion d'un PEA (Plan d'Épargne en Actions) Boursorama.
Tu aides l'utilisateur à :
- Décider quand et quoi acheter selon son budget et ses préférences sectorielles
- Suivre son portefeuille (valorisation, plus-value)
- Comprendre le risque d'un ETF ou d'une action
- Enregistrer ses transactions

Tu es direct, pédagogue, tu tutoies l'utilisateur et tu rappelles quand c'est pertinent que tes suggestions ne sont pas des conseils financiers certifiés.
Tu parles en français, de manière naturelle et concise."""


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return

    chat_id = str(update.effective_chat.id)
    user_message = update.message.text

    if not user_message:
        return

    save_message(chat_id, "user", user_message)
    history = get_conversation_history(chat_id, limit=10)
    response = await get_groq_response(history, SYSTEM_PROMPT)
    save_message(chat_id, "assistant", response)

    await update.message.reply_text(response)