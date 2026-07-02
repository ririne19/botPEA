import json
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from src.database.db import (
    get_conversation_history,
    get_watchlist,
    save_message,
    update_watchlist,
)
from src.services.finnhub_service import (
    format_quote_message,
    get_multiple_quotes,
    get_quote,
)
from src.services.groq_service import get_groq_response
from src.services.notion_service import (
    add_transaction,
    format_portfolio_with_prices,
    get_portfolio,
)

# Prompt système principal
SYSTEM_PROMPT = """Tu es un assistant personnel spécialisé dans la gestion d'un PEA (Plan d'Épargne en Actions) Boursorama.
Tu aides l'utilisateur à décider quand et quoi acheter, suivre son portefeuille, comprendre les risques.
Tu es direct, tu tutoies l'utilisateur, tu parles en français de manière naturelle et concise.

RÈGLES ABSOLUES :
- Ne donne JAMAIS de cours boursiers de ta propre initiative — tu n'as pas accès aux cours en temps réel
- Si on te demande un cours, dis que tu vas le vérifier et utilise l'outil approprié
- Pour les calculs d'achat (combien de parts), utilise UNIQUEMENT les cours fournis dans le contexte de la conversation
- Rappelle quand c'est pertinent que tes suggestions ne sont pas des conseils financiers certifiés"""

# Prompt de classification d'intention
INTENT_PROMPT = """Analyse ce message et retourne UNIQUEMENT un JSON valide avec la structure suivante, sans texte autour :
{
  "intent": "string",
  "data": {}
}

Les intents possibles sont :
- "investir" : l'utilisateur veut investir une somme (ex: "je veux investir", "j'ai 50€ à placer")
- "achat" : l'utilisateur déclare un achat effectué (ex: "j'ai acheté 2 ASML à 650€")
- "portefeuille" : l'utilisateur veut voir son portefeuille (ex: "montre mon portefeuille", "mes positions")
- "cours" : l'utilisateur veut le cours d'un titre (ex: "cours de ASML", "prix de AAPL")
- "risque" : l'utilisateur veut analyser le risque d'un titre (ex: "risque de LTUG", "est-ce stable ?")
- "watchlist_ajout" : l'utilisateur veut ajouter un ticker à sa watchlist (ex: "ajoute ASML", "suis AAPL")
- "watchlist_retrait" : l'utilisateur veut retirer un ticker (ex: "retire ASML de ma watchlist")
- "conversation" : tout autre message (questions générales, salutations, etc.)
- "cours" : l'utilisateur veut le cours actuel d'un titre ET mentionne explicitement un ticker connu (ex: "cours de ASML", "prix de AAPL"). NE PAS utiliser si la question porte sur une évolution historique ou une analyse.
- "confirmation_watchlist" : l'utilisateur répond oui/non à une proposition d'ajout watchlist (ex: "oui", "non", "ok vas-y", "non merci")
  Dans "data" : {"reponse": "oui" ou "non"}
- "suggestion_secteur" : l'utilisateur demande des suggestions dans un secteur spécifique OU mentionne un secteur avec un budget (ex: "50€ dans la tech", "propose des actions santé", "ETF médicaux avec 100€")
  PRIORITAIRE sur "investir" quand un secteur est explicitement mentionné
  Dans "data" : {"secteur": "...", "budget": 50}
Pour "achat", extrais dans "data" : {"ticker": "...", "quantite": 0, "prix_unitaire": 0, "date": "YYYY-MM-DD"}
Pour "cours" et "risque", extrais dans "data" : {"ticker": "..."}
Pour "watchlist_ajout" et "watchlist_retrait", extrais dans "data" : {"ticker": "..."}
Pour "investir", extrais dans "data" : {"montant": 0} si un montant est mentionné, sinon {}

Message à analyser : """


async def detect_intent(message: str) -> dict[str, object]:
    """
    Utilise Groq pour classifier l'intention du message.

    Returns:
        dict avec "intent" (str) et "data" (dict)
    """
    response = await get_groq_response(
        history=[{"role": "user", "content": INTENT_PROMPT + message}],
        system_prompt="Tu es un classificateur d'intentions. Tu retournes UNIQUEMENT du JSON valide, rien d'autre.",
        model="llama-3.3-70b-versatile",
    )

    try:
        # Nettoie la réponse au cas où le modèle ajouterait des backticks
        cleaned = response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return dict(json.loads(cleaned))
    except json.JSONDecodeError:
        return {"intent": "conversation", "data": {}}


async def handle_investir(
    update: Update,
    chat_id: str,
    data: dict[str, object],
) -> None:
    """Gère l'intention 'investir' : propose des achats selon le budget."""
    montant = data.get("montant")

    if not montant:
        await update.message.reply_text(  # type: ignore[union-attr]
            "💰 Ok, combien tu veux investir ?"
        )
        return

    try:
        montant_float = float(str(montant)) if montant is not None else 0.0
    except ValueError:
        await update.message.reply_text("💰 Ok, combien tu veux investir exactement ?")  # type: ignore[union-attr]
        return
    watchlist = get_watchlist(chat_id)
    if not watchlist:
        watchlist = ["LTUG", "AAPL", "MSFT", "ASML", "PFE", "GSK", "SAN"]

    await update.message.reply_text("⏳ Je consulte les cours en temps réel...")  # type: ignore[union-attr]

    # Récupère les vrais cours via Finnhub
    quotes = await get_multiple_quotes(watchlist)

    # Filtre les titres accessibles avec le budget
    accessibles = [
        q for q in quotes
        if "prix_actuel" in q and float(str(q["prix_actuel"])) <= montant_float
    ]
    trop_chers = [
        q for q in quotes
        if "prix_actuel" in q and float(str(q["prix_actuel"])) > montant_float
    ]

    # Formate les cours réels pour Groq
    accessibles_text = "\n".join([
        f"- {q.get('ticker')}: {q.get('prix_actuel')}€ (variation: {q.get('variation_pct')}%)"
        for q in accessibles
    ]) or "Aucun titre accessible avec ce budget"

    trop_chers_text = "\n".join([
        f"- {q.get('ticker')}: {q.get('prix_actuel')}€"
        for q in trop_chers
    ])

    suggestion_prompt = f"""L'utilisateur veut investir {montant_float}€ dans son PEA.

COURS EN TEMPS RÉEL (source Finnhub, fiables) :
Titres accessibles avec {montant_float}€ :
{accessibles_text}

Titres trop chers pour ce budget :
{trop_chers_text}

IMPORTANT :
- Utilise UNIQUEMENT les cours ci-dessus, ne les invente pas
- Ne propose que les titres de la liste "accessibles"
- Calcule exactement combien de parts on peut acheter
- Si aucun titre n'est accessible, dis-le et conseille d'attendre ou d'augmenter le budget
- Ne mentionne jamais de cours que tu n'as pas dans cette liste
- Rappelle brièvement que ce ne sont pas des conseils certifiés
- Boursorama PEA ne permet PAS les fractions de parts, propose uniquement des nombres entiers
- Calcule floor(budget / prix) pour le nombre de parts achetables
"""

    history = get_conversation_history(chat_id, limit=5)
    response = await get_groq_response(
        history=history + [{"role": "user", "content": suggestion_prompt}],
        system_prompt=SYSTEM_PROMPT,
    )

    save_message(chat_id, "assistant", response)
    await update.message.reply_text(response)  # type: ignore[union-attr]


async def handle_achat(
    update: Update,
    chat_id: str,
    data: dict[str, object],
) -> None:
    """Gère l'intention 'achat' : enregistre la transaction dans Notion."""
    ticker = str(data.get("ticker", ""))
    quantite = float(str(data.get("quantite", 0)))
    prix_unitaire = float(str(data.get("prix_unitaire", 0)))
    date = str(data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")))

    if not ticker or quantite == 0 or prix_unitaire == 0:
        await update.message.reply_text(  # type: ignore[union-attr]
            "❓ Je n'ai pas bien compris les détails de ton achat.\n"
            "Dis-moi par exemple : *j'ai acheté 2 ASML à 650€*"
        )
        return

    try:
        await add_transaction(
            ticker=ticker.upper(),
            transaction_type="Achat",
            date=date,
            quantity=quantite,
            prix_unitaire=prix_unitaire,
        )
        montant_total = round(quantite * prix_unitaire, 2)
        await update.message.reply_text(  # type: ignore[union-attr]
            f"✅ Transaction enregistrée dans Notion !\n\n"
            f"📈 **{ticker.upper()}** — {quantite} part(s) à {prix_unitaire}€\n"
            f"💰 Montant total : {montant_total}€"
        )
    except Exception as e:
        await update.message.reply_text(  # type: ignore[union-attr]
            f"❌ Erreur lors de l'enregistrement : {str(e)}"
        )


async def handle_portefeuille(update: Update, chat_id: str) -> None:
    """Gère l'intention 'portefeuille' : affiche les positions avec valorisation."""
    await update.message.reply_text("⏳ Je récupère ton portefeuille...")  # type: ignore[union-attr]

    positions = await get_portfolio()

    if not positions:
        await update.message.reply_text(  # type: ignore[union-attr]
            "📭 Ton portefeuille est vide pour l'instant.\n"
            "Dis-moi quand tu fais un achat et je l'enregistrerai !"
        )
        return

    # Récupère les cours actuels pour chaque position
    tickers = [pos["ticker"] for pos in positions]
    quotes = await get_multiple_quotes(tickers)

    message = format_portfolio_with_prices(positions, quotes)
    await update.message.reply_text(message)  # type: ignore[union-attr]


async def handle_cours(
    update: Update,
    chat_id: str,
    data: dict[str, object],
) -> None:
    """Gère l'intention 'cours' : affiche le prix actuel d'un titre."""
    ticker = str(data.get("ticker", ""))
    if not ticker:
        await update.message.reply_text("❓ Quel ticker tu veux consulter ?")  # type: ignore[union-attr]
        return

    quote = await get_quote(ticker.upper())
    await update.message.reply_text(format_quote_message(quote))  # type: ignore[union-attr]


async def handle_watchlist(
    update: Update,
    chat_id: str,
    intent: str,
    data: dict[str, object],
) -> None:
    """Gère l'ajout/retrait d'un ticker dans la watchlist."""
    ticker = str(data.get("ticker", "")).upper()
    if not ticker:
        await update.message.reply_text("❓ Quel ticker tu veux modifier ?")  # type: ignore[union-attr]
        return

    watchlist = get_watchlist(chat_id)

    if intent == "watchlist_ajout":
        if ticker not in watchlist:
            watchlist.append(ticker)
            update_watchlist(chat_id, watchlist)
            await update.message.reply_text(f"✅ **{ticker}** ajouté à ta watchlist !")  # type: ignore[union-attr]
        else:
            await update.message.reply_text(f"**{ticker}** est déjà dans ta watchlist.")  # type: ignore[union-attr]
    else:
        if ticker in watchlist:
            watchlist.remove(ticker)
            update_watchlist(chat_id, watchlist)
            await update.message.reply_text(f"✅ **{ticker}** retiré de ta watchlist.")  # type: ignore[union-attr]
        else:
            await update.message.reply_text(f"**{ticker}** n'est pas dans ta watchlist.")  # type: ignore[union-attr]


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None or update.effective_chat is None:
        return

    chat_id = str(update.effective_chat.id)
    user_message = update.message.text

    if not user_message:
        return

    try:
        save_message(chat_id, "user", user_message)
        intent_result = await detect_intent(user_message)
        intent = str(intent_result.get("intent", "conversation"))
        raw_data = intent_result.get("data", {})
        data: dict[str, object] = dict(raw_data) if isinstance(raw_data, dict) else {}  # type: ignore[assignment, arg-type]

        if intent == "investir":
            await handle_investir(update, chat_id, data)
        elif intent == "achat":
            await handle_achat(update, chat_id, data)
        elif intent == "portefeuille":
            await handle_portefeuille(update, chat_id)
        elif intent == "cours":
            await handle_cours(update, chat_id, data)
        elif intent in ("watchlist_ajout", "watchlist_retrait"):
            await handle_watchlist(update, chat_id, intent, data)
        elif intent == "suggestion_secteur":
            await handle_suggestion_secteur(update, chat_id, data)
        elif intent == "confirmation_watchlist":
            await handle_confirmation_watchlist(update, chat_id, data)
        else:
            history = get_conversation_history(chat_id, limit=10)
            response = await get_groq_response(history, SYSTEM_PROMPT)
            save_message(chat_id, "assistant", response)
            await update.message.reply_text(response)  # type: ignore[union-attr]

    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Erreur dans handle_message : %s", str(e))
        await update.message.reply_text(  # type: ignore[union-attr]
            "❌ Oups, une erreur s'est produite. Peux-tu reformuler ta question ?"
        )

async def handle_suggestion_secteur(
    update: Update,
    chat_id: str,
    data: dict[str, object],
) -> None:
    """Groq suggère des tickers pour un secteur, on vérifie les cours via Finnhub."""
    secteur = str(data.get("secteur", ""))

    # Demande à Groq une liste de tickers pour ce secteur
    ticker_prompt = f"""Donne-moi une liste de 5-8 tickers boursiers du secteur {secteur} 
    accessibles sur un PEA (donc européens ou cotés en Europe ou sur NYSE/NASDAQ).
    Retourne UNIQUEMENT un JSON valide : {{"tickers": ["TICKER1", "TICKER2", ...]}}
    Pas de texte autour, juste le JSON."""

    ticker_response = await get_groq_response(
        history=[{"role": "user", "content": ticker_prompt}],
        system_prompt="Tu retournes uniquement du JSON valide.",
    )

    try:
        cleaned = ticker_response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        ticker_data = json.loads(cleaned)
        suggested_tickers: list[str] = ticker_data.get("tickers", [])
    except (json.JSONDecodeError, KeyError):
        await update.message.reply_text("❌ Je n'ai pas pu générer de suggestions pour ce secteur.")  # type: ignore[union-attr]
        return

    await update.message.reply_text(f"🔍 Je vérifie les cours réels de {len(suggested_tickers)} titres {secteur}...")  # type: ignore[union-attr]

    # Vérifie les vrais cours via Finnhub
    quotes = await get_multiple_quotes(suggested_tickers)
    valides = [q for q in quotes if "prix_actuel" in q]

    if not valides:
        await update.message.reply_text("❌ Aucun cours disponible pour ces titres via Finnhub.")  # type: ignore[union-attr]
        return

    courses_text = "\n".join([format_quote_message(q) for q in valides])

    # Ajoute automatiquement à la watchlist
    watchlist = get_watchlist(chat_id)
    nouveaux = [str(q.get("ticker", "")) for q in valides if str(q.get("ticker", "")) and str(q.get("ticker", "")) not in watchlist]
    if nouveaux:
        ajout_msg = f"\n\n💬 Veux-tu que j'ajoute {', '.join(nouveaux)} à ta watchlist ? Réponds *oui* ou *non*."
    else:
        ajout_msg = ""  

    await update.message.reply_text(  # type: ignore[union-attr]
        f"📊 **Titres {secteur} avec cours en temps réel :**\n\n{courses_text}{ajout_msg}"
    )

async def handle_confirmation_watchlist(
    update: Update,
    chat_id: str,
    data: dict[str, object],
) -> None:
    """Gère la confirmation d'ajout à la watchlist."""
    reponse = str(data.get("reponse", "non")).lower()
    
    # Récupère les tickers en attente depuis la dernière suggestion
    # On les extrait du dernier message assistant dans l'historique
    history = get_conversation_history(chat_id, limit=3)
    derniere_suggestion = ""
    for msg in reversed(history):
        if msg["role"] == "assistant" and "watchlist" in msg["content"]:
            derniere_suggestion = msg["content"]
            break
    
    if reponse in ("oui", "ok", "yes", "vas-y", "oui merci"):
        # Extrait les tickers du message précédent
        import re
        tickers = re.findall(r'\b[A-Z]{2,5}\b', derniere_suggestion)
        watchlist = get_watchlist(chat_id)
        nouveaux = [t for t in tickers if t not in watchlist and t not in ("ET", "OK", "PEA")]
        if nouveaux:
            watchlist.extend(nouveaux)
            update_watchlist(chat_id, watchlist)
            await update.message.reply_text(f"✅ {', '.join(nouveaux)} ajoutés à ta watchlist !")  # type: ignore[union-attr]
        else:
            await update.message.reply_text("Watchlist déjà à jour !")  # type: ignore[union-attr]
    else:
        await update.message.reply_text("Ok, aucun ajout effectué.")  # type: ignore[union-attr]