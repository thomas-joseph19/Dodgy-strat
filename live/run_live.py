"""
Live trading entry point — Python ↔ NinjaTrader bridge.

Usage
-----
    cd dodgy
    python -m live.run_live

Start this BEFORE attaching the strategy in NinjaTrader.
The server waits for NinjaTrader to connect.

Environment variables (or a .env file + python-dotenv):

    NINJA_HOST        address to listen on (default "127.0.0.1")
    NINJA_PORT        port to listen on    (default "6789")
    RITHMIC_CONTRACTS number of contracts  (default "1")

Quick-start with .env
---------------------
Create  dodgy/.env :

    NINJA_HOST=127.0.0.1
    NINJA_PORT=6789
    RITHMIC_CONTRACTS=1

Then run:

    pip install python-dotenv
    python -c "from dotenv import load_dotenv; load_dotenv()" 2>/dev/null; python -m live.run_live

Or just export the vars in your shell and run:

    python -m live.run_live
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)

# Try to load .env automatically if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from live.ninja_bridge import NinjaBridge


def main() -> None:
    bridge = NinjaBridge.from_env()
    try:
        asyncio.run(bridge.run())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Interrupted — exiting.")


if __name__ == "__main__":
    main()
