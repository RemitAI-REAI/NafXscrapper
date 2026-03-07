import time
import re
from datetime import datetime

from selenium.webdriver import Keys, ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from scrapers.models.base_page import BasePage
from scrapers.utils.utils import setup_drivver

# Remitly: USD → BDT calculator page
# Using the public corridor page that shows rates without login
_URL = "https://www.remitly.com/us/en/bangladesh"


class RemitlySpider:
    def __init__(self):
        self.driver = setup_drivver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def set_amount(self, amount: float):
        """Enter 1000 in the send amount field."""
        for selector in [
            "input[data-testid='send-amount-input']",
            "input[data-testid='calculator-send-amount']",
            "input[id*='sendAmount']",
            "input[name*='sendAmount']",
            "input[placeholder*='1,000']",
            "input[class*='send'][type='number']",
            "input[class*='send'][type='text']",
        ]:
            try:
                field = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                actions = ActionChains(self.driver)
                actions.click(field).key_down(Keys.CONTROL).send_keys("a").key_up(
                    Keys.CONTROL
                ).send_keys(str(int(amount))).perform()
                field.send_keys(Keys.TAB)
                time.sleep(3)
                return True
            except Exception:
                continue
        return False

    def extract_rate(self) -> str:
        try:
            # Common Remitly data-testid selectors
            for selector in [
                "[data-testid='exchange-rate']",
                "[data-testid='fx-rate']",
                "[data-testid='calculator-rate']",
                "[data-testid*='rate']",
                "[class*='ExchangeRate']",
                "[class*='exchangeRate']",
                "[class*='fx-rate']",
            ]:
                els = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in els:
                    t = el.text.strip()
                    if t and ("BDT" in t or "=" in t):
                        return t

            # Fallback: regex scan of page source
            src = self.driver.page_source
            match = re.search(r'1\s*USD\s*=\s*[\d.,]+\s*BDT', src)
            if match:
                return match.group(0)
            return "N/A"
        except Exception:
            return "N/A"

    def extract_fees(self) -> str:
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            if re.search(r'\bno\s+fee\b|\bfree\s+transfer\b|\bno\s+transfer\s+fee\b', body_text, re.IGNORECASE):
                return "0.00 USD (no fee)"
            match = re.search(r'([\d.,]+)\s*USD\s*(?:fee|transfer fee)', body_text, re.IGNORECASE)
            if match:
                return f"{match.group(1)} USD"
            match = re.search(r'(?:fee|transfer fee)[s]?\s*[:\-]?\s*([\d.,]+)\s*USD', body_text, re.IGNORECASE)
            if match:
                return f"{match.group(1)} USD"
            for selector in ["[data-testid*='fee']", "[class*='fee']"]:
                els = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in els:
                    t = el.text.strip()
                    if t and len(t) > 2 and re.search(r'\d', t):
                        return t
            return "See Remitly site for fee details"
        except Exception:
            return "See Remitly site for fee details"

    def extract_transfer_time(self) -> str:
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            match = re.search(
                r'(?:in\s+)?(\d+[-–]\d+\s*(?:business\s*)?(?:minute|hour|day)s?'
                r'|\d+\s*(?:business\s*)?(?:minute|hour|day)s?'
                r'|[Ii]n\s+minutes?|[Ii]n\s+hours?)',
                body_text
            )
            if match:
                return match.group(0)
            for selector in ["[data-testid*='delivery']", "[data-testid*='time']", "[class*='delivery']"]:
                els = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in els:
                    t = el.text.strip()
                    if t and any(k in t.lower() for k in ["minute", "hour", "day"]):
                        return t
            return "Minutes to hours"
        except Exception:
            return "Minutes to hours"

    def scrape(self):
        """Scrape Remitly USD to BDT rate for $1000."""
        self.driver.get(_URL)
        time.sleep(8)

        # Set amount
        self.set_amount(1000)

        rate = self.extract_rate()
        fees = self.extract_fees()
        transfer_time = self.extract_transfer_time()

        return {
            "exchange_rates": [{"pair": "USD/BDT", "rate": rate}],
            "transaction_fees": fees,
            "transfer_times": transfer_time,
            "provider": {"name": "Remitly", "url": "https://www.remitly.com"},
            "timestamp": datetime.now().isoformat(),
        }

    def close(self):
        self.driver.quit()
