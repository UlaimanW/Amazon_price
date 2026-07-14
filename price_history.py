import sqlite3
import uuid
from contextlib import closing
from pathlib import Path


HISTORY_FILE = Path("price_history.db")

EVENT_COLUMNS = {
    "run_id": "TEXT",
    "previous_price": "REAL",
    "price_change": "REAL",
    "price_dropped": "INTEGER NOT NULL DEFAULT 0",
    "sale_started": "INTEGER NOT NULL DEFAULT 0",
}


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
                run_id TEXT,
                previous_price REAL,
                price_change REAL,
                price_dropped INTEGER NOT NULL DEFAULT 0,
                sale_started INTEGER NOT NULL DEFAULT 0,
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

        existing_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(price_history)")
        }
        for column, definition in EVENT_COLUMNS.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE price_history ADD COLUMN {column} {definition}"
                )
        connection.commit()


def create_run_id():
    return uuid.uuid4().hex


def get_latest_successful_observation(url):
    initialize_history()
    with closing(sqlite3.connect(HISTORY_FILE)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT price, is_on_sale, checked_at
            FROM price_history
            WHERE url = ? AND scrape_status = 'success' AND price IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (url,),
        ).fetchone()

    return dict(row) if row else None


def record_price(
    *, url, name, price, is_on_sale=False, original_price=None,
    scrape_status="success", run_id=None, previous_price=None,
    previous_on_sale=None, price_dropped=None, sale_started=None
):
    initialize_history()

    if run_id is None:
        run_id = create_run_id()

    if scrape_status == "success" and price is not None:
        latest = get_latest_successful_observation(url)
        if previous_price is None and latest:
            previous_price = latest["price"]
        if previous_on_sale is None and latest:
            previous_on_sale = bool(latest["is_on_sale"])

        if price_dropped is None:
            price_dropped = (
                previous_price is not None and price < previous_price
            )
        if sale_started is None:
            sale_started = (
                previous_price is not None
                and bool(is_on_sale)
                and not bool(previous_on_sale)
            )
        price_change = (
            price - previous_price if previous_price is not None else None
        )
    else:
        price_change = None
        price_dropped = False
        sale_started = False

    with closing(sqlite3.connect(HISTORY_FILE)) as connection:
        connection.execute(
            """
            INSERT INTO price_history (
                url, name, price, is_on_sale, original_price, scrape_status,
                run_id, previous_price, price_change, price_dropped, sale_started
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                url, name, price, int(is_on_sale), original_price, scrape_status,
                run_id, previous_price, price_change, int(price_dropped),
                int(sale_started),
            ),
        )
        connection.commit()

    return {
        "run_id": run_id,
        "previous_price": previous_price,
        "current_price": price,
        "price_change": price_change,
        "price_dropped": bool(price_dropped),
        "sale_started": bool(sale_started),
    }


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
            SELECT price, is_on_sale, original_price, scrape_status,
                   run_id, previous_price, price_change, price_dropped,
                   sale_started, checked_at
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


def count_products_with_price_drops(active_urls=None):
    initialize_history()
    with closing(sqlite3.connect(HISTORY_FILE)) as connection:
        latest_run = connection.execute(
            """
            SELECT run_id
            FROM price_history
            WHERE run_id IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        if not latest_run:
            return 0

        dropped_urls = {
            row[0] for row in connection.execute(
                """
                SELECT DISTINCT url
                FROM price_history
                WHERE run_id = ? AND scrape_status = 'success'
                  AND price_dropped = 1
                """,
                (latest_run[0],),
            ).fetchall()
        }

    if active_urls is not None:
        dropped_urls &= set(active_urls)

    return len(dropped_urls)
