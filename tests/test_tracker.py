import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

import price_history
import price_checker
import scraper
import storage
import wishlist
from dashboard_utils import build_price_timeline, chunk_products, filter_products


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

    def wishlist_response(self, fixture_name, url):
        fixture = Path(__file__).parent / "fixtures" / fixture_name
        response = Mock(
            status_code=200,
            url=url,
            text=fixture.read_text(encoding="utf-8"),
        )
        response.raise_for_status.return_value = None
        return response

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
            "availability": "in_stock",
        }
        with patch.object(
            price_checker, "get_product_info", return_value=product_info
        ):
            price_checker.check_prices()

        saved = storage.load_products()[0]
        self.assertEqual(saved["image_url"], product_info["image_url"])
        self.assertEqual(saved["availability"], "in_stock")

    def test_availability_detection_from_saved_html(self):
        fixture_directory = Path(__file__).parent / "fixtures"
        cases = {
            "availability_in_stock.html": "in_stock",
            "availability_out_of_stock.html": "out_of_stock",
            "availability_temporary.html": "temporarily_unavailable",
            "availability_other_sellers.html": "available_from_other_sellers",
        }

        for filename, expected in cases.items():
            with self.subTest(filename=filename):
                html_text = (fixture_directory / filename).read_text(
                    encoding="utf-8"
                )
                soup = BeautifulSoup(html_text, "html.parser")
                self.assertEqual(scraper.detect_availability(soup), expected)

    def test_small_unavailable_page_is_not_treated_as_blocked(self):
        html_text = (
            '<html><body><span id="productTitle">Unavailable product</span>'
            '<div id="availability">Currently unavailable.</div></body></html>'
        )
        response = Mock(
            status_code=200,
            url="https://www.amazon.sa/dp/B000000010",
            text=html_text,
        )
        response.raise_for_status.return_value = None

        with patch.object(scraper.requests, "get", return_value=response):
            result = scraper.get_product_info(response.url, max_attempts=1)

        self.assertEqual(result["status"], "availability_only")
        self.assertEqual(result["availability"], "out_of_stock")

    def test_availability_only_check_preserves_price_and_alerts_on_return(self):
        product = {
            "name": "Returning product",
            "url": "https://www.amazon.sa/dp/B000000009",
            "last_price": 100.0,
            "was_on_sale": False,
            "availability": "out_of_stock",
        }
        self.write_products([product])
        product_info = {
            "title": product["name"],
            "price": "Price not found",
            "status": "availability_only",
            "availability": "in_stock",
            "is_on_sale": False,
            "discount_text": None,
            "original_price": None,
            "image_url": None,
        }

        with patch.object(
            price_checker, "get_product_info", return_value=product_info
        ), patch.object(price_checker, "send_telegram_message") as send_message:
            price_checker.check_prices()

        saved = storage.load_products()[0]
        self.assertEqual(saved["last_price"], 100.0)
        self.assertEqual(saved["availability"], "in_stock")
        send_message.assert_called_once()

        rows = price_history.get_price_history(product["url"])
        self.assertTrue(rows[-1]["back_in_stock"])
        self.assertEqual(rows[-1]["scrape_status"], "availability_only")

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
        empty_result = wishlist.WishlistResult([], True, 1)
        with patch.object(
            wishlist, "get_wishlist_links", return_value=empty_result
        ):
            result = wishlist.sync_wishlist("https://example.test/list")

        self.assertFalse(result)
        self.assertEqual(storage.load_products(), [product])

    def test_multi_page_wishlist_is_complete_and_deduplicated(self):
        base = "https://www.amazon.sa/hz/wishlist/ls/TEST?page=1"
        responses = [
            self.wishlist_response("wishlist_page_1.html", base),
            self.wishlist_response(
                "wishlist_page_2.html",
                "https://www.amazon.sa/hz/wishlist/ls/TEST?page=2",
            ),
            self.wishlist_response(
                "wishlist_page_3.html",
                "https://www.amazon.sa/hz/wishlist/ls/TEST?page=3",
            ),
        ]
        with patch.object(wishlist.requests, "get", side_effect=responses):
            result = wishlist.get_wishlist_links(base)

        self.assertTrue(result.complete)
        self.assertEqual(result.pages, 3)
        self.assertEqual(len(result.links), 4)
        self.assertEqual(len(result.links), len(set(result.links)))

    def test_single_page_wishlist_is_complete(self):
        url = "https://www.amazon.sa/hz/wishlist/ls/TEST"
        response = self.wishlist_response("wishlist_page_3.html", url)
        with patch.object(wishlist.requests, "get", return_value=response):
            result = wishlist.get_wishlist_links(url)

        self.assertTrue(result.complete)
        self.assertEqual(result.pages, 1)
        self.assertEqual(result.links, ["https://www.amazon.sa/dp/B000000104"])

    def test_wishlist_page_limit_prevents_partial_sync(self):
        url = "https://www.amazon.sa/hz/wishlist/ls/TEST?page=1"
        response = self.wishlist_response("wishlist_page_1.html", url)
        with patch.object(wishlist.requests, "get", return_value=response):
            result = wishlist.get_wishlist_links(url, max_pages=1)

        self.assertFalse(result.complete)
        self.assertIn("maximum", result.error.lower())

    def test_failed_second_wishlist_page_is_incomplete(self):
        base = "https://www.amazon.sa/hz/wishlist/ls/TEST?page=1"
        first_page = self.wishlist_response("wishlist_page_1.html", base)
        with patch.object(
            wishlist.requests,
            "get",
            side_effect=[first_page, wishlist.requests.exceptions.Timeout()],
        ):
            result = wishlist.get_wishlist_links(base)

        self.assertFalse(result.complete)
        self.assertEqual(result.pages, 1)
        self.assertEqual(len(result.links), 2)

    def test_incomplete_pagination_keeps_existing_products(self):
        tracked = [
            {
                "name": "Existing product",
                "url": "https://www.amazon.sa/dp/B000000101",
                "last_price": 100.0,
            }
        ]
        self.write_products(tracked)
        incomplete = wishlist.WishlistResult(
            links=[], complete=False, pages=1, error="Second page failed"
        )
        with patch.object(
            wishlist, "get_wishlist_links", return_value=incomplete
        ):
            result = wishlist.sync_wishlist(
                "https://www.amazon.sa/hz/wishlist/ls/TEST"
            )

        self.assertFalse(result)
        self.assertEqual(storage.load_products(), tracked)

    def test_wishlist_pagination_loop_is_incomplete(self):
        first_url = "https://www.amazon.sa/hz/wishlist/ls/TEST?page=1"
        second_url = "https://www.amazon.sa/hz/wishlist/ls/TEST?page=2"
        responses = [
            self.wishlist_response("wishlist_page_1.html", first_url),
            self.wishlist_response("wishlist_loop_page.html", second_url),
        ]
        with patch.object(wishlist.requests, "get", side_effect=responses):
            result = wishlist.get_wishlist_links(first_url)

        self.assertFalse(result.complete)
        self.assertIn("loop", result.error.lower())

    def test_wishlist_captcha_is_incomplete(self):
        url = "https://www.amazon.sa/hz/wishlist/ls/TEST"
        response = self.wishlist_response("wishlist_captcha.html", url)
        with patch.object(wishlist.requests, "get", return_value=response):
            result = wishlist.get_wishlist_links(url)

        self.assertFalse(result.complete)
        self.assertIn("captcha", result.error.lower())

    def test_external_wishlist_next_page_is_rejected(self):
        url = "https://www.amazon.sa/hz/wishlist/ls/TEST"
        response = self.wishlist_response("wishlist_external_next.html", url)
        with patch.object(wishlist.requests, "get", return_value=response):
            result = wishlist.get_wishlist_links(url)

        self.assertFalse(result.complete)
        self.assertIn("unsafe", result.error.lower())

    def test_suspicious_wishlist_reduction_keeps_existing_products(self):
        tracked = [
            {
                "name": f"Product {index}",
                "url": f"https://www.amazon.sa/dp/B00000010{index}",
                "last_price": 100.0,
            }
            for index in range(1, 5)
        ]
        self.write_products(tracked)
        suspicious = wishlist.WishlistResult([tracked[0]["url"]], True, 1)
        with patch.object(
            wishlist, "get_wishlist_links", return_value=suspicious
        ):
            result = wishlist.sync_wishlist(
                "https://www.amazon.sa/hz/wishlist/ls/TEST"
            )

        self.assertFalse(result)
        self.assertEqual(storage.load_products(), tracked)

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

    def test_sale_ending_requires_two_checks_and_alerts_once(self):
        url = "https://www.amazon.sa/dp/B000000011"
        product = {
            "name": "Sale ending product",
            "url": url,
            "last_price": 90.0,
            "was_on_sale": True,
        }
        self.write_products([product])
        price_history.record_price(
            url=url,
            name=product["name"],
            price=90.0,
            is_on_sale=True,
            run_id="sale-baseline",
        )
        regular_price = {
            "title": product["name"],
            "price": "120.00 SAR",
            "status": "success",
            "availability": "in_stock",
            "is_on_sale": False,
            "discount_text": None,
            "original_price": None,
            "image_url": None,
        }

        with patch.object(
            price_checker, "get_product_info", return_value=regular_price
        ), patch.object(price_checker, "send_telegram_message") as send_message:
            price_checker.check_prices()
            send_message.assert_not_called()

            price_checker.check_prices()
            send_message.assert_called_once()
            self.assertIn("Sale ended", send_message.call_args.args[0])
            self.assertIn("Previous sale price: 90.00 SAR", send_message.call_args.args[0])

            price_checker.check_prices()
            send_message.assert_called_once()

        rows = price_history.get_price_history(url)
        self.assertEqual(
            [row["sale_end_streak"] for row in rows[-3:]], [1, 2, 3]
        )
        self.assertEqual(
            [bool(row["sale_ended"]) for row in rows[-3:]],
            [False, True, False],
        )

    def test_sale_return_resets_pending_confirmation(self):
        url = "https://www.amazon.sa/dp/B000000012"
        price_history.record_price(
            url=url, name="Returning sale", price=90.0,
            is_on_sale=True, run_id="sale-baseline",
        )
        first_event = price_history.record_price(
            url=url, name="Returning sale", price=120.0,
            is_on_sale=False, run_id="sale-missing-once",
        )
        returned_event = price_history.record_price(
            url=url, name="Returning sale", price=90.0,
            is_on_sale=True, run_id="sale-returned",
        )

        self.assertEqual(first_event["sale_end_streak"], 1)
        self.assertFalse(first_event["sale_ended"])
        self.assertEqual(returned_event["sale_end_streak"], 0)
        self.assertFalse(returned_event["sale_ended"])

    def test_failed_scrape_does_not_advance_sale_end_confirmation(self):
        url = "https://www.amazon.sa/dp/B000000013"
        price_history.record_price(
            url=url, name="Failed check", price=90.0,
            is_on_sale=True, run_id="sale-baseline",
        )
        first_event = price_history.record_price(
            url=url, name="Failed check", price=120.0,
            is_on_sale=False, run_id="sale-missing-once",
        )
        failed_event = price_history.record_price(
            url=url, name="Failed check", price=None,
            scrape_status="failed", run_id="failed-run",
        )

        self.assertEqual(first_event["sale_end_streak"], 1)
        self.assertEqual(failed_event["sale_end_streak"], 0)
        latest = price_history.get_latest_successful_observation(url)
        self.assertEqual(latest["sale_end_streak"], 1)

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

    def test_price_timeline_builds_events_and_ignores_failures(self):
        rows = [
            {
                "checked_at": "2026-07-15 09:00:00",
                "price": 100.0,
                "scrape_status": "success",
                "previous_price": None,
                "price_change": None,
                "price_dropped": 0,
                "sale_started": 0,
                "sale_ended": 0,
            },
            {
                "checked_at": "2026-07-15 10:00:00",
                "price": 80.0,
                "scrape_status": "success",
                "previous_price": 100.0,
                "price_change": -20.0,
                "price_dropped": 1,
                "sale_started": 1,
                "sale_ended": 0,
            },
            {
                "checked_at": "2026-07-15 11:00:00",
                "price": None,
                "scrape_status": "failed",
                "previous_price": 80.0,
                "price_change": None,
                "price_dropped": 0,
                "sale_started": 0,
                "sale_ended": 0,
            },
            {
                "checked_at": "2026-07-15 12:00:00",
                "price": 110.0,
                "scrape_status": "success",
                "previous_price": 80.0,
                "price_change": 30.0,
                "price_dropped": 0,
                "sale_started": 0,
                "sale_ended": 1,
            },
        ]

        observations, events = build_price_timeline(rows)

        self.assertEqual(len(observations), 3)
        self.assertEqual(
            [event["event"] for event in events],
            ["Price dropped", "Sale started", "Price increased", "Sale ended"],
        )
        self.assertTrue(all(event["price"] is not None for event in events))

    def test_price_timeline_does_not_invent_old_events(self):
        observations, events = build_price_timeline([{
            "checked_at": "2026-07-15 09:00:00",
            "price": 100.0,
            "scrape_status": "success",
            "previous_price": None,
            "price_change": None,
            "price_dropped": 0,
            "sale_started": 0,
            "sale_ended": 0,
        }])

        self.assertEqual(len(observations), 1)
        self.assertEqual(events, [])

    def test_dashboard_search_filters_products(self):
        products = [
            {
                "name": "Gaming Headphones",
                "url": "https://www.amazon.sa/dp/B000000201",
                "last_price": 200.0,
                "original_price": 400.0,
                "was_on_sale": True,
            },
            {
                "name": "Office Headphones",
                "url": "https://www.amazon.sa/dp/B000000202",
                "last_price": 100.0,
                "original_price": 120.0,
                "was_on_sale": True,
            },
            {
                "name": "Gaming Mouse",
                "url": "https://www.amazon.sa/dp/B000000203",
                "last_price": 50.0,
                "was_on_sale": False,
            },
        ]

        result = filter_products(
            products,
            search="headphones",
            sort_by="Largest discount",
        )

        self.assertEqual(result, [products[0], products[1]])

    def test_dashboard_product_sorting(self):
        products = [
            {"name": "Expensive", "last_price": 300.0},
            {"name": "Cheap", "last_price": 50.0},
            {"name": "Middle", "last_price": 120.0},
        ]

        result = filter_products(products, sort_by="Price: lowest first")

        self.assertEqual(
            [product["name"] for product in result],
            ["Cheap", "Middle", "Expensive"],
        )


if __name__ == "__main__":
    unittest.main()
