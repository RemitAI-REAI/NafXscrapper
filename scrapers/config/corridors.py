from decimal import Decimal

# Corridors run in this priority order. Add new ones here to enable them.
PRIORITY: list[str] = [
    "USD-BDT",  # P1 — fully scraped
    "GBP-BDT",  # P2
    "EUR-BDT",  # P3
    "SAR-BDT",  # P4
    "AED-BDT",  # P5
    "MYR-BDT",  # P6
    "KWD-BDT",  # P7
    "QAR-BDT",  # P8
    "OMR-BDT",  # P9
    "SGD-BDT",  # P10
]

# Standard send amount per corridor (used for fair provider comparison)
SEND_AMOUNT: dict[str, Decimal] = {corridor: Decimal("1000") for corridor in PRIORITY}
