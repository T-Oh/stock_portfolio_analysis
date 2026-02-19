"""
Module: utils.py

Provides utility functions for processing portfolio activity data and preparing it
for time series and portfolio calculations, as well as for saving data in a format
compatible with Tableau.

Functions:
- remove_timezone_from_index(df):
    Removes timezone information from a DataFrame or Series index, returning the
    same object with a naive datetime index.

- process_input(activities):
    Splits the activity log into subsets by type: buys, sells, stock dividends,
    and cash dividends.

- add_signed_change(activities):
    Adds a 'signed_change' column to the activity DataFrame, representing the signed
    volume change per activity type, which is used to compute inventory over time.

- save_formatted_df(df, savename):
    Saves a DataFrame to CSV for Tableau, formatting the date as YYYY-MM-DD,
    using UTF-8 encoding and a comma separator.
"""

import pandas as pd

def remove_timezone_from_index(df):
    """Remove timezone information from a DataFrame or Series index.
    Args:
        df (pd.DataFrame or pd.Series): Object whose DatetimeIndex may be timezone-aware.
    Returns:
        pd.DataFrame or pd.Series: Same object with its index localized to no timezone
    """

    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df

def process_input(activities):
    buys = activities[activities['type']=='B']
    sells = activities[activities['type']=='S']
    stock_dividends = activities[activities['type']=='SD']
    cash_dividends = activities[activities['type']=='CD']
    return buys, sells, stock_dividends, cash_dividends

def add_signed_change(activities):
    '''Add a column to activities that represents the signed change in volume for each activity type.
    This column will be used to calculate the inventory of stocks owned over time.
    Args:
        activities (pd.DataFrame): DataFrame containing the activity log with columns including 'type' and 'volume'.
    Returns:
        pd.DataFrame: The input DataFrame with an additional 'signed_change' column.
    '''
    multiplier = {"B" : 1, "S" : -1, "SD": 1, "CD" : 0}
    activities['signed_change'] = activities['volume']*activities['type'].map(multiplier)
    return activities

def save_formatted_df(df, savename):
    '''Save a DataFrame to CSV with date formatted as YYYY-MM-DD and UTF-8 encoding for Tableau.
    This function ensures that the date column is in the correct format and that the CSV is saved with UTF-8 encoding and a comma separator, which is suitable for importing into Tableau.
    Args:
        df (pd.DataFrame): The DataFrame to be saved.
        savename (str): The filename for the saved CSV, including .csv extension.
    '''
    
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
    df.to_csv('tableau_data/'+savename, index=False, encoding='utf-8-sig', sep=',')