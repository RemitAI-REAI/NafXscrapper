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

_URL = "https://www.westernunion.com/us/en/web/send-money/start"

# Destination country per receive currency
_RECV_COUNTRY: dict[str, str] = {
    "BDT": "Bangladesh",
    "PKR": "Pakistan",
    "INR": "India",
}


def _to_decimal(text: str) -> Decimal:
    match = re.search(r"[\d,]+\.?\d*", text)
    if match:
        try:
            return Decimal(match.group(0).replace(",", ""))
        except InvalidOperation:
            pass
    return Decimal("0")


class WesternUnionSpider(BaseScraper):
    def __init__(self):
        self.driver = setup_drivver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def _select_country(self, country: str, recv_currency: str) -> bool:
        try:
            field = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.ID, "country"))
            )
            field.clear()
            field.send_keys(country)
            field.send_keys(Keys.RETURN)
            WebDriverWait(self.driver, 15).until(
                lambda d: recv_currency in d.find_element(By.TAG_NAME, "body").text
            )
            return True
        except Exception:
            return False

    def _enter_amount(self, amount: Decimal):
        try:
            field = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "txtSendAmount"))
            )
            field.clear()
            field.send_keys(str(int(amount)))
            time.sleep(2)
        except Exception:
            pass

    def _click_payout_method(self, label: str) -> bool:
        for xpath in [
            f"//span[normalize-space()='{label}']",
            f"//*[contains(text(),'{label}') and not(contains(text(),'How'))]",
        ]:
            try:
                el = WebDriverWait(self.driver, 8).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                self.driver.execute_script("arguments[0].click();", el)
                time.sleep(8)
                return True
            except Exception:
                continue
        return False

    def _extract_rate(self) -> Decimal:
        body = self.driver.find_element(By.TAG_NAME, "body").text
        for pat in [r"1\.?\d*\s*USD\s*=\s*([\d.,]+)", r"([\d]{2,4}\.[\d]{2,4})\s*BDT"]:
            m = re.search(pat, body)
            if m:
                return _to_decimal(m.group(1))
        src = self.driver.page_source
        for pat in [r'"exchangeRate"\s*:\s*([\d.]+)', r'"transferRate"\s*:\s*([\d.]+)']:
            m = re.search(pat, src)
            if m and float(m.group(1)) > 50:
                return _to_decimal(m.group(1))
        return Decimal("0")

    def _extract_fees_for_section(self, body: str, keyword: str) -> Decimal | None:
        idx = body.rfind(keyword)
        if idx < 0:
            return None
        section = body[idx: idx + 200]
        m = re.search(r"Fee\S*\s+([\d.,]+)\s*USD", section, re.IGNORECASE)
        return _to_decimal(m.group(1)) if m else None

    def _extract_all_fees(self) -> dict[str, Decimal]:
        body = self.driver.find_element(By.TAG_NAME, "body").text
        fees: dict[str, Decimal] = {}
        for method, keyword in [
            ("bank", "Bank account"),
            ("debit_card", "Debit Card"),
            ("credit_card", "Credit Card"),
            ("cash_pickup", "Cash pick up"),
        ]:
            fee = self._extract_fees_for_section(body, keyword)
            if fee is not None:
                fees[method] = fee
        return fees or {"bank": Decimal("0")}

    def _extract_transfer_time(self) -> dict[str, str]:
        body = self.driver.find_element(By.TAG_NAME, "body").text
        times: dict[str, str] = {}
        pat = r"\d+[-–]\d+\s*(?:Business\s*)?[Dd]ays?|\d+\s*(?:Business\s*)?[Dd]ays?"
        for method, keyword in [
            ("bank", "Bank account"),
            ("debit_card", "Debit Card"),
            ("credit_card", "Credit Card"),
            ("cash_pickup", "Cash pick up"),
        ]:
            idx = body.rfind(keyword)
            if idx > 0:
                m = re.search(pat, body[idx: idx + 150])
                if m:
                    times[method] = m.group(0)
        return times or {"bank": "Minutes to 1 business day"}

    def scrape(self, send_currency: str, recv_currency: str, send_amount: Decimal) -> ProviderResult:
        corridor = f"{send_currency}-{recv_currency}"
        country = _RECV_COUNTRY.get(recv_currency)
        if not country:
            msg = f"WesternUnionSpider does not support recv currency {recv_currency}"
            raise ValueError(msg)

        self.driver.get(_URL)
        time.sleep(18)

        if not self._select_country(country, recv_currency):
            msg = f"Could not select country {country} on Western Union"
            raise RuntimeError(msg)

        self._enter_amount(send_amount)
        self._click_payout_method("Bank account")

        rate = self._extract_rate()
        fees = self._extract_all_fees()
        transfer_time = self._extract_transfer_time()
        bank_fee = fees.get("bank", Decimal("0"))
        receive = (send_amount - bank_fee) * rate if rate else None

        return ProviderResult(
            provider="Western Union",
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
