import time
import re
from datetime import datetime

from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from scrapers.models.base_page import BasePage
from scrapers.utils.utils import setup_drivver

# MoneyGram Bangladesh corridor landing page — shows rate + fee without login
_URL = "https://www.moneygram.com/us/en/corridor/bangladesh"


class MoneyGramSpider:
    def __init__(self):
        self.driver = setup_drivver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def set_amount(self, amount: float):
        """Set the send amount if the calculator input is available."""
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

    def extract_rate(self) -> str:
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            # Page shows "1 USD =\n121.28\n123.27 BDT" — two rates (standard + promo)
            bdt_matches = re.findall(r'([\d.,]+)\s*BDT', body_text)
            if bdt_matches:
                return f"1 USD = {bdt_matches[0]} BDT"
            src = self.driver.page_source
            m = re.search(r'([\d.,]+)\s*BDT', src)
            if m:
                return f"1 USD = {m.group(1)} BDT"
            return "N/A"
        except Exception:
            return "N/A"

    def extract_fees(self) -> str:
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            # "Fees1\n5.49 USD\n0.00 USD" pattern — first USD amount after "Fees"
            fee_match = re.search(r'Fees?\d*\s*([\d.,]+)\s*USD', body_text, re.IGNORECASE)
            if fee_match:
                return f"{fee_match.group(1)} USD"
            usd_amounts = re.findall(r'([\d.,]+)\s*USD', body_text)
            if usd_amounts:
                return f"{usd_amounts[0]} USD"
            return "See MoneyGram site for fee details"
        except Exception:
            return "See MoneyGram site for fee details"

    def extract_transfer_time(self) -> str:
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if re.search(r'\binstant\b', body_text, re.IGNORECASE):
                return "Instant (bank account/mobile wallet)"
            match = re.search(
                r'(\d+[-\u2013]\d+\s*(?:business\s*)?(?:minute|hour|day)s?'
                r'|\d+\s*(?:business\s*)?(?:minute|hour|day)s?)',
                body_text, re.IGNORECASE
            )
            if match:
                return match.group(0)
            return "Minutes to hours"
        except Exception:
            return "Minutes to hours"

    def scrape(self):
        """Scrape MoneyGram USD to BDT from the Bangladesh corridor page."""
        self.driver.get(_URL)
        WebDriverWait(self.driver, 20).until(
            lambda d: "BDT" in d.find_element(By.TAG_NAME, "body").text
        )
        time.sleep(3)

        self.set_amount(1000)

        rate = self.extract_rate()
        fees = self.extract_fees()
        transfer_time = self.extract_transfer_time()

        return {
            "exchange_rates": [{"pair": "USD/BDT", "rate": rate}],
            "transaction_fees": fees,
            "transfer_times": transfer_time,
            "provider": {"name": "MoneyGram", "url": "https://www.moneygram.com"},
            "timestamp": datetime.now().isoformat(),
        }

    def close(self):
        self.driver.quit()
