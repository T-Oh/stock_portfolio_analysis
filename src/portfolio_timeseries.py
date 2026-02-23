"""
Module for constructing portfolio time series and computing portfolio indices.

This module provides functions to process portfolio activity logs and historical
stock prices to calculate daily portfolio values and indices. Key functionalities:

- build_portfolio_timeseries: Build the full portfolio time series and compute
  the portfolio index based on weighted returns.
- prepare_inventory: Convert activity logs into cumulative stock volumes per day.
- merge_prices_and_compute_depotwert: Merge historical prices with inventory
  to compute daily position values and total portfolio value.
- compute_portfolio_index: Compute the portfolio index from weighted returns and
  include benchmark comparison (MSCI World index).

All functions expect long-format pandas DataFrames and return DataFrames suitable
for further analysis or visualization.
"""

import pandas as pd

def build_portfolio_timeseries(activities, historical_prices):
    '''Build a time series of the portfolio value (depotwert) over time by merging the inventory of stocks owned with their historical prices.
    This function prepares the inventory of stocks owned over time based on the activity log, merges it with the historical prices to compute the daily depotwert for each stock, and then computes the portfolio index based on the weighted returns of the individual stocks. The resulting time series and portfolio index are returned as DataFrames.
    Args:
        activities (pd.DataFrame): DataFrame containing the activity log with columns including 'date', 'anlage', 'type' and 'volume'.
        historical_prices (pd.DataFrame): Long-format DataFrame with columns ['date', 'anlage', 'kurs'] representing the historical close price of each stock on each date.
    Returns:
        time_series_df, LongFormat DataFrame with columns:
            - date (datetime)
            - anlage (stock label)
            - kurs (float, close price)
            - volume (float, cumulative volume owned)
            - depotwert (float, value of the position in that stock on that date)
        portfolio, LongFormat DataFrame with columns:
            - date (datetime)
            - anlage (str, either 'normalisierte_rendite' for the portfolio or 'MSCI' for the benchmark)
            - gewichtete_rendite (float, weighted return of the portfolio or return of MSCI)
            - index (float, cumulative index value starting at 100)
    '''
    df_inventory = prepare_inventory(activities)
    time_series_df = merge_prices_and_compute_depotwert(df_inventory, historical_prices)
    portfolio, time_series_df = compute_portfolio_index(time_series_df)
    portfolio, time_series_df, max_drawdown = compute_drawdown(portfolio, time_series_df)


    # Strip whitespace from column names to ensure consistency
    time_series_df.columns = time_series_df.columns.str.strip()
    portfolio.columns = portfolio.columns.str.strip()
    
    return time_series_df, portfolio

def compute_drawdown(portfolio, time_series_df):
    '''Compute the drawdown of the portfolio index over time.
    This function calculates the drawdown of the portfolio index by comparing the current index value to the historical maximum index value. The drawdown is expressed as a percentage and indicates the decline from the peak value.
    Args:
        portfolio (pd.DataFrame): DataFrame with columns ['date', 'anlage', 'gewichtete_rendite', 'index'] representing the portfolio index over time.
    Returns:
        pd.DataFrame: DataFrame with columns:
            - date (datetime)
            - anlage (str, should be 'normalisierte_rendite' for the portfolio)
            - drawdown (float, percentage drawdown from the historical maximum index value)
    '''
    time_series_df = time_series_df.copy()
    time_series_df['historical_max'] = time_series_df.groupby('anlage')['kurs'].transform('cummax')
    time_series_df['drawdown'] = (time_series_df['kurs'] - time_series_df['historical_max']) / time_series_df['historical_max']
    time_series_df['weighted_drawdown'] = time_series_df['drawdown'] * time_series_df['gewicht_prev']
    max_drawdown = time_series_df['drawdown'].min()
    df = portfolio.copy()
    df['historical_max'] = df['index'].cummax()
    df['drawdown'] = (df['index'] - df['historical_max']) / df['historical_max']
    max_drawdown = df['drawdown'].min()
    time_series_df['drawdown'][time_series_df['anlage'] == 'Gesamtwert'] = df['drawdown'][df['anlage'] == 'normalisierte_rendite'].values
    time_series_df['weighted_drawdown'][time_series_df['anlage'] == 'Gesamtwert'] = df['drawdown'][df['anlage'] == 'normalisierte_rendite'].values
    return df, time_series_df, max_drawdown


def prepare_inventory(activities):
    ''' Calculate inventory of stocks owned over time based on activities, including buys, sells and dividends.
    This function creates a time series of the volume of each stock owned on each date, which will be used to compute the portfolio value when merged with historical prices.
    Args:
        activities (pd.DataFrame): DataFrame containing the activity log with columns including 'date', 'anlage', 'type' and 'volume'.
    Returns:    
        pd.DataFrame: Long-format DataFrame with columns:
            - date (datetime)
            - anlage (stock label)
            - volume (float, cumulative volume of the stock owned on that date)
    '''

    df_inventory = activities.pivot_table(
        index='date', columns='anlage', values='signed_change', aggfunc='sum'
    ).fillna(0).cumsum()
    
    # Alle Daten auffüllen
    all_dates = pd.date_range(start=df_inventory.index.min(), end=df_inventory.index.max())
    df_inventory = df_inventory.reindex(all_dates).ffill().fillna(0)
    
    # Reset Index
    df_inventory = df_inventory.reset_index().rename(columns={'index': 'date'})
    df_inventory.columns.name = None
    
    # Transform to long format
    df_long_inventory = df_inventory.melt(
        id_vars='date', var_name='anlage', value_name='volume'
    )
    return df_long_inventory


def merge_prices_and_compute_depotwert(df_inventory, historical_prices):
    '''Merge historical prices with inventory to compute daily depot value per stock.
    This function takes the long-format inventory DataFrame and merges it with the historical prices to compute the daily value of the portfolio (depotwert) for each stock. It also computes the total depotwert per day.
    Args:
        df_inventory (pd.DataFrame): Long-format DataFrame with columns ['date', 'anlage', 'volume'] representing the cumulative volume of each stock owned on each date.
        historical_prices (pd.DataFrame): Long-format DataFrame with columns ['date', 'anlage', 'kurs'] representing the historical close price of each stock on each date.
    Returns:
        pd.DataFrame: DataFrame with columns:
            - date (datetime)
            - anlage (stock label)
            - kurs (float, close price)
            - volume (float, cumulative volume owned)
            - depotwert (float, value of the position in that stock on that date)
    '''

    df = pd.merge(
        historical_prices,
        df_inventory,
        on=['date','anlage'],
        how='left'
    )
    df['volume'] = df['volume'].ffill().fillna(0)
    df['depotwert'] = df['kurs'] * df['volume']
    df = df.ffill()
    
    # Total Depotwert pro Tag
    total = df.groupby("date", as_index=False)["depotwert"].sum()
    total['kurs'] = 0
    total['anlage'] = "Gesamtwert"
    
    df = pd.concat([df, total], ignore_index=True)
    return df


def compute_portfolio_index(time_series_df):
    '''Compute the portfolio index based on weighted returns of individual stocks and compare it to the MSCI World index.
    This function calculates the daily return for each stock, computes a weighted return for the portfolio based on the previous day's weights, and then computes the cumulative index for the portfolio. It also extracts the MSCI World index from the time series for comparison.
    Args:
        time_series_df (pd.DataFrame): DataFrame with columns ['date', 'anlage', 'kurs', 'volume', 'depotwert'] representing the daily value of each stock in the portfolio.
    Returns:
        pd.DataFrame: DataFrame with columns:
            - date (datetime)
            - anlage (str, either 'normalisierte_rendite' for the portfolio or 'MSCI' for the benchmark)
            - gewichtete_rendite (float, weighted return of the portfolio or return of MSCI)
            - index (float, cumulative index value starting at 100)
    '''

    df = time_series_df.copy()
    
    # Returns per Anlage
    df['return'] = df.groupby('anlage')['kurs'].pct_change()
    
    # Index pro Anlage
    df['index'] = (1 + df['return']).groupby(df['anlage']).cumprod() * 100
    
    # Gewichtete Rendite für Portfolio
    df['gesamtwert_prev'] = df.groupby('date')['depotwert'].transform('sum').shift(1) 
    df['gewicht_prev'] = df['depotwert'].shift(1) / (df['gesamtwert_prev'] / 2 ) # Devision by 2 to acount for the fact that the total portfolio value is included as an asset in the time series and would otherwise distort the weights
    df['gewichtete_rendite'] = df['gewicht_prev'] * df['return']
    
    # Portfolio-Index
    portfolio = df.groupby('date')['gewichtete_rendite'].sum().reset_index()
    portfolio['anlage'] = 'normalisierte_rendite'
    portfolio['index'] = (1 + portfolio['gewichtete_rendite']).cumprod() * 100
    
    # MSCI hinzufügen
    mscidata = df[df['anlage']=='MSCI'][['date','gewichtete_rendite','anlage','index']]
    portfolio = pd.concat([portfolio, mscidata], ignore_index=True)
    
    portfolio['date'] = pd.to_datetime(portfolio['date'])
    portfolio['index'] = portfolio['index'].astype(float)
    
    return portfolio, df