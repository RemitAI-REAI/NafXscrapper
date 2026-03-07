import time
import re
from datetime import datetime

from selenium.webdriver import Keys, ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from scrapers.models.base_page import BasePage
from scrapers.utils.utils import setup_drivver

# Western Union: USD → BDT, $1000
# The /web/send-money/start page supports country selection and renders rates
_URL = "https://www.westernunion.com/us/en/web/send-money/start"


class WesternUnionSpider:
    def __init__(self):
        self.driver = setup_drivver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def select_country_bangladesh(self) -> bool:
        """Type Bangladesh in the country input and wait for calculator to load."""
        try:
            country_input = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.ID, "country"))
            )
            country_input.clear()
            country_input.send_keys("Bangladesh")
            country_input.send_keys(Keys.RETURN)
            # Wait for BDT to appear in the page (confirms Bangladesh is loaded)
            WebDriverWait(self.driver, 15).until(
                lambda d: "BDT" in d.find_element(By.TAG_NAME, "body").text
            )
            return True
        except Exception:
            return False

    def enter_send_amount(self, amount: float):
        """Enter the send amount (USD)."""
        try:
            field = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "txtSendAmount"))
            )
            field.clear()
            field.send_keys(str(int(amount)))
            time.sleep(2)
        except Exception:
            pass

    def select_bank_account_payout(self) -> bool:
        """Click the 'Bank account' payout method to reveal the exchange rate."""
        for xpath in [
            "//span[normalize-space()='Bank account']",
            "//*[contains(text(),'Bank account') and not(contains(text(),'How'))]",
            "//span[normalize-space()='Cash pick up']",
        ]:
            try:
                el = WebDriverWait(self.driver, 8).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", el)
                self.driver.execute_script("arguments[0].click();", el)
                time.sleep(8)  # longer wait for rate to populate
                return True
            except Exception:
                continue
        return False

    def extract_rate(self) -> str:
        """Extract rate from visible page text or embedded JSON."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            # "1.00 USD = 122.8920" pattern in visible text
            match = re.search(r'1\.?\d*\s*USD\s*=\s*([\d.,]+)', body_text)
            if match:
                rate_num = match.group(1).replace(",", "")
                return f"1 USD = {rate_num} BDT"
            # "122.8920 BDT" pattern (rate before "BDT")
            match = re.search(r'([\d]{2,4}\.[\d]{2,4})\s*BDT', body_text)
            if match:
                return f"1 USD = {match.group(1)} BDT"
            # JSON in page source: "exchangeRate":122.89 or "transferRate":122
            src = self.driver.page_source
            for pat in [
                r'"exchangeRate"\s*:\s*([\d.]+)',
                r'"transferRate"\s*:\s*([\d.]+)',
                r'"fxRate"\s*:\s*([\d.]+)',
                r'1\s*USD\s*=\s*[\d.,]+\s*BDT',
            ]:
                m = re.search(pat, src)
                if m:
                    val = m.group(1) if m.lastindex else m.group(0)
                    if '.' in val and float(val) > 50:
                        return f"1 USD = {val} BDT"
                    if 'BDT' in val:
                        return val
            return "N/A"
        except Exception:
            return "N/A"

    def extract_fees(self) -> str:
        """Extract fee for bank account transfer — look in bank-account section."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            # The body lists: Credit Card, Debit Card, Bank account sections.
            # We want the LAST "Bank account" section's fee (0.00 for ACH).
            bank_idx = body_text.rfind("Bank account")
            if bank_idx > 0:
                section = body_text[bank_idx: bank_idx + 200]
                fee_match = re.search(r'Fee\S*\s+([\d.,]+)\s*USD', section, re.IGNORECASE)
                if fee_match:
                    return f"{fee_match.group(1)} USD (bank account)"
            # Fallback: all fee matches — take the last one (likely bank account)
            fee_matches = re.findall(
                r'(?:Fee\S*)\s+([\d.,]+)\s*USD', body_text, re.IGNORECASE
            )
            if fee_matches:
                # Return the last fee (closest to bank account listing)
                return f"{fee_matches[-1]} USD"

            # Generic fee search
            match = re.search(r'(?:fee|charge)\s*:?\s*\$?([\d.,]+)\s*USD', body_text, re.IGNORECASE)
            if match:
                return f"{match.group(1)} USD"
            return "See Western Union site for fee details"
        except Exception:
            return "See Western Union site for fee details"

    def extract_transfer_time(self) -> str:
        """Extract bank-account transfer time from visible page text."""
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            # Look in the Bank account payment method section (last occurrence)
            bank_idx = body_text.rfind("Bank account")
            if bank_idx > 0:
                section = body_text[bank_idx: bank_idx + 150]
                match = re.search(
                    r'(\d+[-–]\d+\s*(?:Business\s*)?[Dd]ays?|\d+\s*(?:Business\s*)?[Dd]ays?)',
                    section
                )
                if match:
                    return match.group(0)
            # Fallback: find last days-range pattern (bank account tends to be longest)
            all_matches = re.findall(
                r'\d+[-–]\d+\s*(?:Business\s*)?[Dd]ays?|\d+\s*(?:Business\s*)?[Dd]ays?',
                body_text, re.IGNORECASE
            )
            if all_matches:
                return all_matches[-1]  # Last match typically = bank account
            return "Minutes to 1 business day"
        except Exception:
            return "Minutes to 1 business day"

    def scrape(self):
        """Scrape Western Union USD to BDT rate for $1000."""
        self.driver.get(_URL)
        time.sleep(18)  # Angular app needs time to fully render

        # Step 1: Select Bangladesh
        country_ok = self.select_country_bangladesh()
        if not country_ok:
            return {
                "exchange_rates": [{"pair": "USD/BDT", "rate": "N/A"}],
                "transaction_fees": "See Western Union site for fee details",
                "transfer_times": "Minutes to 1 business day",
                "provider": {"name": "Western Union", "url": "https://www.westernunion.com"},
                "timestamp": datetime.now().isoformat(),
            }

        # Step 2: Enter 1000 send amount
        self.enter_send_amount(1000)

        # Step 3: Select bank account payout to reveal exchange rate
        self.select_bank_account_payout()

        # Step 4: Extract data
        rate = self.extract_rate()
        fees = self.extract_fees()
        transfer_time = self.extract_transfer_time()

        return {
            "exchange_rates": [{"pair": "USD/BDT", "rate": rate}],
            "transaction_fees": fees,
            "transfer_times": transfer_time,
            "provider": {"name": "Western Union", "url": "https://www.westernunion.com"},
            "timestamp": datetime.now().isoformat(),
        }

    def close(self):
        self.driver.quit()
