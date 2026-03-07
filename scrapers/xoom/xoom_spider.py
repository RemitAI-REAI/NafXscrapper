import time
from datetime import datetime

from selenium.webdriver import Keys, ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from scrapers.models.base_page import BasePage
from scrapers.utils.utils import setup_drivver

# Xoom: USD → BDT, $1000, bank transfer
# URL pre-sets BDT as destination; source amount is set via input field
_URL = "https://www.xoom.com/bangladesh/send-money"


class XoomSpider:
    def __init__(self):
        self.driver = setup_drivver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def set_amount(self, amount: float):
        """Try to set the send amount to 1000 USD; skip gracefully if input not found."""
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

    def extract_exchange_rate(self) -> str:
        el = WebDriverWait(self.driver, 15).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='fx-rate-comparison-string']"))
        )
        return el.text.strip()

    def extract_receiving_amount(self) -> str:
        """Returns the BDT amount the recipient gets."""
        try:
            el = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, "[data-testid='destination-amount-input']")
                )
            )
            return el.get_attribute("value").strip() + " BDT"
        except Exception:
            return "N/A"

    def extract_fees(self) -> str:
        """Click 'Show Fees' to reveal fee breakdown, extract bank-deposit bank-account fee."""
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
            full_text = fee_el.text.strip()

            # Parse: find "Bank Deposit" section, then "Bank Account" line
            import re as _re
            bank_deposit_idx = full_text.find("Bank Deposit")
            if bank_deposit_idx >= 0:
                section = full_text[bank_deposit_idx: bank_deposit_idx + 300]
                # Find "Bank Account  X.XX" line within that section
                m = _re.search(r'Bank\s+Account\s+([\d.]+)', section)
                if m:
                    return f"Bank Deposit via Bank Account: {m.group(1)} USD"
                # Try any amount in that section
                m = _re.search(r'([\d.]+)\s*$', section.split('\n')[3] if '\n' in section else section)
                if m:
                    return f"Bank Deposit fee: {m.group(1)} USD"

            # Fallback: return first two meaningful lines
            lines = [l.strip() for l in full_text.split('\n') if l.strip() and not l.strip().lower().startswith('back')]
            return ' | '.join(lines[:4]) if lines else full_text[:150]
        except Exception:
            return "Fee details not available (see Xoom site)"

    def extract_transfer_time(self) -> str:
        try:
            el = self.driver.find_element(
                By.CSS_SELECTOR, "[data-testid='delivery-estimate'], [class*='delivery'], [class*='speed']"
            )
            return el.text.strip()
        except Exception:
            return "Minutes to hours"

    def scrape(self):
        """Scrape Xoom data for USD to BDT with 1000 amount."""
        self.driver.get(_URL)

        # Accept cookies if prompted
        try:
            accept_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[id*='accept'], button[class*='accept']"))
            )
            accept_btn.click()
        except Exception:
            pass

        # Wait for calculator to load
        WebDriverWait(self.driver, 15).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='calculator-section']"))
        )

        # Set amount to 1000
        self.set_amount(1000)

        exchange_rate = self.extract_exchange_rate()
        fees = self.extract_fees()
        transfer_time = self.extract_transfer_time()

        return {
            "exchange_rates": [{"pair": "USD/BDT", "rate": exchange_rate}],
            "transaction_fees": fees,
            "transfer_times": transfer_time,
            "provider": {"name": "Xoom", "url": "https://www.xoom.com"},
            "timestamp": datetime.now().isoformat(),
        }

    def close(self):
        self.driver.quit()
