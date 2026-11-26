import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import price_checker
import price_history


class PriceDropAlertTests(unittest.TestCase):
    def check_alert(self, *, old_low, expected_low, sale=False):
        url = "https://www.amazon.sa/dp/B000000001"
        original = 369.0 if sale else None
        discount = "-30%" if sale else None
        product = dict(name="Example", url=url, last_price=300.0,
                       original_price=original, discount_text=discount)
        info = dict(price="260.00 SAR", status="success",
                    original_price=original, discount_text=discount)
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(price_history, "HISTORY_FILE", Path(folder) / "history.db"),
            patch.object(price_checker, "load_products", return_value=[product]),
            patch.object(price_checker, "save_products"),
            patch.object(price_checker, "get_product_info", return_value=info),
            patch.object(price_checker, "send_telegram_message") as send,
        ):
            for price in (old_low, 262.0):
                price_history.record_price(url=url, name="Example", price=price, is_on_sale=sale)
            price_history.record_price(url=url, name="Example", price=1.0, scrape_status="failed")
            price_history.record_price(url=url + "2", name="Other", price=2.0)
            price_checker.check_prices()

        expected = [
            "📉 Price dropped",
            "",
            "💰 Current price: 260.00 SAR",
            "📉 Previous price: 262.00 SAR",
            "💵 Price drop savings: 2.00 SAR",
            f"📊 Lowest price in history: {expected_low} SAR",
        ]
        if sale:
            expected.extend([
                "🏷️ Original price: 369.00 SAR",
                "💸 You save: 109.00 SAR",
                "🔖 Discount: -30%",
            ])
        send.assert_called_once_with("\n".join(expected))

    def test_drop_during_sale(self):
        self.check_alert(old_low=249, expected_low="249.00", sale=True)

    def test_drop_without_sale(self):
        self.check_alert(old_low=245, expected_low="245.00")

    def test_drop_sets_new_low(self):
        self.check_alert(old_low=270, expected_low="260.00")
