#!/usr/bin/env python3
"""
Stock Portfolio Performance Tracker
-----------------------------------
Enter stock ticker symbols, buy prices and share quantities. The program:
  * stores the positions in a dictionary (repeat buys of a ticker are merged
    into one position with a weighted-average buy price)
  * looks up current prices from a CSV file (e.g. the S&P 500 ticker dataset)
    or, optionally, live from Yahoo Finance via the `yfinance` package
  * calculates invested capital, current market value and % gain/loss per holding
  * prints a formatted report to the console
  * appends the results (with a timestamp) to 'portfolio_summary.csv'

Usage:
    python portfolio.py                        # interactive, prices from sp500_prices.csv
    python portfolio.py --csv my_prices.csv    # use another price file
    python portfolio.py --live                 # try live prices first (needs: pip install yfinance)
    python portfolio.py --demo                 # run with a built-in sample portfolio
    python portfolio.py --out results.csv      # choose the output CSV name
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PRICE_FILE = HERE / "sp500_prices.csv"
DEFAULT_OUTPUT_FILE = HERE / "portfolio_summary.csv"

# Column names we accept in a price CSV (compared in lowercase)
SYMBOL_COLUMNS = ("symbol", "ticker", "tickers", "stock", "code")
PRICE_COLUMNS = ("price", "current price", "current_price", "last", "last price",
                 "close", "adj close", "adj_close", "market price", "regularmarketprice")

CSV_HEADER = ["timestamp", "symbol", "shares", "avg_buy_price", "current_price",
              "invested", "market_value", "gain_loss", "gain_loss_pct"]

DEMO_POSITIONS = [("AAPL", 150.00, 10), ("MSFT", 320.50, 5),
                  ("NVDA", 410.00, 3), ("INTC", 48.20, 20)]


# --------------------------------------------------------------------------- #
# Price lookup
# --------------------------------------------------------------------------- #
def parse_number(text):
    """Convert strings like '$1,234.50' to float. Returns None if invalid."""
    try:
        return float(str(text).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def load_price_table(path):
    """
    Read a CSV of ticker prices and return {SYMBOL: price}.
    If a symbol appears several times (e.g. historical data), the last row wins.
    """
    prices = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("the CSV file is empty")
        lookup = {name.strip().lower(): name for name in reader.fieldnames}
        symbol_col = next((lookup[c] for c in SYMBOL_COLUMNS if c in lookup), None)
        price_col = next((lookup[c] for c in PRICE_COLUMNS if c in lookup), None)
        if not symbol_col or not price_col:
            raise ValueError(
                f"could not find a ticker and a price column in: {reader.fieldnames}"
            )
        for row in reader:
            symbol = (row.get(symbol_col) or "").strip().upper()
            price = parse_number(row.get(price_col, ""))
            if symbol and price is not None and price > 0:
                prices[symbol] = price
    return prices


def fetch_live_price(symbol):
    """Latest close from Yahoo Finance, or None if yfinance/network unavailable."""
    try:
        import yfinance as yf
        history = yf.Ticker(symbol).history(period="1d")
        if not history.empty:
            return float(history["Close"].iloc[-1])
    except Exception:
        pass
    return None


def get_current_price(symbol, price_table, use_live):
    if use_live:
        live = fetch_live_price(symbol)
        if live:
            return live, "live"
    if symbol in price_table:
        return price_table[symbol], "csv"
    # Some datasets use '-' instead of '.' (BRK-B vs BRK.B)
    alt = symbol.replace(".", "-") if "." in symbol else symbol.replace("-", ".")
    if alt in price_table:
        return price_table[alt], "csv"
    return None, None


# --------------------------------------------------------------------------- #
# User input
# --------------------------------------------------------------------------- #
def ask_positive_number(prompt):
    """Keep asking until the user types a number greater than zero."""
    while True:
        value = parse_number(input(prompt))
        if value is not None and value > 0:
            return value
        print("  Please enter a positive number.")


def add_position(portfolio, symbol, buy_price, shares):
    """Add a purchase. Repeat buys of the same ticker are merged (weighted average)."""
    position = portfolio.setdefault(symbol, {"shares": 0.0, "total_cost": 0.0})
    position["shares"] += shares
    position["total_cost"] += buy_price * shares


def collect_positions():
    portfolio = {}
    print("Enter your holdings. Type 'done' as the ticker when you are finished.\n")
    while True:
        symbol = input("Ticker symbol (e.g. AAPL): ").strip().upper()
        if symbol in ("DONE", "Q", "QUIT", "EXIT"):
            break
        if not symbol or not all(ch.isalnum() or ch in ".-" for ch in symbol):
            print("  Please enter a valid ticker symbol (letters/numbers only).")
            continue
        buy_price = ask_positive_number("  Buy price per share ($): ")
        shares = ask_positive_number("  Number of shares: ")
        add_position(portfolio, symbol, buy_price, shares)
        print(f"  Added {shares:g} x {symbol} @ ${buy_price:,.2f}\n")
    return portfolio


# --------------------------------------------------------------------------- #
# Calculations & reporting
# --------------------------------------------------------------------------- #
def evaluate(portfolio, price_table, use_live):
    """Return (holdings, skipped). Each holding is a dict of calculated values."""
    holdings, skipped = [], []
    for symbol, pos in portfolio.items():
        shares = pos["shares"]
        avg_price = pos["total_cost"] / shares
        price, source = get_current_price(symbol, price_table, use_live)

        if price is None:
            print(f"\nNo current price found for {symbol}.")
            typed = input(f"  Enter the current price for {symbol} (or press Enter to skip): ")
            price, source = parse_number(typed), "manual"
            if price is None or price <= 0:
                skipped.append(symbol)
                continue

        invested = shares * avg_price
        value = shares * price
        gain = value - invested
        holdings.append({
            "symbol": symbol, "shares": shares, "avg_price": avg_price,
            "price": price, "source": source, "invested": invested,
            "value": value, "gain": gain, "pct": gain / invested * 100,
        })
    return holdings, skipped


def money(amount):
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def print_report(holdings, skipped):
    width = 86
    print("\n" + "=" * width)
    print(f"  PORTFOLIO REPORT  -  {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * width)
    print(f"{'Symbol':<8}{'Shares':>9}{'Buy Price':>12}{'Current':>12}"
          f"{'Invested':>14}{'Value':>14}{'Gain/Loss %':>13}")
    print("-" * width)
    for h in holdings:
        arrow = "+" if h["pct"] >= 0 else ""
        print(f"{h['symbol']:<8}{h['shares']:>9g}{money(h['avg_price']):>12}"
              f"{money(h['price']):>12}{money(h['invested']):>14}"
              f"{money(h['value']):>14}{arrow + format(h['pct'], '.2f') + '%':>13}")
    print("-" * width)

    total_invested = sum(h["invested"] for h in holdings)
    total_value = sum(h["value"] for h in holdings)
    total_gain = total_value - total_invested
    total_pct = total_gain / total_invested * 100 if total_invested else 0.0

    print(f"{'Total invested capital:':<30}{money(total_invested):>16}")
    print(f"{'Current portfolio value:':<30}{money(total_value):>16}")
    status = "GAIN" if total_gain >= 0 else "LOSS"
    print(f"{'Overall ' + status + ':':<30}{money(total_gain):>16}  ({total_pct:+.2f}%)")

    if len(holdings) > 1:
        best = max(holdings, key=lambda h: h["pct"])
        worst = min(holdings, key=lambda h: h["pct"])
        print(f"\nBest performer : {best['symbol']} ({best['pct']:+.2f}%)")
        print(f"Worst performer: {worst['symbol']} ({worst['pct']:+.2f}%)")
    if skipped:
        print(f"\nSkipped (no price available): {', '.join(skipped)}")
    print("=" * width)
    return total_invested, total_value, total_gain, total_pct


# --------------------------------------------------------------------------- #
# CSV logging
# --------------------------------------------------------------------------- #
def write_summary(path, holdings, totals):
    """Append this run's results to the CSV log (creates it, with header, if needed)."""
    path = Path(path)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_invested, total_value, total_gain, total_pct = totals

    def save(target):
        is_new = not target.exists() or target.stat().st_size == 0
        with open(target, "a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if is_new:
                writer.writerow(CSV_HEADER)
            for h in holdings:
                writer.writerow([stamp, h["symbol"], f"{h['shares']:g}",
                                 f"{h['avg_price']:.2f}", f"{h['price']:.2f}",
                                 f"{h['invested']:.2f}", f"{h['value']:.2f}",
                                 f"{h['gain']:.2f}", f"{h['pct']:.2f}"])
            writer.writerow([stamp, "TOTAL", "", "", "",
                             f"{total_invested:.2f}", f"{total_value:.2f}",
                             f"{total_gain:.2f}", f"{total_pct:.2f}"])

    try:
        save(path)
        print(f"\nSummary saved to: {path}")
    except PermissionError:
        # Typically the file is open in Excel. Save to a timestamped copy instead.
        backup = path.with_name(f"{path.stem}_{datetime.now():%Y%m%d_%H%M%S}{path.suffix}")
        print(f"\nCould not write to {path.name} (is it open in another program?).")
        save(backup)
        print(f"Summary saved to: {backup}")
    except OSError as err:
        print(f"\nCould not save the summary file: {err}")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description="Stock Portfolio Performance Tracker")
    parser.add_argument("--csv", default=str(DEFAULT_PRICE_FILE),
                        help="CSV file with ticker prices (default: sp500_prices.csv)")
    parser.add_argument("--live", action="store_true",
                        help="try live prices via yfinance first (falls back to the CSV)")
    parser.add_argument("--demo", action="store_true",
                        help="use a built-in sample portfolio instead of typing one in")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_FILE),
                        help="output CSV file (default: portfolio_summary.csv)")
    args = parser.parse_args()

    print("=" * 60)
    print("   STOCK PORTFOLIO PERFORMANCE TRACKER")
    print("=" * 60)

    try:
        price_table = load_price_table(args.csv)
        print(f"Loaded {len(price_table)} prices from {Path(args.csv).name}\n")
    except FileNotFoundError:
        print(f"[warning] Price file '{args.csv}' not found. "
              "You will be asked for prices manually.\n")
        price_table = {}
    except (ValueError, OSError) as err:
        print(f"[warning] Could not read price file: {err}\n")
        price_table = {}

    if args.demo:
        portfolio = {}
        for symbol, price, shares in DEMO_POSITIONS:
            add_position(portfolio, symbol, price, shares)
        print("Demo mode: using sample holdings " +
              ", ".join(s for s, _, _ in DEMO_POSITIONS))
    else:
        try:
            portfolio = collect_positions()
        except (EOFError, KeyboardInterrupt):
            print("\nInput cancelled.")
            return

    if not portfolio:
        print("No holdings entered. Nothing to calculate.")
        return

    try:
        holdings, skipped = evaluate(portfolio, price_table, args.live)
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return

    if not holdings:
        print("No holdings had a usable price. Nothing to report.")
        return

    totals = print_report(holdings, skipped)
    write_summary(args.out, holdings, totals)


if __name__ == "__main__":
    main()
