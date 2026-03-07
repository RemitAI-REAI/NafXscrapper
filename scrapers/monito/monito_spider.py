import time
import re
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from bs4 import BeautifulSoup

from scrapers.models.base_page import BasePage
from scrapers.utils.utils import setup_drivver

# Monito: comparison aggregator - one scrape gives multiple providers
# URL: /send-money/usa/bangladesh/usd/1000
_URL = "https://www.monito.com/send-money/usa/bangladesh/usd/1000"


class MonitoSpider:
    def __init__(self):
        self.driver = setup_drivver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def wait_for_results(self):
        """Wait for comparison results to appear."""
        try:
            WebDriverWait(self.driver, 25).until(
                lambda d: len(d.find_elements(
                    By.CSS_SELECTOR,
                    "[class*='SearchResult'], [class*='result'], [class*='offer'], li[class*='search']"
                )) > 0
            )
        except Exception:
            pass

    def extract_results(self) -> list:
        """Extract list of provider comparison results."""
        results = []
        try:
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # Try multiple selector patterns Monito uses
            row_selectors = [
                {"tag": "li", "class_": lambda c: c and "search" in c.lower()},
                {"tag": "article"},
                {"tag": "div", "class_": lambda c: c and "result" in c.lower()},
            ]

            for sel in row_selectors:
                rows = soup.find_all(sel["tag"])
                for row in rows:
                    text = row.get_text(separator=" ").strip()
                    # Check if it looks like a rate row (has BDT and USD or a provider name)
                    if "BDT" in text and len(text) > 30:
                        results.append(text[:300])
                if results:
                    break

            if not results:
                # Fallback: scan for rate patterns
                src = self.driver.page_source
                matches = re.findall(r'[\d.,]+\s*BDT', src)
                results = [m for m in matches[:5]]

        except Exception:
            pass
        return results

    def scrape(self):
        """Scrape Monito comparison for USD $1000 → BDT."""
        self.driver.get(_URL)
        time.sleep(15)
        self.wait_for_results()

        comparison_results = self.extract_results()

        # Build a summary string
        if comparison_results:
            summary = " | ".join(comparison_results[:5])
        else:
            summary = "Comparison data not available (site may require JS rendering)"

        # Try to extract the top rate from results
        rate = "N/A"
        for r in comparison_results:
            match = re.search(r'[\d.,]+\s*BDT', r)
            if match:
                rate = f"Top rate: {match.group(0)} per USD 1000"
                break

        return {
            "exchange_rates": [{"pair": "USD/BDT", "rate": rate}],
            "transaction_fees": summary,
            "transfer_times": "Varies by provider",
            "provider": {"name": "Monito (aggregator)", "url": "https://www.monito.com"},
            "timestamp": datetime.now().isoformat(),
        }

    def close(self):
        self.driver.quit()
