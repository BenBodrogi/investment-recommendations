import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

import config
from data.errors import DataSourceError


@dataclass
class NewsSentiment:
    symbol: str
    average_sentiment: float | None   # roughly -1..1, None if no scored articles
    headlines: list[str] = field(default_factory=list)


def get_news_sentiment(symbol: str, limit: int = 5) -> NewsSentiment:
    """Targeted per-symbol query — call only for deep-dive candidates, never
    the whole watchlist, to conserve the free-tier quota."""
    api_key = os.getenv("MARKETAUX_API_KEY")
    if not api_key:
        raise DataSourceError("marketaux", symbol, "MARKETAUX_API_KEY is not set")

    published_after = (
        datetime.now(timezone.utc) - timedelta(days=config.MARKETAUX_LOOKBACK_DAYS)
    ).strftime("%Y-%m-%dT%H:%M")

    try:
        resp = requests.get(
            f"{config.MARKETAUX_BASE_URL}/news/all",
            params={
                "symbols": symbol,
                "filter_entities": "true",
                "language": "en",
                "published_after": published_after,
                "limit": limit,
                "api_token": api_key,
            },
            timeout=config.DEFAULT_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        articles = resp.json().get("data") or []
    except requests.RequestException as exc:
        raise DataSourceError("marketaux", symbol, str(exc)) from exc

    scores = []
    headlines = []
    for article in articles:
        headlines.append(article.get("title", ""))
        for entity in article.get("entities") or []:
            if entity.get("symbol") == symbol and entity.get("sentiment_score") is not None:
                scores.append(entity["sentiment_score"])

    return NewsSentiment(
        symbol=symbol,
        average_sentiment=(sum(scores) / len(scores)) if scores else None,
        headlines=headlines,
    )
