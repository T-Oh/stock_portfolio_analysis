# Portfolio Time Series Analysis

This project builds a daily portfolio time series and computes portfolio indices based on historical stock prices and activity logs. 
The output can then be viewed and analyzed using the included Tableau Dashboard.

## Features

- Fetch historical stock prices using Yahoo Finance (`yfinance`), with manual price fallbacks.  
- Compute stock inventory over time from buy, sell, and dividend activities.  
- Build daily portfolio time series and calculate portfolio indices like Total Return, Unrealized Return, Drawdown, Total Owned Value etc.  
- Save formatted CSV files ready for Tableau.  

## Requirements

- Conda (recommended)  
- Python 3.10

All required packages are listed in `environment.yml`.

## Setup

1. Create and activate the Conda environment:

```bash
conda env create -f environment.yml
conda activate portfolio
```

### Input Data

The analysis uses `Portfolio_Activities.xlsx` as the activity log. The file should include at least the following columns:

- `anlage` (asset label)
- `date` (date of activity)
- `type` (activity type, e.g., B (Buy), S (Sell), SD (Dividend payed in shares), CD (Dividends payed in money))
- `volume` (number of shares acquired or sold)
- `value` (stock price for Buys, amount of obtained money for Sells and Cash Dividends)

An examplary activity file can be found in `/data`

Ensure that dates are normalized (no time component) and that column names match exactly, as the scripts rely on them.  

Place your activity log Excel file in the data/ folder.
By default, the script looks for data/Portfolio_Activities.xlsx.

## Usage

Run the main script:
```bash
python src/main.py
```

This will:

1. Read the activity log.

2. Fetch historical prices (or apply manual fallbacks).

3. Build the portfolio time series and compute indices.

4. Save CSV files in tableau_data/ for Tableau:

5. time_series_data.csv – daily value per stock and for the total portfolio.

6. portfolio_history.csv – historical prices of stocks.

7. index_benchmark.csv – portfolio index vs MSCI benchmark.

# Tableau Dashboard

## Features

 - KPIs (total value, total returns, unrealized gains, relative unrealized gains)

 - Allocation pie chart

 - Total and relative return bar charts per stock

 - Time series graphs for:

    - Comparison of the portfolio performance to the MSCI World Index

    - Share price development of all assests in your portfolio

    - Development of owned value of your assets and your total portfolio

    - Drawdown of all assets and you total portfolio

    - Weighted Drawdown (Total Drawdown based on owned volumes) for all assets and total portfolio

    - Total Return (including money made from sales and money spent on buys) for all assets and total portfolio

    - Telative Total Return (Total Return normalized to money spent ont buys)

- Compare the graphs to analyze performance of different assets

To visualize the portfolio:

1. Open Tableau and connect to the CSV files in tableau_data/.

2. Use filters and color highlights:

 - Filter by asset to select which stocks to display.

 - Highlight selected assets using color to track them across the portfolio.

If everything worked succesfully you should see something like this:
## Tableau Dashboard Preview

Here’s an example of the dashboard:

![Portfolio Dashboard](images/dashboard.PNG)

## Configuration

 - Modify constants.py to update tickers or manual prices.

 - The data file path can be changed in main.py at the activities assignment.

## Notes

 - Column names are currently mixed English/German for consistency with Tableau dashboards.

 - Manual price overrides are used for tickers that cannot be fetched automatically.
