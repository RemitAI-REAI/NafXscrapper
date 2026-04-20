from abc import ABC, abstractmethod
from decimal import Decimal

from scrapers.models.data_model import ProviderResult


class BaseScraper(ABC):
    """All provider spiders must implement this interface.

    scrape() is called once per corridor per run. close() is always called
    afterward, even on failure, so browser resources are released.
    """

    @abstractmethod
    def scrape(self, send_currency: str, recv_currency: str, send_amount: Decimal) -> ProviderResult:
        """Return a ProviderResult for the given corridor and send amount."""
        ...

    def close(self) -> None:
        """Release browser/session resources."""
