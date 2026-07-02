from typing import TypedDict

import httpx

from src.config import FINNHUB_API_KEY

BASE_URL = "https://finnhub.io/api/v1"


class QuoteResult(TypedDict, total=False):
    """Type pour le résultat d'un cours boursier."""
    ticker: str
    prix_actuel: float
    variation_pct: float
    haut_jour: float
    bas_jour: float
    ouverture: float
    cloture_precedente: float
    error: str


class NewsArticle(TypedDict):
    """Type pour un article de news."""
    titre: str | None
    resume: str | None
    url: str | None
    source: str | None


async def get_quote(ticker: str) -> QuoteResult:
    """
    Récupère le cours actuel d'un ticker via Finnhub.

    Args:
        ticker: le symbole boursier (ex: "ASML", "AAPL")

    Returns:
        QuoteResult avec prix, variation, haut/bas du jour
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/quote",
            params={"symbol": ticker, "token": FINNHUB_API_KEY},
        )
        response.raise_for_status()
        data = response.json()

    if data.get("c") == 0:
        return {"ticker": ticker, "error": f"Ticker '{ticker}' introuvable ou non couvert en free tier"}

    return {
        "ticker": ticker,
        "prix_actuel": data["c"],
        "variation_pct": round(data["dp"], 2),
        "haut_jour": data["h"],
        "bas_jour": data["l"],
        "ouverture": data["o"],
        "cloture_precedente": data["pc"],
    }


async def get_multiple_quotes(tickers: list[str]) -> list[QuoteResult]:
    """
    Récupère les cours de plusieurs tickers.

    Args:
        tickers: liste de symboles boursiers

    Returns:
        liste de QuoteResult
    """
    results: list[QuoteResult] = []
    for ticker in tickers:
        try:
            quote = await get_quote(ticker)
            results.append(quote)
        except Exception as e:
            results.append({"ticker": ticker, "error": str(e)})
    return results


async def get_company_news(ticker: str, from_date: str, to_date: str) -> list[NewsArticle]:
    """
    Récupère les actualités récentes d'une entreprise.

    Args:
        ticker: le symbole boursier
        from_date: date de début au format YYYY-MM-DD
        to_date: date de fin au format YYYY-MM-DD

    Returns:
        liste d'articles avec titre, resume, url, source
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/company-news",
            params={
                "symbol": ticker,
                "from": from_date,
                "to": to_date,
                "token": FINNHUB_API_KEY,
            },
        )
        response.raise_for_status()
        articles: list[dict[str, str]] = response.json()

    return [
        NewsArticle(
            titre=article.get("headline"),
            resume=article.get("summary"),
            url=article.get("url"),
            source=article.get("source"),
        )
        for article in articles[:5]
    ]

async def get_company_name(ticker: str) -> str:
    """Récupère le nom complet d'une entreprise via Finnhub."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/stock/profile2",
                params={"symbol": ticker, "token": FINNHUB_API_KEY},
            )
            response.raise_for_status()
            data = response.json()
            return str(data.get("name", ticker))
        except Exception:
            return ticker  # Retourne le ticker si le nom n'est pas trouvable

def format_quote_message(quote: QuoteResult, company_name: str = "") -> str:
    """Formate un cours en message lisible pour Telegram."""
    if "error" in quote:
        return f"❌ {quote.get('ticker')} : {quote.get('error')}"

    variation = float(str(quote.get("variation_pct", 0)))
    emoji = "📈" if variation >= 0 else "📉"
    signe = "+" if variation >= 0 else ""
    
    # Affiche le nom complet si disponible, sinon juste le ticker
    titre = f"{company_name} ({quote.get('ticker')})" if company_name else str(quote.get('ticker'))

    return (
        f"{emoji} **{titre}**\n"
        f"Prix actuel : {quote.get('prix_actuel')} €\n"
        f"Variation : {signe}{variation}%\n"
        f"Haut/Bas du jour : {quote.get('haut_jour')} / {quote.get('bas_jour')}"
    )