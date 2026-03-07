import time
from datetime import datetime

from selenium.webdriver import Keys, ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from scrapers.models.base_page import BasePage
from scrapers.utils.utils import setup_drivver

# Taptap Send: USD → BDT
# Their web shows rates on the Bangladesh landing page
_URL = "https://www.taptapsend.com/send-to/bangladesh"


class TaptapSpider:
    def __init__(self):
        self.driver = setup_drivver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def extract_rate(self) -> str:
        try:
            # Try common rate element patterns
            for selector in [
                "[class*='rate']", "[class*='exchange']", "[class*='Rate']",
                "[data-testid*='rate']", "[data-testid*='exchange']",
            ]:
                els = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in els:
                    t = el.text.strip()
                    if "BDT" in t or "USD" in t or "=" in t:
                        return t
            # Fallback: search page text for rate pattern
            import re
            src = self.driver.page_source
            match = re.search(r'1\s*USD\s*=\s*[\d.,]+\s*BDT', src)
            if match:
                return match.group(0)
            return "See Taptap Send app for live rates"
        except Exception:
            return "See Taptap Send app for live rates"

    def extract_fees(self) -> str:
        try:
            for selector in ["[class*='fee']", "[class*='Fee']", "[data-testid*='fee']"]:
                els = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in els:
                    t = el.text.strip()
                    if t and len(t) > 3:
                        return t
            return "0 USD (no transfer fee)"
        except Exception:
            return "0 USD (no transfer fee)"

    def extract_transfer_time(self) -> str:
        try:
            for selector in [
                "[class*='speed']", "[class*='delivery']", "[class*='time']",
                "[data-testid*='speed']", "[data-testid*='delivery']",
            ]:
                els = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in els:
                    t = el.text.strip()
                    if t and len(t) > 3:
                        return t
            return "Minutes (bank transfer: 1-2 days)"
        except Exception:
            return "Minutes (bank transfer: 1-2 days)"

    def scrape(self):
        """Scrape Taptap Send data for USD to BDT."""
        self.driver.get(_URL)
        time.sleep(8)

        rate = self.extract_rate()
        fees = self.extract_fees()
        transfer_time = self.extract_transfer_time()

        return {
            "exchange_rates": [{"pair": "USD/BDT", "rate": rate}],
            "transaction_fees": fees,
            "transfer_times": transfer_time,
            "provider": {"name": "Taptap Send", "url": "https://www.taptapsend.com"},
            "timestamp": datetime.now().isoformat(),
        }

    def close(self):
        self.driver.quit()
