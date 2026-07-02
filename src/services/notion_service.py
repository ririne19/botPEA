from typing import Any, TypedDict

from notion_client import AsyncClient

from src.config import NOTION_API_KEY, NOTION_TRANSACTIONS_DB_ID
from src.services.finnhub_service import QuoteResult


class Position(TypedDict):
    """Position dans le portefeuille (ticker + quantité + PRU)."""

    ticker: str
    quantite: float
    valeur_investie: float
    pru: float


notion = AsyncClient(auth=NOTION_API_KEY)


async def add_transaction(
    ticker: str,
    transaction_type: str,
    date: str,
    quantity: float,
    prix_unitaire: float,
    secteur: str = "Tech",
    notes: str = "",
) -> dict[str, Any]:
    """
    Ajoute une transaction dans la base Notion Transactions PEA.

    Args:
        ticker: symbole boursier (ex: "ASML")
        transaction_type: "Achat" ou "Vente"
        date: date au format YYYY-MM-DD
        quantity: nombre de parts
        prix_unitaire: prix par part en €
        secteur: secteur de l'action
        notes: notes libres

    Returns:
        La page Notion créée (dict brut de l'API Notion)
    """
    result: dict[str, Any] = await notion.pages.create(
        parent={"database_id": NOTION_TRANSACTIONS_DB_ID},
        properties={
            "Ticker": {"title": [{"text": {"content": ticker}}]},
            "Type": {"select": {"name": transaction_type}},
            "Date": {"date": {"start": date}},
            "Quantité": {"number": quantity},
            "Prix unitaire": {"number": prix_unitaire},
            "Secteur": {"select": {"name": secteur}},
            "Source": {"select": {"name": "Message Telegram"}},
            "Notes": {"rich_text": [{"text": {"content": notes}}]},
        },
    )
    return result


async def get_portfolio() -> list[Position]:
    """
    Récupère toutes les transactions depuis Notion et calcule le portefeuille actuel.

    Returns:
        liste de positions avec ticker, quantité totale, PRU
    """
    response: dict[str, Any] = await notion.databases.query(  # type: ignore[attr-defined]
        **{
            "database_id": NOTION_TRANSACTIONS_DB_ID,
            "sorts": [{"property": "Date", "direction": "ascending"}],
        }
    )

    raw_positions: dict[str, dict[str, float]] = {}

    results: list[dict[str, Any]] = response.get("results", [])  # type: ignore[misc]
    for page in results:
        page_data: dict[str, Any] = page  # type: ignore[assignment]
        props: dict[str, Any] = dict(page_data["properties"])

        ticker: str = (
            str(props["Ticker"]["title"][0]["plain_text"])
            if props["Ticker"]["title"]
            else ""
        )
        transaction_type: str = (
            str(props["Type"]["select"]["name"])
            if props["Type"]["select"]
            else ""
        )
        quantity: float = float(props["Quantité"]["number"] or 0)
        prix_unitaire: float = float(props["Prix unitaire"]["number"] or 0)

        if not ticker:
            continue

        if ticker not in raw_positions:
            raw_positions[ticker] = {"quantite": 0.0, "valeur_investie": 0.0}

        if transaction_type == "Achat":
            raw_positions[ticker]["quantite"] += quantity
            raw_positions[ticker]["valeur_investie"] += quantity * prix_unitaire
        elif transaction_type == "Vente":
            raw_positions[ticker]["quantite"] -= quantity
            raw_positions[ticker]["valeur_investie"] -= quantity * prix_unitaire

    result: list[Position] = []
    for ticker, pos in raw_positions.items():
        if pos["quantite"] > 0:
            result.append(
                Position(
                    ticker=ticker,
                    quantite=pos["quantite"],
                    valeur_investie=round(pos["valeur_investie"], 2),
                    pru=round(pos["valeur_investie"] / pos["quantite"], 2),
                )
            )

    return result


def format_portfolio_message(positions: list[Position]) -> str:
    """Formate le portefeuille en message lisible pour Telegram."""
    if not positions:
        return "📭 Ton portefeuille est vide pour l'instant."

    lines = ["📊 **Ton portefeuille actuel :**\n"]
    for pos in positions:
        lines.append(
            f"• **{pos['ticker']}** — {pos['quantite']} part(s)\n"
            f"  PRU : {pos['pru']} € | Investi : {pos['valeur_investie']} €"
        )

    return "\n".join(lines)


def format_portfolio_with_prices(
    positions: list[Position],
    quotes: list[QuoteResult],
) -> str:
    """
    Formate le portefeuille avec valorisation actuelle et plus-value.

    Args:
        positions: liste des positions (depuis Notion)
        quotes: liste des cours actuels (depuis Finnhub)
    """
    if not positions:
        return "📭 Ton portefeuille est vide pour l'instant."

    quotes_by_ticker: dict[str, QuoteResult] = {
        str(q.get("ticker", "")): q for q in quotes
    }

    lines = ["📊 **Ton portefeuille avec valorisation :**\n"]
    total_investi: float = 0.0
    total_valeur: float = 0.0

    for pos in positions:
        quote = quotes_by_ticker.get(pos["ticker"])
        investi: float = float(pos["valeur_investie"])
        total_investi += investi

        if quote and "prix_actuel" in quote:
            prix_actuel: float = float(str(quote["prix_actuel"]))
            valeur_actuelle: float = round(pos["quantite"] * prix_actuel, 2)
            plus_value: float = round(valeur_actuelle - investi, 2)
            pv_pct: float = round((plus_value / investi) * 100, 2) if investi > 0 else 0.0
            # emoji et signe définis ICI dans le bon scope, avant d'être utilisés
            emoji: str = "📈" if plus_value >= 0 else "📉"
            signe: str = "+" if plus_value >= 0 else ""
            total_valeur += valeur_actuelle

            lines.append(
                f"{emoji} **{pos['ticker']}** — {pos['quantite']} part(s)\n"
                f"  PRU : {pos['pru']} € | Actuel : {prix_actuel} €\n"
                f"  Plus-value : {signe}{plus_value} € ({signe}{pv_pct}%)"
            )
        else:
            total_valeur += investi
            lines.append(
                f"• **{pos['ticker']}** — {pos['quantite']} part(s)\n"
                f"  PRU : {pos['pru']} € | Cours indisponible"
            )

    plus_value_totale: float = round(total_valeur - total_investi, 2)
    signe_total: str = "+" if plus_value_totale >= 0 else ""
    lines.append(
        f"\n💼 **Total investi :** {round(total_investi, 2)} €\n"
        f"💰 **Valorisation actuelle :** {round(total_valeur, 2)} €\n"
        f"📊 **Plus-value totale :** {signe_total}{plus_value_totale} €"
    )

    return "\n".join(lines)