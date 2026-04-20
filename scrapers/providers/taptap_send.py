import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from scrapers.core.base_spider import BaseScraper
from scrapers.models.base_page import BasePage
from scrapers.models.data_model import ProviderResult
from scrapers.utils.utils import setup_driver

_CORRIDOR_URLS: dict[str, str] = {
    "USD-BDT": "https://www.taptapsend.com/send-to/bangladesh",
    "GBP-BDT": "https://www.taptapsend.com/send-to/bangladesh",
    "EUR-BDT": "https://www.taptapsend.com/send-to/bangladesh",
}


def _to_decimal(text: str) -> Decimal:
    match = re.search(r"[\d,]+\.?\d*", text)
    if match:
        try:
            return Decimal(match.group(0).replace(",", ""))
        except InvalidOperation:
            pass
    return Decimal("0")


class TaptapSendSpider(BaseScraper):
    def __init__(self):
        self.driver = setup_driver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def _extract_rate(self) -> Decimal:
        for selector in ["[class*='rate']", "[class*='exchange']", "[class*='Rate']", "[data-testid*='rate']"]:
            for el in self.driver.find_elements(By.CSS_SELECTOR, selector):
                t = el.text.strip()
                if "BDT" in t or "USD" in t or "=" in t:
                    part = t.split("=")[-1] if "=" in t else t
                    return _to_decimal(part)
        src = self.driver.page_source
        m = re.search(r"1\s*\w+\s*=\s*([\d.,]+)\s*BDT", src)
        return _to_decimal(m.group(1)) if m else Decimal("0")

    def _extract_fees(self) -> dict[str, Decimal]:
        # Taptap Send is typically fee-free for bank transfers
        for selector in ["[class*='fee']", "[class*='Fee']", "[data-testid*='fee']"]:
            for el in self.driver.find_elements(By.CSS_SELECTOR, selector):
                t = el.text.strip()
                if t and len(t) > 3:
                    return {"bank": _to_decimal(t)}
        return {"bank": Decimal("0")}

    def _extract_transfer_time(self) -> dict[str, str]:
        for selector in ["[class*='speed']", "[class*='delivery']", "[class*='time']", "[data-testid*='speed']"]:
            for el in self.driver.find_elements(By.CSS_SELECTOR, selector):
                t = el.text.strip()
                if t and len(t) > 3:
                    return {"bank": t}
        return {"bank": "Minutes (bank transfer: 1-2 days)"}

    def scrape(self, send_currency: str, recv_currency: str, send_amount: Decimal) -> ProviderResult:
        corridor = f"{send_currency}-{recv_currency}"
        url = _CORRIDOR_URLS.get(corridor)
        if not url:
            msg = f"TaptapSendSpider does not support corridor {corridor}"
            raise ValueError(msg)

        self.driver.get(url)
        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='rate'], [class*='exchange'], [class*='amount']"))
            )
        except Exception:
            pass

        rate = self._extract_rate()
        fees = self._extract_fees()
        transfer_time = self._extract_transfer_time()
        bank_fee = fees.get("bank", Decimal("0"))
        receive = (send_amount - bank_fee) * rate if rate else None

        return ProviderResult(
            provider="Taptap Send",
            corridor=corridor,
            send_amount=send_amount,
            exchange_rate=rate,
            fees=fees,
            transfer_time=transfer_time,
            receive_amount=receive.quantize(Decimal("0.01")) if receive else None,
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )

    def close(self):
        self.driver.quit()
