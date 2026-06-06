from scrapers.providers.wise import WiseSpider
from scrapers.providers.remitly import RemitlySpider
from scrapers.providers.xoom import XoomSpider
from scrapers.providers.western_union import WesternUnionSpider
from scrapers.providers.moneygram import MoneyGramSpider
from scrapers.providers.taptap_send import TaptapSendSpider
from scrapers.providers.monito import MonitoSpider

# To add a new provider: create scrapers/providers/<name>.py implementing BaseScraper,
# then add an entry here with the corridors it supports.
# To add a new corridor to an existing provider: append the corridor string to its list.

PROVIDERS: list[dict] = [
    {
        "name": "Wise",
        "spider": WiseSpider,
        "tier": "B",  # Web calculator (also has public API — upgrade to A later)
        "corridors": ["USD-BDT", "GBP-BDT", "EUR-BDT", "MYR-BDT", "SGD-BDT"],
        "enabled": True,
    },
    {
        "name": "Remitly",
        "spider": RemitlySpider,
        "tier": "B",
        "corridors": ["USD-BDT", "GBP-BDT", "EUR-BDT"],
        "enabled": True,
    },
    {
        "name": "Xoom",
        "spider": XoomSpider,
        "tier": "B",
        "corridors": ["USD-BDT", "GBP-BDT"],
        "enabled": True,
    },
    {
        "name": "Western Union",
        "spider": WesternUnionSpider,
        "tier": "B",
        "corridors": ["USD-BDT", "GBP-BDT", "EUR-BDT", "SAR-BDT", "AED-BDT", "MYR-BDT", "QAR-BDT", "OMR-BDT"],
        "enabled": True,
    },
    {
        "name": "MoneyGram",
        "spider": MoneyGramSpider,
        "tier": "B",
        "corridors": ["USD-BDT", "GBP-BDT", "EUR-BDT"],
        "enabled": True,
    },
    {
        "name": "Taptap Send",
        "spider": TaptapSendSpider,
        "tier": "B",
        "corridors": ["USD-BDT", "GBP-BDT", "EUR-BDT"],
        "enabled": True,
    },
    {
        "name": "Monito",
        "spider": MonitoSpider,
        "tier": "B",  # Aggregator — useful for cross-checking
        "corridors": ["USD-BDT", "GBP-BDT", "EUR-BDT"],
        "enabled": True,
    },
]
