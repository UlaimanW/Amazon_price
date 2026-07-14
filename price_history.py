import sqlite3
from contextlib import closing
from pathlib import Path


HISTORY_FILE = Path("price_history.db")


def initialize_history():
    with closing(sqlite3.connect(HISTORY_FILE)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history (
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
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_price_history_url_checked
            ON price_history (url, checked_at)
            """
        )
        connection.commit()


def record_price(
    *, url, name, price, is_on_sale=False, original_price=None,
    scrape_status="success"
):
    initialize_history()
    with closing(sqlite3.connect(HISTORY_FILE)) as connection:
        connection.execute(
            """
            INSERT INTO price_history (
                url, name, price, is_on_sale, original_price, scrape_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (url, name, price, int(is_on_sale), original_price, scrape_status),
        )
        connection.commit()


def get_product_stats(url):
    initialize_history()
    with closing(sqlite3.connect(HISTORY_FILE)) as connection:
        row = connection.execute(
            """
            SELECT MIN(price), MAX(price), AVG(price), COUNT(price)
            FROM price_history
            WHERE url = ? AND scrape_status = 'success' AND price IS NOT NULL
            """,
            (url,),
        ).fetchone()

    return {
        "lowest_price": row[0],
        "highest_price": row[1],
        "average_price": row[2],
        "observations": row[3],
    }


def get_price_history(url):
    initialize_history()
    with closing(sqlite3.connect(HISTORY_FILE)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT price, is_on_sale, original_price, scrape_status, checked_at
            FROM price_history
            WHERE url = ?
            ORDER BY checked_at, id
            """,
            (url,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_tracker_health():
    initialize_history()
    with closing(sqlite3.connect(HISTORY_FILE)) as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*),
                SUM(CASE WHEN scrape_status = 'success' THEN 1 ELSE 0 END),
                MAX(checked_at)
            FROM price_history
            """
        ).fetchone()

    total = row[0] or 0
    successful = row[1] or 0
    return {
        "checks": total,
        "successful_checks": successful,
        "failed_checks": total - successful,
        "last_check": row[2],
    }


def count_products_with_price_drops():
    initialize_history()
    with closing(sqlite3.connect(HISTORY_FILE)) as connection:
        rows = connection.execute(
            """
            SELECT url, price
            FROM price_history
            WHERE scrape_status = 'success' AND price IS NOT NULL
            ORDER BY url, id DESC
            """
        ).fetchall()

    latest_prices = {}
    previous_prices = {}
    for url, price in rows:
        if url not in latest_prices:
            latest_prices[url] = price
        elif url not in previous_prices:
            previous_prices[url] = price

    return sum(
        latest_prices[url] < previous_price
        for url, previous_price in previous_prices.items()
    )
