import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from scrapers.core.base_spider import BaseScraper
from scrapers.models.base_page import BasePage
from scrapers.models.data_model import ProviderResult
from scrapers.utils.utils import setup_drivver

_CORRIDOR_URLS: dict[str, str] = {
    "USD-BDT": "https://www.remitly.com/us/en/bangladesh",
    "GBP-BDT": "https://www.remitly.com/gb/en/bangladesh",
    "EUR-BDT": "https://www.remitly.com/de/en/bangladesh",
}


def _to_decimal(text: str) -> Decimal:
    match = re.search(r"[\d,]+\.?\d*", text)
    if match:
        try:
            return Decimal(match.group(0).replace(",", ""))
        except InvalidOperation:
            pass
    return Decimal("0")


class RemitlySpider(BaseScraper):
    def __init__(self):
        self.driver = setup_drivver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def _set_amount(self, amount: Decimal):
        for selector in [
            "input[data-testid='send-amount-input']",
            "input[data-testid='calculator-send-amount']",
            "input[id*='sendAmount']",
            "input[name*='sendAmount']",
            "input[class*='send'][type='number']",
            "input[class*='send'][type='text']",
        ]:
            try:
                field = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                ActionChains(self.driver).click(field).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(str(int(amount))).perform()
                field.send_keys(Keys.TAB)
                time.sleep(3)
                return
            except Exception:
                continue

    def _extract_rate(self) -> Decimal:
        for selector in [
            "[data-testid='exchange-rate']", "[data-testid='fx-rate']",
            "[data-testid='calculator-rate']", "[data-testid*='rate']",
            "[class*='ExchangeRate']", "[class*='exchangeRate']",
        ]:
            els = self.driver.find_elements(By.CSS_SELECTOR, selector)
            for el in els:
                t = el.text.strip()
                if t and ("BDT" in t or "=" in t):
                    return _to_decimal(t.split("=")[-1] if "=" in t else t)
        src = self.driver.page_source
        match = re.search(r"1\s*\w+\s*=\s*([\d.,]+)\s*BDT", src)
        return _to_decimal(match.group(1)) if match else Decimal("0")

    def _extract_fees(self) -> dict[str, Decimal]:
        body = self.driver.find_element(By.TAG_NAME, "body").text
        fees: dict[str, Decimal] = {}

        if re.search(r"\bno\s+fee\b|\bfree\s+transfer\b|\bno\s+transfer\s+fee\b", body, re.IGNORECASE):
            fees["bank"] = Decimal("0")
        else:
            # Try to find fee per method — Remitly often lists "Economy" (bank) and "Express" (debit/card)
            for method, pattern in [
                ("bank", r"Economy.*?([\d.,]+)\s*USD"),
                ("debit_card", r"Express.*?([\d.,]+)\s*USD"),
            ]:
                m = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
                if m:
                    fees[method] = _to_decimal(m.group(1))

            if not fees:
                m = re.search(r"([\d.,]+)\s*USD\s*(?:fee|transfer fee)", body, re.IGNORECASE)
                fees["bank"] = _to_decimal(m.group(1)) if m else Decimal("0")

        return fees

    def _extract_transfer_time(self) -> dict[str, str]:
        body = self.driver.find_element(By.TAG_NAME, "body").text
        times: dict[str, str] = {}

        for method, pattern in [
            ("bank", r"Economy.*?(\d+[-–]\d+\s*(?:business\s*)?days?|\d+\s*(?:business\s*)?days?)"),
            ("debit_card", r"Express.*?(\d+[-–]\d+\s*(?:business\s*)?(?:minute|hour|day)s?|[Ii]n\s+minutes?)"),
        ]:
            m = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
            if m:
                times[method] = m.group(1)

        if not times:
            m = re.search(
                r"(\d+[-–]\d+\s*(?:business\s*)?(?:minute|hour|day)s?|\d+\s*(?:business\s*)?(?:minute|hour|day)s?|[Ii]n\s+minutes?)",
                body,
            )
            times["bank"] = m.group(0) if m else "Minutes to hours"

        return times

    def scrape(self, send_currency: str, recv_currency: str, send_amount: Decimal) -> ProviderResult:
        corridor = f"{send_currency}-{recv_currency}"
        url = _CORRIDOR_URLS.get(corridor)
        if not url:
            msg = f"RemitlySpider does not support corridor {corridor}"
            raise ValueError(msg)

        self.driver.get(url)
        time.sleep(8)
        self._set_amount(send_amount)

        rate = self._extract_rate()
        fees = self._extract_fees()
        transfer_time = self._extract_transfer_time()
        bank_fee = fees.get("bank", Decimal("0"))
        receive = (send_amount - bank_fee) * rate if rate else None

        return ProviderResult(
            provider="Remitly",
            corridor=corridor,
            send_amount=send_amount,
            exchange_rate=rate,
            fees=fees,
            transfer_time=transfer_time,
            receive_amount=receive.quantize(Decimal("0.00000001")) if receive else None,
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )

    def close(self):
        self.driver.quit()
