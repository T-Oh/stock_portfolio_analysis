"""
Module: price_fetcher.py

Provides functionality to fetch historical stock and cryptocurrency prices using yfinance,
with fallbacks to manual prices for tickers with missing data. The prices are returned
in long-format DataFrames suitable for downstream portfolio and time series calculations.

Functions:
- fetch_historical_prices(ticker_map, start_date, end_date):
    Fetches historical close prices for a mapping of labels to tickers. If data is missing,
    falls back to manually specified constant prices. Returns a long-format DataFrame
    with columns ['date', 'anlage', 'kurs'].

- apply_manual_fallback(historical_prices, label, start_date, end_date):
    Helper function to fill missing stock data with a constant manual price from MANUAL_PRICES.
    Updates the historical_prices dictionary in place and returns it.
"""

import yfinance as yf
import numpy as np
import pandas as pd

from constants import MANUAL_PRICES
from utils import remove_timezone_from_index

def fetch_historical_prices(ticker_map, start_date, end_date):
    """Fetch historical close prices for a mapping of labels to tickers.

    For each entry in ticker_map this function tries to download historical Close
    prices via yfinance. If no data is returned or an error occurs, a constant
    fallback series is created from MANUAL_PRICES (or NaN). The result is
    returned in long format suitable for merging: columns ['date','anlage','kurs'].

    Args:
        ticker_map (dict): Mapping of label -> yfinance ticker symbol.
        start_date (datetime-like): Start date for fetching prices (inclusive).
        end_date (datetime-like): End date for fetching prices (exclusive/depending on yfinance).

    Returns:
        pd.DataFrame: Long-format DataFrame with columns:
            - date (datetime)
            - anlage (label)
            - kurs (float, close price)
    """
    print(f"Fetching historical prices from {start_date.date()} to {end_date.date()}...")
    historical_prices = {}
    for label, ticker in ticker_map.items():
        try:
            data = yf.Ticker(ticker).history(start=start_date, end=end_date)
            if data.empty:
                print(f"⚠ No data for {label} ({ticker}), using manual price as constant fallback\n")
                apply_manual_fallback(historical_prices, label, start_date, end_date)
            else:
                prices = data['Close']
                prices.index = pd.to_datetime(prices.index).normalize()
                prices = remove_timezone_from_index(prices.to_frame()).iloc[:, 0]  # convert to Series after removing tz
                full_index = pd.date_range(start=start_date, end=end_date)
                prices = prices.reindex(full_index, method='ffill')
                historical_prices[label] = prices
        except Exception as e:
            print(f"❌ Error fetching {label} ({ticker}): {e}, using manual price fallback\n")
            apply_manual_fallback(historical_prices, label, start_date, end_date)

    hist_prices_df = pd.DataFrame(historical_prices)
    hist_prices_df = hist_prices_df.reset_index()
    hist_prices_df = hist_prices_df.rename(columns={'index': 'date'})
    prices_long = hist_prices_df.melt(id_vars='date', var_name='anlage', value_name='kurs')
    for stock, prices in historical_prices.items():
        historical_prices[stock] = prices.ffill().fillna(0)
    return prices_long

def apply_manual_fallback(historical_prices, label, start_date, end_date):
    '''Apply manual price fallback for any stocks that have missing data after fetching historical prices.
    This function can be called for any stock label that is missing data in historical_prices after the initial fetch.

    Args:        
        historical_prices (dict): Dictionary of label -> pd.Series with historical prices.
        label (str): Stock label for which to apply the manual price fallback.
        start_date (datetime): Start date for the fallback series.
        end_date (datetime): End date for the fallback series.

    Returns:
        pd.Series: The updated historical price series, filled with the manual price for the given label.
    '''
    manual_price = MANUAL_PRICES.get(label, np.nan)
    date_range = pd.date_range(start=start_date, end=end_date)
    historical_prices[label] = pd.Series(manual_price, index=date_range)
    return historical_prices