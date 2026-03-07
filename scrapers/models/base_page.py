from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait
from tenacity import stop_after_attempt, wait_exponential, retry


class BasePage:
    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def wait_for_element(self, by: str, value: str):
        try:
            return self.wait.until(EC.presence_of_element_located((by, value)))
        except TimeoutException:
            raise NoSuchElementException("Element {value} not found")

    def get_text(self, by: str, value: str) -> str:
        element = self.wait_for_element(by, value)
        return element.text.strip()

    def click_element(self, by: str, value: str):
        element = self.wait_for_element(by, value)
        element.click()

    def send_keys_to_element(self, by: str, value: str, keys: str):
        element = self.wait_for_element(by, value)
        element.send_keys(keys)