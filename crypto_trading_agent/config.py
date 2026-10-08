import os
from dotenv import load_dotenv

load_dotenv()

# --- Exchange Configuration ---
EXCHANGE = "binance"
API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# --- Trading Pairs ---
TRADING_PAIRS = ["BTC/USDT", "ETH/USDT", "BNB/USDT"]

# --- Strategy Parameters ---
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70       # Sell signal threshold
RSI_OVERSOLD = 30         # Buy signal threshold

SHORT_MA_PERIOD = 9       # Short moving average (EMA)
LONG_MA_PERIOD = 21       # Long moving average (EMA)

# --- Timeframe ---
TIMEFRAME = "1h"          # Candle interval: 1m, 5m, 15m, 1h, 4h, 1d

# --- Risk Management ---
TRADE_AMOUNT_USDT = 50.0  # Amount in USDT per trade
STOP_LOSS_PCT = 0.02      # 2% stop loss
TAKE_PROFIT_PCT = 0.04    # 4% take profit
MAX_OPEN_TRADES = 3       # Maximum concurrent open trades

# --- Paper Trading ---
PAPER_TRADING = True      # Set False for live trading (USE WITH CAUTION)
PAPER_BALANCE = 1000.0    # Starting virtual balance in USDT

# --- Logging ---
LOG_FILE = "trading_agent.log"
LOG_LEVEL = "INFO"

# --- Polling Interval (seconds) ---
POLL_INTERVAL = 60        # How often to check signals (60s recommended for 1h candles)
