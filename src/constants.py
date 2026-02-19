"""
Constants used for price fetching.

MANUAL_PRICES: Dictionary of manual/fallback prices for tickers that cannot be
    fetched automatically from Yahoo Finance.

TICKER_MAP: Dictionary mapping portfolio asset labels to their corresponding
    Yahoo Finance ticker symbols.
"""

# Manual prices for tickers that can't be fetched automatically
MANUAL_PRICES = {
    'OTLY' : 11.19
}

# Mapping of stock labels to Yahoo Finance tickers
TICKER_MAP = {
    'ETH': 'ETH-USD',
    'BTC': 'BTC-USD',
    'APPLE': 'AAPL',
    'AMZN': 'AMZN',
    'MSCI': 'EUNL.DE',

}