# Task 2: Stock Portfolio Performance Tracker

A command-line tool that tracks an investment portfolio. You enter ticker symbols, buy prices and share quantities; it calculates the current value and gain/loss of each holding and logs the results to a CSV file.

## Features
- Positions stored in a dictionary; repeat buys of one ticker are merged with a weighted-average buy price
- Current prices from a CSV (e.g. the S&P 500 ticker dataset), or live via `yfinance` with `--live`
- Per-holding invested amount, market value and **% gain/loss**
- Total invested capital vs. current portfolio value, plus best and worst performer
- Formatted console report
- Results appended with a timestamp to `portfolio_summary.csv` (built-in `csv` module)
- Input validation, manual price entry when a ticker is missing, and a safe fallback if the CSV is open in Excel

## Run
```bash
python portfolio.py                       # interactive
python portfolio.py --demo                # sample portfolio, no typing
python portfolio.py --csv my_prices.csv   # use another price file
python portfolio.py --live                # live prices (pip install yfinance)
python portfolio.py --out results.csv     # choose the output file
```

## Price file format
Any CSV with a ticker column (`Symbol`, `Ticker`...) and a price column (`Price`, `Close`, `Last`...):
```csv
Symbol,Name,Sector,Price
AAPL,Apple Inc.,Information Technology,189.95
```
`sp500_prices.csv` here holds sample prices; replace it with the official dataset if you prefer.

## Output (`portfolio_summary.csv`)
`timestamp, symbol, shares, avg_buy_price, current_price, invested, market_value, gain_loss, gain_loss_pct`, with one `TOTAL` row per run.
