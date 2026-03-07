from dataclasses import dataclass
from typing import Dict, List


@dataclass
class TransferData:
    exchange_rates: List[Dict[str, str]]
    transaction_fees: str
    transfer_time: str
    provider: Dict[str,str]
    timestamp: str

    def to_dict(self) -> Dict:
        return {
            "exchange_rates": self.exchange_rates,
            "transaction_fees": self.transaction_fees,
            "transfer_times": self.transfer_time,
            "provider": self.provider,
            "timestamp": self.timestamp
        }

