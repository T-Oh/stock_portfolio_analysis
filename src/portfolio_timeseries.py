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
import numpy as np

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
            - cumulative_buys (float, total money spent on buys up to that date)
            - cumulative_sales (float, total money gained from sales up to that date)
            - total_return (float, returns: depotwert + cumulative_sales - cumulative_buys)
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
    time_series_df = compute_total_returns(time_series_df, activities)
    time_series_df = add_unrealized_gain_fifo(time_series_df, activities)

    # Strip whitespace from column names to ensure consistency
    time_series_df.columns = time_series_df.columns.str.strip()
    portfolio.columns = portfolio.columns.str.strip()
    
    return time_series_df, portfolio

def compute_total_returns(time_series_df, activities):
    '''Compute total returns for the portfolio and individual assets as a time series.
    
    Uses the formula: total_return(t) = current_market_value(t) + sum_t(sales(t)) - sum_t(buys(t))
    Where:
        - current_market_value(t) = depotwert (current value of holdings)
        - sum_t(sales(t)) = cumulative proceeds from sales up to time t
        - sum_t(buys(t)) = cumulative cost of buys up to time t
    
    This provides a total return metric that accounts for capital in and out of the portfolio,
    representing the total profit/loss including realized gains from sales and remaining positions.
    
    Args:
        time_series_df (pd.DataFrame): Time series DataFrame with columns:
            - date (datetime)
            - anlage (asset label)
            - depotwert (float, current market value)
            - other columns from the build process
        activities (pd.DataFrame): Activity log with columns:
            - date (datetime)
            - anlage (asset label)
            - type (str: 'B' for buy, 'S' for sell, etc.)
            - volume (float, number of shares)
            - value (float, price per share) - optional, will be fetched from context if needed
    
    Returns:
        pd.DataFrame: Enhanced time_series_df with additional columns:
            - cumulative_buys (float, total money spent on buys up to that date)
            - cumulative_sales (float, total money gained from sales up to that date)
            - total_return (float, returns computed from the formula)
    '''
    
    df = time_series_df.copy()
    
    # Extract buys and sells with their costs/proceeds
    buys = activities[activities['type'] == 'B'].copy()
    sells = activities[activities['type'] == 'S'].copy()
    cash_dividends = activities[activities['type'] == 'CD'].copy()
    

    if 'value' not in buys.columns:
        print("Warning: 'value' column not found in buys activities")
        buys['cost'] = 0
    else:
        buys['cost'] = buys['volume'] * buys['value']
    
    if 'value' not in sells.columns:
        print("Warning: 'value' column not found in sells activities")
        sells['proceeds'] = 0
    else:
        sells['proceeds'] =  sells['value'] #the original excel formatting in Portfolio_Activities.xlsx considers the value field for sells to be the total proceeds, not the price per share, so we can use it directly without multiplying by volume. If your actual data has a different format, you may need to adjust this calculation.
    
    # Build cumulative buy costs per asset per date
    buys_agg = buys.groupby(['date', 'anlage'])['cost'].sum().reset_index()
    buys_agg = buys_agg.sort_values(['anlage', 'date'])
    buys_agg['cumulative_buys'] = buys_agg.groupby('anlage')['cost'].cumsum()
    buys_agg = buys_agg[['date', 'anlage', 'cumulative_buys']]
    
    # Build cumulative sell proceeds per asset per date
    sells_agg = sells.groupby(['date', 'anlage'])['proceeds'].sum().reset_index()
    sells_agg = sells_agg.sort_values(['anlage', 'date'])
    sells_agg['cumulative_sales'] = sells_agg.groupby('anlage')['proceeds'].cumsum()
    sells_agg = sells_agg[['date', 'anlage', 'cumulative_sales']]

    # Build cumulative cash dividends per asset per date
    dividends_agg = cash_dividends.groupby(['date', 'anlage'])['value'].sum().reset_index()
    dividends_agg = dividends_agg.sort_values(['anlage', 'date'])
    dividends_agg['cumulative_dividends'] = dividends_agg.groupby('anlage')['value'].cumsum()
    dividends_agg = dividends_agg[['date', 'anlage', 'cumulative_dividends']]
    
    # Merge cumulative buys and sales and dividends into time series for individual assets
    df = df.merge(buys_agg, on=['date', 'anlage'], how='left')
    df = df.merge(sells_agg, on=['date', 'anlage'], how='left')
    df = df.merge(dividends_agg, on=['date', 'anlage'], how='left')
    
    # Forward-fill cumulative values for dates without activity
    df = df.sort_values(['anlage', 'date']).reset_index(drop=True)
    df['cumulative_buys'] = df.groupby('anlage')['cumulative_buys'].ffill().fillna(0)
    df['cumulative_sales'] = df.groupby('anlage')['cumulative_sales'].ffill().fillna(0)
    df['cumulative_dividends'] = df.groupby('anlage')['cumulative_dividends'].ffill().fillna(0)
    
    # Compute total return for individual assets: depotwert + cumulative_sales - cumulative_buys + cumulative_dividends
    df['total_return'] = df['depotwert'] + df['cumulative_sales'] - df['cumulative_buys'] + df['cumulative_dividends']
    
    # Handle portfolio total ("Gesamtwert") by summing across all assets
    # The portfolio total is the sum of all individual asset returns
    portfolio_total = df[df['anlage'] != 'Gesamtwert'].groupby('date').agg({
        'cumulative_buys': 'sum',
        'cumulative_sales': 'sum',
        'total_return': 'sum'
    }).reset_index()
    portfolio_total['anlage'] = 'Gesamtwert'
    
    # Replace the Gesamtwert row calculations with summed values
    df_non_total = df[df['anlage'] != 'Gesamtwert'].copy()
    df_total = df[df['anlage'] == 'Gesamtwert'].copy()
    
    # Update Gesamtwert with calculated portfolio totals
    df_total = df_total.merge(portfolio_total[['date', 'cumulative_buys', 'cumulative_sales', 'total_return']], 
                              on='date', how='left', suffixes=('_old', ''))
    df_total = df_total.drop(columns=['cumulative_buys_old', 'cumulative_sales_old'], errors='ignore')
    
    # Reconstruct the dataframe
    df = pd.concat([df_non_total, df_total], ignore_index=True).sort_values(['date', 'anlage']).reset_index(drop=True)

    # Weighted total return: normalize total_return by amount of money spent (cumulative_buys)
    # Avoid division by zero - if cumulative_buys is zero, set result to NaN
    df['weighted_total_return'] = np.where(
        df['cumulative_buys'] == 0,
        np.nan,
        df['total_return'] / df['cumulative_buys']
    )
    # Replace infinite values (shouldn't occur due to the guard) and keep NaN for zero-investment periods
    df['weighted_total_return'].replace([np.inf, -np.inf], np.nan, inplace=True)

    return df


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
    
    # Total Depotwert per day
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


def calculate_fifo_cost_basis(asset_name, target_volume, activities):
    """Calculate FIFO cost basis for a specific volume of an asset.
    
    Uses FIFO matching of sell orders to earliest buy orders to determine
    the cost basis of the remaining target volume.
    
    Args:
        asset_name (str): The name of the asset
        target_volume (float): The volume to calculate cost basis for (remaining holdings)
        activities (pd.DataFrame): Activity log with columns: 'date', 'type', 'volume', 'value', 'fee_buy'
    
    Returns:
        float: Cost basis for the target volume using FIFO method
    """
    # Filter and sort activities for this asset
    asset_activities = activities[activities['anlage'] == asset_name].sort_values('date').copy()
    
    # Extract buys and sells
    buys = asset_activities[asset_activities['type'] == 'B'][['date', 'volume', 'value', 'fee_buy']].copy()
    sells = asset_activities[asset_activities['type'] == 'S'][['volume']].copy()
    
    # Build FIFO queue with (volume, cost_per_unit) for each buy
    fifo_queue = []
    for _, buy_row in buys.iterrows():
        
        fifo_queue.append({
            'volume': buy_row['volume'],
            'cost_per_unit': buy_row['value']
        })
    
    # Calculate cost basis for target volume by summing from remaining buys
    cost_basis = 0
    remaining_to_match = target_volume
    
    for buy in fifo_queue:
        if remaining_to_match <= 0:
            break
        volume_to_use = min(buy['volume'], remaining_to_match)
        cost_basis += volume_to_use * buy['cost_per_unit']
        remaining_to_match -= volume_to_use
    
    return cost_basis


def add_unrealized_gain_fifo(time_series_df, activities):
    """Add unrealized gain for the most recent date using FIFO cost basis.
    
    Unrealized gain = depotwert (market value) - FIFO cost basis of remaining holdings
    Only calculates for the most recent date in the time series.
    
    Args:
        time_series_df (pd.DataFrame): Time series DataFrame with columns:
            - date (datetime)
            - anlage (asset label)
            - depotwert (float): current market value
            - volume (float): current volume held
        activities (pd.DataFrame): Activity log with columns:
            - date (datetime)
            - anlage (asset label)
            - type (str: 'B' for buy, 'S' for sell)
            - volume (float)
            - value (float)
            - fee_buy (float)
    
    Returns:
        pd.DataFrame: time_series_df with unrealized_gain and unrealized_gain_pct columns
    """
    df = time_series_df.copy()
    
    # Get the most recent date
    max_date = df['date'].max()
    
    # Only add unrealized gain for the most recent date
    df['unrealized_gain'] = np.nan
    df['unrealized_gain_pct'] = np.nan
    
    # Get last date data (excluding totals)
    last_date_data = df[(df['date'] == max_date) & (df['anlage'] != 'Gesamtwert')].copy()
    
    for _, row in last_date_data.iterrows():
        asset = row['anlage']
        volume = row['volume']
        depotwert = row['depotwert']
        
        if volume > 0:
            # Calculate FIFO cost basis for this asset's remaining volume
            fifo_cost = calculate_fifo_cost_basis(asset, volume, activities)
            unrealized_gain = depotwert - fifo_cost
            unrealized_gain_pct = (unrealized_gain / fifo_cost * 100) if fifo_cost != 0 else np.nan
            
            # Update the dataframe
            df.loc[(df['date'] == max_date) & (df['anlage'] == asset), 'unrealized_gain'] = unrealized_gain
            df.loc[(df['date'] == max_date) & (df['anlage'] == asset), 'unrealized_gain_pct'] = unrealized_gain_pct
    
    # Calculate portfolio total for unrealized gain on last date
    portfolio_unrealized = df[(df['date'] == max_date) & (df['anlage'] != 'Gesamtwert')]['unrealized_gain'].sum()
    portfolio_fifo_cost = df[(df['date'] == max_date) & (df['anlage'] != 'Gesamtwert')]['depotwert'].sum() - portfolio_unrealized
    portfolio_unrealized_pct = (portfolio_unrealized / portfolio_fifo_cost * 100) if portfolio_fifo_cost != 0 else np.nan
    
    df.loc[(df['date'] == max_date) & (df['anlage'] == 'Gesamtwert'), 'unrealized_gain'] = portfolio_unrealized
    df.loc[(df['date'] == max_date) & (df['anlage'] == 'Gesamtwert'), 'unrealized_gain_pct'] = portfolio_unrealized_pct
    
    return df