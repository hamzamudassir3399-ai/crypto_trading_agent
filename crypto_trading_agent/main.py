"""
main.py - Entry point for the Crypto Trading Agent
"""

import sys
import signal
from agent import TradingAgent
import config


def handle_exit(sig, frame):
    print("\n\nShutting down trading agent gracefully...")
    sys.exit(0)


def main():
    # Register Ctrl+C handler
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    print("""
╔══════════════════════════════════════════╗
║       CRYPTO TRADING AGENT v1.0          ║
║   Strategy: RSI + EMA Crossover          ║
╚══════════════════════════════════════════╝
""")

    if not config.PAPER_TRADING:
        print("⚠️  WARNING: LIVE TRADING MODE ENABLED")
        print("Real money will be used. Are you sure? (yes/no): ", end="")
        confirm = input().strip().lower()
        if confirm != "yes":
            print("Aborted. Set PAPER_TRADING=True in config.py to use paper mode.")
            sys.exit(0)
    else:
        print(f"✅ Paper trading mode | Virtual balance: ${config.PAPER_BALANCE:.2f} USDT\n")

    agent = TradingAgent()
    agent.run()


if __name__ == "__main__":
    main()
