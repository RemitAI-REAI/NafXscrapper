"""Entry point for the RemitAI scraper.

Usage:
    # Run USD-BDT only (default / P1 corridor):
    python scrapers/main.py

    # Run specific corridors:
    python scrapers/main.py USD-BDT GBP-BDT

    # Run all configured corridors in priority order:
    python scrapers/main.py --all
"""
import logging
import re
import sys

from scrapers.config.corridors import PRIORITY, SEND_AMOUNT
from scrapers.config.providers import PROVIDERS
from scrapers.core.orchestrator import run_all

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

_CORRIDOR_RE = re.compile(r"^[A-Za-z]{3}-[A-Za-z]{3}$")


def main():
    args = sys.argv[1:]

    if "--all" in args:
        corridors = PRIORITY
    elif args:
        corridors = [a for a in args if _CORRIDOR_RE.match(a)]
        if not corridors:
            logging.warning("No valid corridors provided — falling back to USD-BDT")
            corridors = ["USD-BDT"]
    else:
        corridors = ["USD-BDT"]

    run_all(corridors=corridors, providers=PROVIDERS, send_amounts=SEND_AMOUNT)


if __name__ == "__main__":
    main()
