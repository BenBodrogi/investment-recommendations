import re

_SECRET_PARAM_PATTERN = re.compile(r"(token|api_key|api_token|apikey)=([^&\s]+)", re.IGNORECASE)


def redact_secrets(text: str) -> str:
    """Strip API key/token values out of error text before it's logged or
    wrapped in an exception — requests' exception messages often include
    the full request URL, and every client here authenticates via a query
    param at least somewhere."""
    return _SECRET_PARAM_PATTERN.sub(r"\1=***REDACTED***", text)


class DataSourceError(Exception):
    """Normalized failure from any of the 5 API clients, so orchestration
    code only ever needs to catch one exception type."""

    def __init__(self, source: str, symbol: str | None, detail: str):
        self.source = source
        self.symbol = symbol
        self.detail = redact_secrets(detail)
        target = f" ({symbol})" if symbol else ""
        super().__init__(f"[{source}]{target} {self.detail}")
