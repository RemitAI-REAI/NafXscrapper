import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from scrapers.core.base_spider import BaseScraper
from scrapers.models.base_page import BasePage
from scrapers.models.data_model import ProviderResult
from scrapers.utils.utils import setup_drivver

_CORRIDOR_URLS: dict[str, str] = {
    "USD-BDT": "https://www.moneygram.com/us/en/corridor/bangladesh",
    "GBP-BDT": "https://www.moneygram.com/gb/en/corridor/bangladesh",
    "EUR-BDT": "https://www.moneygram.com/de/en/corridor/bangladesh",
}


def _to_decimal(text: str) -> Decimal:
    match = re.search(r"[\d,]+\.?\d*", text)
    if match:
        try:
            return Decimal(match.group(0).replace(",", ""))
        except InvalidOperation:
            pass
    return Decimal("0")


class MoneyGramSpider(BaseScraper):
    def __init__(self):
        self.driver = setup_drivver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def _set_amount(self, amount: Decimal):
        try:
            field = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='number'], input[inputmode='decimal']"))
            )
            self.driver.execute_script("arguments[0].value = '';", field)
            field.send_keys(str(int(amount)))
            field.send_keys(Keys.TAB)
            time.sleep(3)
        except Exception:
            pass

    def _extract_rate(self) -> Decimal:
        body = self.driver.find_element(By.TAG_NAME, "body").text
        # Page shows two rates: standard and promo — take the first (standard)
        matches = re.findall(r"([\d.,]+)\s*BDT", body)
        if matches:
            return _to_decimal(matches[0])
        src = self.driver.page_source
        m = re.search(r"([\d.,]+)\s*BDT", src)
        return _to_decimal(m.group(1)) if m else Decimal("0")

    def _extract_fees(self) -> dict[str, Decimal]:
        body = self.driver.find_element(By.TAG_NAME, "body").text
        fees: dict[str, Decimal] = {}

        # MoneyGram typically lists: "Fees1\n5.49 USD\n0.00 USD" (bank=0, card=5.49)
        for method, pattern in [
            ("bank", r"(?:Bank|Online)\s+\w*.*?([\d.,]+)\s*USD"),
            ("debit_card", r"Debit.*?([\d.,]+)\s*USD"),
            ("credit_card", r"Credit.*?([\d.,]+)\s*USD"),
        ]:
            m = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
            if m:
                fees[method] = _to_decimal(m.group(1))

        if not fees:
            m = re.search(r"Fees?\d*\s*([\d.,]+)\s*USD", body, re.IGNORECASE)
            fees["bank"] = _to_decimal(m.group(1)) if m else Decimal("0")

        return fees

    def _extract_transfer_time(self) -> dict[str, str]:
        body = self.driver.find_element(By.TAG_NAME, "body").text
        times: dict[str, str] = {}

        if re.search(r"\binstant\b", body, re.IGNORECASE):
            times["mobile_money"] = "Instant"

        m = re.search(
            r"(\d+[-\u2013]\d+\s*(?:business\s*)?(?:minute|hour|day)s?|\d+\s*(?:business\s*)?(?:minute|hour|day)s?)",
            body, re.IGNORECASE,
        )
        if m:
            times["bank"] = m.group(0)

        return times or {"bank": "Minutes to hours"}

    def scrape(self, send_currency: str, recv_currency: str, send_amount: Decimal) -> ProviderResult:
        corridor = f"{send_currency}-{recv_currency}"
        url = _CORRIDOR_URLS.get(corridor)
        if not url:
            msg = f"MoneyGramSpider does not support corridor {corridor}"
            raise ValueError(msg)

        self.driver.get(url)
        WebDriverWait(self.driver, 20).until(
            lambda d: recv_currency in d.find_element(By.TAG_NAME, "body").text
        )
        time.sleep(3)
        self._set_amount(send_amount)

        rate = self._extract_rate()
        fees = self._extract_fees()
        transfer_time = self._extract_transfer_time()
        bank_fee = fees.get("bank", Decimal("0"))
        receive = (send_amount - bank_fee) * rate if rate else None

        return ProviderResult(
            provider="MoneyGram",
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
