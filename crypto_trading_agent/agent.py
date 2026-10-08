"""
Crypto Trading Agent - RSI + Moving Average Strategy
"""

import time
import logging
import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
from colorama import Fore, Style, init
import config

# Initialize colorama
init(autoreset=True)

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PaperWallet:
    """Simulated wallet for paper trading."""

    def __init__(self, balance: float):
        self.usdt_balance = balance
        self.holdings: dict = {}   # symbol -> {"amount": float, "buy_price": float}
        self.trade_history: list = []

    def get_balance(self) -> float:
        return self.usdt_balance

    def buy(self, symbol: str, amount_usdt: float, price: float) -> bool:
        if self.usdt_balance < amount_usdt:
            logger.warning(f"[Paper] Insufficient balance to buy {symbol}")
            return False
        qty = amount_usdt / price
        self.usdt_balance -= amount_usdt
        self.holdings[symbol] = {"amount": qty, "buy_price": price}
        self.trade_history.append({
            "time": datetime.now().isoformat(),
            "symbol": symbol,
            "side": "BUY",
            "price": price,
            "amount_usdt": amount_usdt,
            "qty": qty
        })
        logger.info(f"{Fore.GREEN}[Paper BUY]  {symbol} @ {price:.4f} | Qty: {qty:.6f} | Spent: ${amount_usdt:.2f}")
        return True

    def sell(self, symbol: str, price: float) -> bool:
        if symbol not in self.holdings:
            logger.warning(f"[Paper] No holdings to sell for {symbol}")
            return False
        qty = self.holdings[symbol]["amount"]
        buy_price = self.holdings[symbol]["buy_price"]
        proceeds = qty * price
        pnl = proceeds - (qty * buy_price)
        self.usdt_balance += proceeds
        self.trade_history.append({
            "time": datetime.now().isoformat(),
            "symbol": symbol,
            "side": "SELL",
            "price": price,
            "amount_usdt": proceeds,
            "qty": qty,
            "pnl": pnl
        })
        del self.holdings[symbol]
        color = Fore.GREEN if pnl >= 0 else Fore.RED
        logger.info(f"{color}[Paper SELL] {symbol} @ {price:.4f} | Qty: {qty:.6f} | PnL: ${pnl:.2f}")
        return True

    def summary(self):
        total_pnl = sum(t.get("pnl", 0) for t in self.trade_history)
        logger.info(f"\n{'='*50}")
        logger.info(f"  PAPER WALLET SUMMARY")
        logger.info(f"  USDT Balance : ${self.usdt_balance:.2f}")
        logger.info(f"  Open Trades  : {list(self.holdings.keys())}")
        logger.info(f"  Total PnL    : ${total_pnl:.2f}")
        logger.info(f"  Total Trades : {len(self.trade_history)}")
        logger.info(f"{'='*50}\n")


class TradingAgent:
    """Crypto trading agent using RSI + EMA crossover strategy."""

    def __init__(self):
        self.exchange = self._init_exchange()
        self.paper_wallet = PaperWallet(config.PAPER_BALANCE) if config.PAPER_TRADING else None
        self.open_trades: dict = {}   # symbol -> entry price
        logger.info(f"Trading Agent initialized | Mode: {'PAPER' if config.PAPER_TRADING else 'LIVE'}")
        logger.info(f"Pairs: {config.TRADING_PAIRS} | Timeframe: {config.TIMEFRAME}")

    def _init_exchange(self) -> ccxt.Exchange:
        exchange_class = getattr(ccxt, config.EXCHANGE)
        params = {
            "apiKey": config.API_KEY,
            "secret": config.API_SECRET,
            "enableRateLimit": True,
        }
        exchange = exchange_class(params)
        logger.info(f"Connected to {config.EXCHANGE.upper()}")
        return exchange

    # ------------------------------------------------------------------ #
    #  Data Fetching                                                       #
    # ------------------------------------------------------------------ #

    def fetch_ohlcv(self, symbol: str) -> pd.DataFrame:
        """Fetch OHLCV candles and return as DataFrame."""
        candles = self.exchange.fetch_ohlcv(
            symbol,
            timeframe=config.TIMEFRAME,
            limit=max(config.LONG_MA_PERIOD, config.RSI_PERIOD) + 50
        )
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df

    # ------------------------------------------------------------------ #
    #  Indicators                                                          #
    # ------------------------------------------------------------------ #

    def compute_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def compute_ema(self, series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df["rsi"] = self.compute_rsi(df["close"], config.RSI_PERIOD)
        df["ema_short"] = self.compute_ema(df["close"], config.SHORT_MA_PERIOD)
        df["ema_long"] = self.compute_ema(df["close"], config.LONG_MA_PERIOD)
        return df

    # ------------------------------------------------------------------ #
    #  Signal Generation                                                   #
    # ------------------------------------------------------------------ #

    def get_signal(self, df: pd.DataFrame) -> str:
        """
        Strategy:
          BUY  when RSI < oversold AND short EMA crosses above long EMA
          SELL when RSI > overbought OR short EMA crosses below long EMA
        """
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        rsi = latest["rsi"]
        ema_cross_up = (prev["ema_short"] <= prev["ema_long"]) and (latest["ema_short"] > latest["ema_long"])
        ema_cross_down = (prev["ema_short"] >= prev["ema_long"]) and (latest["ema_short"] < latest["ema_long"])

        if rsi < config.RSI_OVERSOLD and ema_cross_up:
            return "BUY"
        elif rsi > config.RSI_OVERBOUGHT or ema_cross_down:
            return "SELL"
        return "HOLD"

    # ------------------------------------------------------------------ #
    #  Stop Loss / Take Profit                                             #
    # ------------------------------------------------------------------ #

    def check_sl_tp(self, symbol: str, current_price: float) -> str:
        """Returns 'SELL' if SL or TP hit, else 'HOLD'."""
        if symbol not in self.open_trades:
            return "HOLD"
        entry = self.open_trades[symbol]
        change = (current_price - entry) / entry
        if change <= -config.STOP_LOSS_PCT:
            logger.warning(f"{Fore.RED}[SL HIT] {symbol} | Entry: {entry:.4f} | Now: {current_price:.4f} | {change*100:.2f}%")
            return "SELL"
        if change >= config.TAKE_PROFIT_PCT:
            logger.info(f"{Fore.GREEN}[TP HIT] {symbol} | Entry: {entry:.4f} | Now: {current_price:.4f} | {change*100:.2f}%")
            return "SELL"
        return "HOLD"

    # ------------------------------------------------------------------ #
    #  Trade Execution                                                     #
    # ------------------------------------------------------------------ #

    def execute_trade(self, symbol: str, signal: str, price: float):
        if signal == "BUY":
            if symbol in self.open_trades:
                return  # already in position
            if len(self.open_trades) >= config.MAX_OPEN_TRADES:
                logger.info(f"Max open trades reached. Skipping {symbol}")
                return
            if config.PAPER_TRADING:
                success = self.paper_wallet.buy(symbol, config.TRADE_AMOUNT_USDT, price)
            else:
                success = self._live_buy(symbol, price)
            if success:
                self.open_trades[symbol] = price

        elif signal == "SELL":
            if symbol not in self.open_trades:
                return  # nothing to sell
            if config.PAPER_TRADING:
                success = self.paper_wallet.sell(symbol, price)
            else:
                success = self._live_sell(symbol, price)
            if success:
                del self.open_trades[symbol]

    def _live_buy(self, symbol: str, price: float) -> bool:
        """Execute a real market buy order."""
        try:
            amount = config.TRADE_AMOUNT_USDT / price
            order = self.exchange.create_market_buy_order(symbol, amount)
            logger.info(f"{Fore.GREEN}[LIVE BUY] {symbol} | Order: {order['id']} | Price: {price:.4f}")
            return True
        except ccxt.BaseError as e:
            logger.error(f"Buy order failed for {symbol}: {e}")
            return False

    def _live_sell(self, symbol: str, price: float) -> bool:
        """Execute a real market sell order."""
        try:
            balance = self.exchange.fetch_balance()
            base_asset = symbol.split("/")[0]
            amount = balance["free"].get(base_asset, 0)
            if amount <= 0:
                logger.warning(f"No {base_asset} balance to sell.")
                return False
            order = self.exchange.create_market_sell_order(symbol, amount)
            logger.info(f"{Fore.RED}[LIVE SELL] {symbol} | Order: {order['id']} | Price: {price:.4f}")
            return True
        except ccxt.BaseError as e:
            logger.error(f"Sell order failed for {symbol}: {e}")
            return False

    # ------------------------------------------------------------------ #
    #  Main Loop                                                           #
    # ------------------------------------------------------------------ #

    def analyze_pair(self, symbol: str):
        """Run full analysis cycle for one trading pair."""
        try:
            df = self.fetch_ohlcv(symbol)
            df = self.add_indicators(df)
            current_price = df["close"].iloc[-1]
            rsi = df["rsi"].iloc[-1]
            ema_short = df["ema_short"].iloc[-1]
            ema_long = df["ema_long"].iloc[-1]

            logger.info(
                f"{Fore.CYAN}{symbol:<12} | Price: {current_price:>10.4f} | "
                f"RSI: {rsi:>5.1f} | EMA{config.SHORT_MA_PERIOD}: {ema_short:.4f} | "
                f"EMA{config.LONG_MA_PERIOD}: {ema_long:.4f}"
            )

            # Check SL/TP first
            sl_tp_signal = self.check_sl_tp(symbol, current_price)
            if sl_tp_signal == "SELL":
                self.execute_trade(symbol, "SELL", current_price)
                return

            # Then check strategy signal
            signal = self.get_signal(df)
            if signal != "HOLD":
                logger.info(f"{Fore.YELLOW}Signal: {signal} for {symbol}")
            self.execute_trade(symbol, signal, current_price)

        except ccxt.NetworkError as e:
            logger.error(f"Network error for {symbol}: {e}")
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error for {symbol}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error for {symbol}: {e}")

    def run(self):
        """Start the trading loop."""
        logger.info(f"\n{'='*50}")
        logger.info("  CRYPTO TRADING AGENT STARTED")
        logger.info(f"  Mode     : {'PAPER TRADING' if config.PAPER_TRADING else '⚠️  LIVE TRADING'}")
        logger.info(f"  Strategy : RSI({config.RSI_PERIOD}) + EMA({config.SHORT_MA_PERIOD}/{config.LONG_MA_PERIOD})")
        logger.info(f"  Pairs    : {', '.join(config.TRADING_PAIRS)}")
        logger.info(f"{'='*50}\n")

        iteration = 0
        while True:
            iteration += 1
            logger.info(f"\n--- Iteration {iteration} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

            for pair in config.TRADING_PAIRS:
                self.analyze_pair(pair)
                time.sleep(0.5)  # small delay between pairs to respect rate limits

            if config.PAPER_TRADING:
                self.paper_wallet.summary()

            logger.info(f"Sleeping {config.POLL_INTERVAL}s until next cycle...\n")
            time.sleep(config.POLL_INTERVAL)
