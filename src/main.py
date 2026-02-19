# -*- coding: utf-8 -*-
"""
Main script for processing portfolio activities and generating Tableau-ready CSVs.

This script orchestrates the workflow for analyzing a portfolio based on historical prices 
and a log of stock activities. It performs the following steps:

1. Load activity log from Excel (buys, sells, dividends).
2. Add signed changes to compute cumulative stock volumes.
3. Fetch historical prices for relevant assets from Yahoo Finance, with manual fallbacks.
4. Compute daily portfolio values, weighted returns, and portfolio and benchmark indices.
5. Save output as CSVs for Tableau visualization.

Inputs:
- data/Portfolio_Activities.xlsx: Excel file containing the activity log.

Outputs (saved in 'tableau_data/'):
- time_series_data.csv: daily portfolio values per stock.
- portfolio_history.csv: historical prices per stock.
- index_benchmark.csv: weighted portfolio index and benchmark index (MSCI).

Dependencies:
- portfolio_timeseries.py: portfolio calculation functions.
- price_fetcher.py: functions to fetch historical prices.
- utils.py: helper functions (save CSV, add signed changes, etc.)
- constants.py: ticker map and manual price constants.

Author: Tobias Ohlinger

"""
import pandas as pd
import datetime

from portfolio_timeseries import build_portfolio_timeseries
from price_fetcher import fetch_historical_prices
from constants import TICKER_MAP
from utils import add_signed_change, save_formatted_df

# Define the path to the activity log Excel file
DATA_FILE_PATH = 'data/Portfolio_Activities.xlsx'

def main():
    # Read activity log and preprocess
    activities = pd.read_excel(DATA_FILE_PATH)
    activities = activities.sort_values('date').reset_index(drop=True)
    activities['date'] = pd.to_datetime(activities['date']).dt.normalize()
    activities = add_signed_change(activities)

    # Determine date range for fetching prices
    start_date = activities['date'].min()
    end_date = datetime.datetime.today()
    historical_prices = fetch_historical_prices(TICKER_MAP, start_date, end_date)

    # Calculate portfolio values per day from historical prices and owned shares inferred from activities
    time_series_df, portfolio = build_portfolio_timeseries(activities, historical_prices)
   
    # Save formatted data for Tableau
    print('Saving formatted data for Tableau...\n')
    save_formatted_df(time_series_df, 'time_series_data.csv')
    save_formatted_df(historical_prices, 'portfolio_history.csv')
    save_formatted_df(portfolio, 'index_benchmark.csv')
    print('All files saved succesfully!\n')



def get_stock_conclusions(activities, buys, sells, stock_dividends, cash_dividends, historical_prices):
    # UNUSED: This function was originally intended to compute per-stock summary metrics such as current value, dividends, fees and gains
    # It is currently reserved for future use if we want to add a detailed stock summary table in Tableau. For now, all relevant metrics are computed in the time series and portfolio DataFrames.
    """Compute per-stock summary metrics such as current value, dividends, fees and gains.

    Uses the latest available price for each asset (from historical_prices or MANUAL_PRICES)
    to compute current values and various aggregates based on the provided activity DataFrames.

    Args:
        activities (pd.DataFrame): Full activity log with an 'anlage' column listing assets.
        buys (pd.DataFrame): Subset of activities corresponding to buy actions.
        sells (pd.DataFrame): Subset of activities corresponding to sell actions.
        stock_dividends (pd.DataFrame): Subset corresponding to stock dividend actions.
        cash_dividends (pd.DataFrame): Subset corresponding to cash dividend actions.
        historical_prices (Mapping or pd.DataFrame): Object providing recent prices per asset.
            Expected to support .get(key) returning a Series or similar sequence of prices,
            or be a DataFrame with asset columns.

    Returns:
        pd.DataFrame: Index=asset label, columns include:
            - kurs (float): last known price
            - CD (float): total cash dividends
            - value_at_buy (float): total invested at buys (excl. fees)
            - value_of_sells (float): total proceeds from sells
            - fees_buy (float): total buy fees
            - fees_annual (float): estimated annual fees pro-rated by days owned
            - volume (float): current volume held
            - value_current (float): current market value
            - profit (float): computed profit accounting for dividends, sells and fees
            - tot_value, tot_fees_payed, tot_gain, rel_gain
    """

    today = datetime.datetime.now()

    # Use last available price (latest date in historical prices) per stock for conclusions
    last_prices = {}
    for stock in activities['anlage'].unique():
        price_series = historical_prices.get(stock)
        if price_series is not None and not price_series.empty:
            last_prices[stock] = price_series.dropna().iloc[-1]
        else:
            last_prices[stock] = MANUAL_PRICES.get(stock, 0)

    stock_conclusions = pd.DataFrame({'kurs': [last_prices.get(stock, 0) for stock in activities['anlage'].unique()]},
                                     index=activities['anlage'].unique())

    buys = buys.copy()
    buys['value_of_buy'] = buys.volume*buys.value #Total value of buy actions excluding fees
    buys['days_owned'] = 0
    for ID in buys.index:
        buys.at[ID,'days_owned'] = (today - buys.at[ID,'date']).days

    volumes = []
    stock_conclusions['CD'] = 0.0                 #Total cash dividends per stock
    stock_conclusions['value_at_buy'] = 0.0       #Total value of all buy actions per stock excluding fees
    stock_conclusions['value_of_sells'] = 0.0     #Total value of sell actions per stock excluding fees
    stock_conclusions['fees_buy'] = 0.0           #Total fees payed at buying per stock
    stock_conclusions['fees_annual'] = 0.0        #Total payed annual fees per stock (calculated per day of ownership)

    for stock in activities['anlage'].unique():
        volumes.append(buys[buys['anlage']==stock]['volume'].sum()
                       - sells[sells['anlage']==stock]['volume'].sum()
                       + stock_dividends[stock_dividends['anlage']==stock]['volume'].sum())
        stock_conclusions.at[stock,'CD'] = cash_dividends[cash_dividends['anlage']==stock]['volume'].sum()
        stock_conclusions.at[stock,'value_at_buy'] = buys[buys['anlage']==stock]['value_of_buy'].sum()
        stock_conclusions.at[stock,'value_of_sells'] = sells[sells['anlage']==stock]['value'].sum()
        stock_conclusions.at[stock,'fees_buy'] = (buys[buys['anlage']==stock]['value']*buys[buys['anlage']==stock]['volume']*buys[buys['anlage']==stock].get('fee_buy',0)).sum()
        # Annual fees estimated as fee_annual * days owned / 365
        stock_conclusions.at[stock,'fees_annual'] = ((buys[buys['anlage']==stock]['fee_annual']*buys[buys['anlage']==stock]['days_owned']/365).sum())

    stock_conclusions['volume'] = volumes
    stock_conclusions['value_current'] = stock_conclusions['volume'] * stock_conclusions['kurs']

    # Calculate profit for each stock
    stock_conclusions['profit'] = (stock_conclusions['value_current'] + stock_conclusions['CD'] + stock_conclusions['value_of_sells']
                                   - stock_conclusions['value_at_buy'] - stock_conclusions['fees_buy'] - stock_conclusions['fees_annual'])


    stock_conclusions['tot_value'] = stock_conclusions['volume']*stock_conclusions['kurs'] #Total value of owned stocks (excluding fees, sells and dividends)
    stock_conclusions['tot_fees_payed'] = stock_conclusions['fees_buy']+stock_conclusions['fees_annual']
    
    stock_conclusions['tot_gain'] = stock_conclusions['tot_value']+stock_conclusions['CD']-stock_conclusions['value_at_buy']+stock_conclusions['value_of_sells']-stock_conclusions['tot_fees_payed']
    stock_conclusions['rel_gain'] = stock_conclusions['tot_gain']/stock_conclusions['value_at_buy']
    return stock_conclusions



if __name__ == "__main__":
    main()



   

   

   
