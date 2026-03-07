import asyncio
import json
from datetime import datetime

from wise.wise_spider import WiseSpider
from xoom.xoom_spider import XoomSpider
from remitly.remitly_spider import RemitlySpider
from westernunion.wu_spider import WesternUnionSpider
from moneygram.moneygram_spider import MoneyGramSpider
from taptapsend.taptap_spider import TaptapSpider
from monito.monito_spider import MonitoSpider

SPIDERS = [
    WiseSpider,
    XoomSpider,
    RemitlySpider,
    WesternUnionSpider,
    MoneyGramSpider,
    TaptapSpider,
    MonitoSpider,
]


async def main():
    results = []
    errors = []

    for SpiderClass in SPIDERS:
        name = SpiderClass.__name__.replace("Spider", "")
        print(f"\n[{name}] Scraping...", flush=True)
        spider = SpiderClass()
        try:
            data = spider.scrape()
            results.append(data)
            rate = data["exchange_rates"][0]["rate"]
            print(f"[{name}] OK  Rate: {rate}", flush=True)
            print(f"[{name}]    Fees: {data['transaction_fees'][:80]}", flush=True)
            print(f"[{name}]    Time: {data['transfer_times'][:60]}", flush=True)
        except Exception as e:
            errors.append({"provider": name, "error": str(e)})
            print(f"[{name}] FAIL  {e}", flush=True)
        finally:
            try:
                spider.close()
            except Exception:
                pass

    print("\n" + "=" * 60)
    print(f"Scrape completed at {datetime.now().isoformat()}")
    print(f"  Successful: {len(results)} / {len(SPIDERS)}")
    if errors:
        print(f"  Failed:     {[e['provider'] for e in errors]}")
    print("=" * 60)
    print("\n=== FULL RESULTS ===")
    for r in results:
        print(json.dumps(r, indent=2))

    return results


if __name__ == "__main__":
    asyncio.run(main())
