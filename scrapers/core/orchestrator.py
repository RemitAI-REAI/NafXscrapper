from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal

from scrapers.core.output import save_run
from scrapers.models.data_model import ProviderResult, ScrapeRun

logger = logging.getLogger(__name__)

_CORRIDOR_RE = re.compile(r"^[A-Za-z]{3}-[A-Za-z]{3}$")


def _run_one(provider_cfg: dict, send_currency: str, recv_currency: str, send_amount: Decimal) -> ProviderResult:
    """Instantiate a spider, run scrape(), close() regardless of outcome."""
    spider = provider_cfg["spider"]()
    try:
        return spider.scrape(send_currency, recv_currency, send_amount)
    finally:
        spider.close()


def run_corridor(corridor: str, providers: list[dict], send_amount: Decimal, max_workers: int = 5) -> ScrapeRun:
    """Run all enabled providers for one corridor with bounded parallelism."""
    if not _CORRIDOR_RE.match(corridor):
        msg = f"Invalid corridor format: {corridor!r}. Expected 'XXX-YYY'."
        raise ValueError(msg)

    send_currency, recv_currency = corridor.split("-")
    enabled = [p for p in providers if p["enabled"] and corridor in p["corridors"]]

    run = ScrapeRun(
        corridor=corridor,
        send_amount=send_amount,
        started_at=datetime.now(timezone.utc).isoformat(),
    )

    with ThreadPoolExecutor(max_workers=min(max_workers, len(enabled) or 1)) as pool:
        futures = {
            pool.submit(_run_one, cfg, send_currency, recv_currency, send_amount): cfg["name"]
            for cfg in enabled
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                run.results.append(result)
                logger.info("[%s] OK  rate=%s  fees=%s", name, result.exchange_rate, result.fees)
            except Exception as exc:
                run.errors.append({"provider": name, "error": str(exc)})
                logger.error("[%s] FAIL  %s", name, exc)

    run.completed_at = datetime.now(timezone.utc).isoformat()
    return run


def run_all(corridors: list[str], providers: list[dict], send_amounts: dict[str, Decimal], max_workers: int = 5) -> list[ScrapeRun]:
    """Run corridors sequentially in priority order; save each run to disk."""
    runs = []
    for corridor in corridors:
        logger.info("=" * 60)
        logger.info("Corridor: %s", corridor)
        logger.info("=" * 60)
        amount = send_amounts.get(corridor, Decimal("1000"))
        run = run_corridor(corridor, providers, amount, max_workers)
        save_run(run)
        runs.append(run)
        ok = len(run.results)
        fail = len(run.errors)
        started = datetime.fromisoformat(run.started_at)
        completed = datetime.fromisoformat(run.completed_at)
        elapsed = (completed - started).total_seconds()
        logger.info("Done — %d OK, %d failed, elapsed: %.1fs", ok, fail, elapsed)
    return runs
