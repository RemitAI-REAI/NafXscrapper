import logging
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
from scrapers.utils.utils import setup_driver

logger = logging.getLogger(__name__)

_CORRIDOR_URLS: dict[str, str] = {
    "USD-BDT": "https://www.xoom.com/bangladesh/send-money",
    "GBP-BDT": "https://www.xoom.com/bangladesh/send-money",  # Xoom uses same page; currency set by account region
}


def _to_decimal(text: str) -> Decimal:
    match = re.search(r"[\d,]+\.?\d*", text)
    if match:
        try:
            return Decimal(match.group(0).replace(",", ""))
        except InvalidOperation:
            pass
    return Decimal("0")


class XoomSpider(BaseScraper):
    def __init__(self):
        self.driver = setup_driver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def _set_amount(self, amount: Decimal):
        for selector in [
            "input[data-testid='source-amount-input']",
            "[data-testid='calculator-section'] input[type='text']",
            "[data-testid='calculator-section'] input[type='number']",
            "[data-testid='calculator-section'] input",
        ]:
            try:
                field = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                self.driver.execute_script("arguments[0].value = '';", field)
                field.send_keys(str(int(amount)))
                field.send_keys(Keys.TAB)
                time.sleep(3)
                return
            except Exception:
                continue
        logger.warning("XoomSpider: could not find send-amount input field")

    def _extract_rate(self) -> Decimal:
        el = WebDriverWait(self.driver, 15).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='fx-rate-comparison-string']"))
        )
        text = el.text.strip()
        # "1 USD = 115.50 BDT" — take the number after "="
        match = re.search(r"=\s*([\d.,]+)", text)
        return _to_decimal(match.group(1)) if match else _to_decimal(text)

    def _extract_receive_amount(self) -> Decimal | None:
        try:
            el = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='destination-amount-input']"))
            )
            return _to_decimal(el.get_attribute("value") or "0") or None
        except Exception:
            return None

    def _extract_fees(self) -> dict[str, Decimal]:
        fees: dict[str, Decimal] = {}
        try:
            fee_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='fees-sheet-button']"))
            )
            self.driver.execute_script("arguments[0].click();", fee_btn)
            time.sleep(2)
            fee_el = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, "[data-testid='fees-sheet'], [class*='FeesSheet'], [class*='fees']")
                )
            )
            text = fee_el.text.strip()

            # Parse: find each payment section header then grab the dollar amount
            for method, keyword in [
                ("bank", "Bank Account"),
                ("debit_card", "Debit Card"),
                ("credit_card", "Credit Card"),
            ]:
                idx = text.find(keyword)
                if idx >= 0:
                    section = text[idx: idx + 150]
                    m = re.search(r"([\d.,]+)\s*(?:USD)?$", section.split("\n")[1] if "\n" in section else section)
                    if m:
                        fees[method] = _to_decimal(m.group(1))
        except Exception:
            pass

        return fees or {"bank": Decimal("0")}

    def _extract_transfer_time(self) -> dict[str, str]:
        try:
            el = self.driver.find_element(
                By.CSS_SELECTOR, "[data-testid='delivery-estimate'], [class*='delivery'], [class*='speed']"
            )
            return {"bank": el.text.strip()}
        except Exception:
            return {"bank": "Minutes to hours"}

    def scrape(self, send_currency: str, recv_currency: str, send_amount: Decimal) -> ProviderResult:
        corridor = f"{send_currency}-{recv_currency}"
        url = _CORRIDOR_URLS.get(corridor)
        if not url:
            msg = f"XoomSpider does not support corridor {corridor}"
            raise ValueError(msg)

        self.driver.get(url)

        try:
            accept_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[id*='accept'], button[class*='accept']"))
            )
            accept_btn.click()
        except Exception:
            pass

        WebDriverWait(self.driver, 15).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='calculator-section']"))
        )
        self._set_amount(send_amount)

        rate = self._extract_rate()
        fees = self._extract_fees()
        receive = self._extract_receive_amount()
        transfer_time = self._extract_transfer_time()

        return ProviderResult(
            provider="Xoom",
            corridor=corridor,
            send_amount=send_amount,
            exchange_rate=rate,
            fees=fees,
            transfer_time=transfer_time,
            receive_amount=receive,
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )

    def close(self):
        self.driver.quit()
