import time
from datetime import datetime

from bs4 import BeautifulSoup
from selenium.webdriver import Keys, ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
import re
from scrapers.models.base_page import BasePage
from scrapers.utils.utils import setup_drivver


class WiseSpider:
    def __init__(self):
        self.driver = setup_drivver(headless=True)
        self.driver.implicitly_wait(5)
        self.page = BasePage(self.driver)

    def select_currency(self, currency: str, button_id: str, search_id: str):
        button = WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.ID, button_id))
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        time.sleep(0.5)
        self.driver.execute_script("arguments[0].click();", button)
        input_currency_field = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.ID, search_id))
        )
        input_currency_field.send_keys(currency)
        input_currency_field.send_keys(Keys.ENTER)

    def input_amount(self, amount: float):
        input_field_selected = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR,"input#source"))
        )
        actions = ActionChains(self.driver)
        actions.click(input_field_selected).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(
            Keys.DELETE).perform()
        input_field_selected.send_keys(amount)


    def extract_exchange_rate(self) -> str:
        exchange_rate_button = WebDriverWait(self.driver, 15).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "button[aria-describedby='rateLabel']"))
        )
        return exchange_rate_button.text.strip()

    def extract_transaction_fees(self) -> str:
        fees_container = WebDriverWait(self.driver, 20).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".Fees_container"))
        )
        text = fees_container.text.strip()
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        # Pair label lines with their following USD amount lines
        fees = []
        i = 0
        while i < len(lines) - 1:
            curr = lines[i]
            nxt = lines[i + 1]
            if not re.match(r'^[\d.,]+', curr) and re.match(r'^[\d.,]+\s*USD', nxt):
                fees.append(f"{curr}: {nxt}")
                i += 2
            else:
                i += 1

        usd_amounts = re.findall(r'[\d.,]+\s*USD', text)
        pct = re.search(r'([\d.,]+%)', text)
        total = usd_amounts[-1] if usd_amounts else None
        pct_str = pct.group(1) if pct else None

        result = ', '.join(fees)
        if total:
            result += f', Total: {total}'
        if pct_str:
            result += f', Percentage: {pct_str}'
        return result or text[:200]

    def extract_transfer_time(self) -> str:
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".np-section.m-t-2"))
        )
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".np-section.m-t-2 p.m-b-0 strong"))
        )
        transfer_time_container = self.driver.find_element(By.CSS_SELECTOR, ".tapestry-card-content .np-section.m-t-2 span[role='status']")
        transfer_time_html = transfer_time_container.get_attribute("outerHTML")
        soup = BeautifulSoup(transfer_time_html, "html.parser")
        transfer_time = soup.select_one("p.m-b-0 strong").text.strip()
        return transfer_time.replace("by ", "")



    def scrape(self):
        """Scrape Wise data for USD to BDT with 1000 amount."""
        self.driver.get("https://wise.com/us/pricing/send-money?source=USD&target=BDT&payInMethod=BANK_TRANSFER&sourceAmount=1000")

        # Select currencies
        self.select_currency("USD", "sourceSelectedCurrency", "sourceSelectedCurrencySearch")
        self.select_currency("BDT", "targetSelectedCurrency", "targetSelectedCurrencySearch")

        # Input amount
        self.input_amount(1000)

        # Extract data
        time.sleep(5)  # delay for UI stability
        exchange_rate = self.extract_exchange_rate()
        transaction_fees = self.extract_transaction_fees()
        transfer_time = self.extract_transfer_time()

        return {
            "exchange_rates": [{"pair": "USD/BDT", "rate": exchange_rate}],
            "transaction_fees": transaction_fees,
            "transfer_times": transfer_time,
            "provider": {"name": "Wise", "url": "https://wise.com"},
            "timestamp": datetime.now().isoformat()
        }

    def close(self):
        self.driver.quit()
