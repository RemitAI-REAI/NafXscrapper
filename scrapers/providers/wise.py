import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from scrapers.core.base_spider import BaseScraper
from scrapers.models.base_page import BasePage
from scrapers.models.data_model import ProviderResult
from scrapers.utils.utils import setup_drivver

_CORRIDOR_URLS: dict[str, str] = {
    "USD-BDT": "https://wise.com/us/pricing/send-money?source=USD&target=BDT&payInMethod=BANK_TRANSFER&sourceAmount=1000",
    "GBP-BDT": "https://wise.com/gb/pricing/send-money?source=GBP&target=BDT&payInMethod=BANK_TRANSFER&sourceAmount=1000",
    "EUR-BDT": "https://wise.com/de/pricing/send-money?source=EUR&target=BDT&payInMethod=BANK_TRANSFER&sourceAmount=1000",
    "MYR-BDT": "https://wise.com/my/pricing/send-money?source=MYR&target=BDT&payInMethod=BANK_TRANSFER&sourceAmount=1000",
    "SGD-BDT": "https://wise.com/sg/pricing/send-money?source=SGD&target=BDT&payInMethod=BANK_TRANSFER&sourceAmount=1000",
}


def _to_decimal(text: str) -> Decimal:
    match = re.search(r"[\d,]+\.?\d*", text.replace(",", ""))
    if match:
        try:
            return Decimal(match.group(0).replace(",", ""))
        except InvalidOperation:
            pass
    return Decimal("0")


class WiseSpider(BaseScraper):
    def __init__(self):
        self.driver = setup_drivver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def _select_currency(self, currency: str, button_id: str, search_id: str):
        button = WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.ID, button_id))
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        time.sleep(0.5)
        self.driver.execute_script("arguments[0].click();", button)
        field = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.ID, search_id))
        )
        field.send_keys(currency)
        field.send_keys(Keys.ENTER)

    def _input_amount(self, amount: Decimal):
        field = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input#source"))
        )
        ActionChains(self.driver).click(field).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(Keys.DELETE).perform()
        field.send_keys(str(int(amount)))

    def _extract_rate(self) -> Decimal:
        el = WebDriverWait(self.driver, 15).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "button[aria-describedby='rateLabel']"))
        )
        return _to_decimal(el.text.strip())

    def _extract_fees(self) -> dict[str, Decimal]:
        container = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".Fees_container"))
        )
        text = container.text.strip()
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        fees: dict[str, Decimal] = {}
        i = 0
        while i < len(lines) - 1:
            label, nxt = lines[i], lines[i + 1]
            if not re.match(r"^[\d.,]+", label) and re.match(r"^[\d.,]+\s*USD", nxt):
                key = re.sub(r"\s+", "_", label.lower().strip(":"))
                fees[key] = _to_decimal(nxt)
                i += 2
            else:
                i += 1

        if not fees:
            # Fallback: grab all USD amounts and label generically
            for idx, amt in enumerate(re.findall(r"[\d.,]+\s*USD", text)):
                fees[f"method_{idx}"] = _to_decimal(amt)

        return fees or {"bank": Decimal("0")}

    def _extract_transfer_time(self) -> dict[str, str]:
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".np-section.m-t-2 p.m-b-0 strong"))
        )
        el = self.driver.find_element(
            By.CSS_SELECTOR, ".tapestry-card-content .np-section.m-t-2 span[role='status']"
        )
        soup = BeautifulSoup(el.get_attribute("outerHTML"), "html.parser")
        time_str = soup.select_one("p.m-b-0 strong").text.strip().replace("by ", "")
        return {"bank": time_str}

    def scrape(self, send_currency: str, recv_currency: str, send_amount: Decimal) -> ProviderResult:
        corridor = f"{send_currency}-{recv_currency}"
        url = _CORRIDOR_URLS.get(corridor)
        if not url:
            msg = f"WiseSpider does not support corridor {corridor}"
            raise ValueError(msg)

        self.driver.get(url)
        self._select_currency(send_currency, "sourceSelectedCurrency", "sourceSelectedCurrencySearch")
        self._select_currency(recv_currency, "targetSelectedCurrency", "targetSelectedCurrencySearch")
        self._input_amount(send_amount)
        time.sleep(5)

        rate = self._extract_rate()
        fees = self._extract_fees()
        transfer_time = self._extract_transfer_time()
        receive = (send_amount - min(fees.values())) * rate if fees else send_amount * rate

        return ProviderResult(
            provider="Wise",
            corridor=corridor,
            send_amount=send_amount,
            exchange_rate=rate,
            fees=fees,
            transfer_time=transfer_time,
            receive_amount=receive.quantize(Decimal("0.00000001")),
            scraped_at=datetime.now(timezone.utc).isoformat(),
        )

    def close(self):
        self.driver.quit()
