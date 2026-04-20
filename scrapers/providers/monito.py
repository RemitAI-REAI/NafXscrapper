import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from scrapers.core.base_spider import BaseScraper
from scrapers.models.base_page import BasePage
from scrapers.models.data_model import ProviderResult
from scrapers.utils.utils import setup_drivver

# Monito is a comparison aggregator — URL encodes corridor and send amount
_CORRIDOR_URL_TEMPLATES: dict[str, str] = {
    "USD-BDT": "https://www.monito.com/send-money/usa/bangladesh/usd/{amount}",
    "GBP-BDT": "https://www.monito.com/send-money/united-kingdom/bangladesh/gbp/{amount}",
    "EUR-BDT": "https://www.monito.com/send-money/germany/bangladesh/eur/{amount}",
}


def _to_decimal(text: str) -> Decimal:
    match = re.search(r"[\d,]+\.?\d*", text)
    if match:
        try:
            return Decimal(match.group(0).replace(",", ""))
        except InvalidOperation:
            pass
    return Decimal("0")


class MonitoSpider(BaseScraper):
    def __init__(self):
        self.driver = setup_drivver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def _wait_for_results(self):
        try:
            WebDriverWait(self.driver, 25).until(
                lambda d: len(d.find_elements(
                    By.CSS_SELECTOR,
                    "[class*='SearchResult'], [class*='result'], [class*='offer'], li[class*='search']",
                )) > 0
            )
        except Exception:
            pass

    def _extract_results(self, recv_currency: str) -> list[str]:
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        results = []
        for tag in ["li", "article", "div"]:
            for row in soup.find_all(tag):
                text = row.get_text(separator=" ").strip()
                if recv_currency in text and len(text) > 30:
                    results.append(text[:300])
            if results:
                break
        if not results:
            results = re.findall(rf"[\d.,]+\s*{recv_currency}", self.driver.page_source)[:5]
        return results

    def scrape(self, send_currency: str, recv_currency: str, send_amount: Decimal) -> ProviderResult:
        corridor = f"{send_currency}-{recv_currency}"
        template = _CORRIDOR_URL_TEMPLATES.get(corridor)
        if not template:
            msg = f"MonitoSpider does not support corridor {corridor}"
            raise ValueError(msg)

        url = template.format(amount=int(send_amount))
        self.driver.get(url)
        time.sleep(15)
        self._wait_for_results()

        results = self._extract_results(recv_currency)

        # Best rate = first BDT amount found (Monito sorts by best rate)
        rate = Decimal("0")
        for r in results:
            m = re.search(rf"([\d.,]+)\s*{recv_currency}", r)
            if m:
                candidate = _to_decimal(m.group(1))
                # Monito may show total receive amount rather than rate — normalise
                if candidate > send_amount:
                    rate = (candidate / send_amount).quantize(Decimal("0.00000001"))
                else:
                    rate = candidate
                break

        return ProviderResult(
            provider="Monito",
            corridor=corridor,
            send_amount=send_amount,
            exchange_rate=rate,
            fees={"bank": Decimal("0")},   # Monito shows net receive — fee already baked in
            transfer_time={"bank": "Varies by provider"},
            receive_amount=None,
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )

    def close(self):
        self.driver.quit()
