import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import price_history
import price_checker
import storage
import wishlist
from dashboard_utils import chunk_products


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.products_file = Path(self.temp_dir.name) / "products.json"
        self.history_file = Path(self.temp_dir.name) / "history.db"
        self.products_file.write_text("[]", encoding="utf-8")
        self.storage_patch = patch.object(
            storage, "PRODUCTS_FILE", str(self.products_file)
        )
        self.history_patch = patch.object(
            price_history, "HISTORY_FILE", self.history_file
        )
        self.storage_patch.start()
        self.history_patch.start()

    def tearDown(self):
        self.storage_patch.stop()
        self.history_patch.stop()
        self.temp_dir.cleanup()

    def write_products(self, products):
        self.products_file.write_text(json.dumps(products), encoding="utf-8")

    def test_failed_scrape_keeps_last_valid_price(self):
        product = {
            "name": "Example",
            "url": "https://www.amazon.sa/dp/B000000001",
            "last_price": 100.0,
            "was_on_sale": True,
        }
        self.write_products([product])
        failed = {
            "title": "Title not found",
            "price": "Price not found",
            "status": "failed",
            "is_on_sale": False,
            "image_url": None,
        }
        with patch.object(price_checker, "get_product_info", return_value=failed):
            price_checker.check_prices()

        saved = storage.load_products()[0]
        self.assertEqual(saved["last_price"], 100.0)
        self.assertTrue(saved["was_on_sale"])
        self.assertEqual(
            price_history.count_products_with_price_drops([product["url"]]), 0
        )

    def test_successful_check_saves_product_image(self):
        product = {
            "name": "Example",
            "url": "https://www.amazon.sa/dp/B000000001",
            "last_price": 100.0,
            "was_on_sale": False,
        }
        self.write_products([product])
        product_info = {
            "title": "Example",
            "price": "100.00 SAR",
            "status": "success",
            "is_on_sale": False,
            "discount_text": None,
            "original_price": None,
            "image_url": "https://images.example.test/product.jpg",
        }
        with patch.object(
            price_checker, "get_product_info", return_value=product_info
        ):
            price_checker.check_prices()

        saved = storage.load_products()[0]
        self.assertEqual(saved["image_url"], product_info["image_url"])

    def test_successful_check_saves_discount_details(self):
        product = {
            "name": "Discounted product",
            "url": "https://www.amazon.sa/dp/B000000004",
            "last_price": 120.0,
            "was_on_sale": False,
        }
        self.write_products([product])
        product_info = {
            "title": "Discounted product",
            "price": "90.00 SAR",
            "status": "success",
            "is_on_sale": True,
            "discount_text": "-25%",
            "original_price": 120.0,
            "image_url": None,
        }
        with patch.object(
            price_checker, "get_product_info", return_value=product_info
        ), patch.object(price_checker, "send_telegram_message"):
            price_checker.check_prices()

        saved = storage.load_products()[0]
        self.assertEqual(saved["original_price"], 120.0)
        self.assertEqual(saved["discount_text"], "-25%")

    def test_empty_wishlist_does_not_erase_products(self):
        product = {
            "name": "Example",
            "url": "https://www.amazon.sa/dp/B000000001",
            "last_price": 100.0,
        }
        self.write_products([product])
        with patch.object(wishlist, "get_wishlist_links", return_value=[]):
            result = wishlist.sync_wishlist("https://example.test/list")

        self.assertFalse(result)
        self.assertEqual(storage.load_products(), [product])

    def test_history_statistics_ignore_failures(self):
        url = "https://www.amazon.sa/dp/B000000001"
        run_id = "shared-run"
        price_history.record_price(
            url=url, name="Example", price=100.0, run_id=run_id
        )
        price_history.record_price(
            url=url, name="Example", price=80.0, run_id=run_id
        )
        price_history.record_price(
            url=url, name="Example", price=None, scrape_status="failed",
            run_id=run_id,
        )
        stats = price_history.get_product_stats(url)
        self.assertEqual(stats["lowest_price"], 80.0)
        self.assertEqual(stats["highest_price"], 100.0)
        self.assertEqual(stats["average_price"], 90.0)
        self.assertEqual(stats["observations"], 2)

        rows = price_history.get_price_history(url)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[-1]["scrape_status"], "failed")

        health = price_history.get_tracker_health()
        self.assertEqual(health["checks"], 3)
        self.assertEqual(health["successful_checks"], 2)
        self.assertEqual(health["failed_checks"], 1)

        self.assertEqual(price_history.count_products_with_price_drops(), 1)

    def test_price_drop_count_ignores_unchanged_and_increased_prices(self):
        unchanged_url = "https://www.amazon.sa/dp/B000000002"
        increased_url = "https://www.amazon.sa/dp/B000000003"
        run_id = "unchanged-run"
        price_history.record_price(
            url=unchanged_url, name="Same", price=50.0, run_id=run_id
        )
        price_history.record_price(
            url=unchanged_url, name="Same", price=50.0, run_id=run_id
        )
        price_history.record_price(
            url=increased_url, name="Higher", price=20.0, run_id=run_id
        )
        price_history.record_price(
            url=increased_url, name="Higher", price=30.0, run_id=run_id
        )

        self.assertEqual(price_history.count_products_with_price_drops(), 0)

    def test_telegram_and_dashboard_use_same_price_drop_event(self):
        url = "https://www.amazon.sa/dp/B000000005"
        product = {
            "name": "Shared event product",
            "url": url,
            "last_price": 100.0,
            "was_on_sale": False,
        }
        self.write_products([product])
        product_info = {
            "title": product["name"],
            "price": "80.00 SAR",
            "status": "success",
            "is_on_sale": False,
            "discount_text": None,
            "original_price": None,
            "image_url": None,
        }
        with patch.object(
            price_checker, "get_product_info", return_value=product_info
        ), patch.object(
            price_checker, "create_run_id", return_value="unified-run"
        ), patch.object(price_checker, "send_telegram_message") as send_message:
            price_checker.check_prices()

        send_message.assert_called_once()
        rows = price_history.get_price_history(url)
        self.assertTrue(rows[-1]["price_dropped"])
        self.assertEqual(rows[-1]["previous_price"], 100.0)
        self.assertEqual(rows[-1]["price_change"], -20.0)
        self.assertEqual(
            price_history.count_products_with_price_drops([url]), 1
        )

    def test_removed_products_are_not_counted(self):
        active_url = "https://www.amazon.sa/dp/B000000006"
        removed_url = "https://www.amazon.sa/dp/B000000007"
        for url in (active_url, removed_url):
            price_history.record_price(
                url=url, name="Product", price=100.0, run_id="older-run"
            )
            price_history.record_price(
                url=url, name="Product", price=80.0, run_id="latest-run"
            )

        self.assertEqual(
            price_history.count_products_with_price_drops([active_url]), 1
        )

    def test_first_observation_does_not_create_false_events(self):
        event = price_history.record_price(
            url="https://www.amazon.sa/dp/B000000008",
            name="First observation",
            price=75.0,
            is_on_sale=True,
            run_id="first-run",
        )

        self.assertFalse(event["price_dropped"])
        self.assertFalse(event["sale_started"])
        self.assertIsNone(event["previous_price"])

    def test_existing_database_migrates_event_columns(self):
        with closing(sqlite3.connect(self.history_file)) as connection:
            connection.execute(
                """
                CREATE TABLE price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    name TEXT NOT NULL,
                    price REAL,
                    currency TEXT NOT NULL DEFAULT 'SAR',
                    is_on_sale INTEGER NOT NULL DEFAULT 0,
                    original_price REAL,
                    scrape_status TEXT NOT NULL,
                    checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()

        price_history.initialize_history()
        with closing(sqlite3.connect(self.history_file)) as connection:
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(price_history)")
            }

        self.assertTrue(set(price_history.EVENT_COLUMNS).issubset(columns))

    def test_twenty_products_form_seven_dashboard_rows(self):
        products = list(range(20))
        rows = chunk_products(products)

        self.assertEqual(len(rows), 7)
        self.assertEqual([len(row) for row in rows], [3, 3, 3, 3, 3, 3, 2])
        self.assertEqual([item for row in rows for item in row], products)


if __name__ == "__main__":
    unittest.main()
