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
    "sale_end_streak": "INTEGER NOT NULL DEFAULT 0",
    "sale_ended": "INTEGER NOT NULL DEFAULT 0",
    "previous_sale_price": "REAL",
    "availability": "TEXT NOT NULL DEFAULT 'unknown'",
    "previous_availability": "TEXT",
    "availability_changed": "INTEGER NOT NULL DEFAULT 0",
    "back_in_stock": "INTEGER NOT NULL DEFAULT 0",
    "became_unavailable": "INTEGER NOT NULL DEFAULT 0",
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
                sale_end_streak INTEGER NOT NULL DEFAULT 0,
                sale_ended INTEGER NOT NULL DEFAULT 0,
                previous_sale_price REAL,
                availability TEXT NOT NULL DEFAULT 'unknown',
                previous_availability TEXT,
                availability_changed INTEGER NOT NULL DEFAULT 0,
                back_in_stock INTEGER NOT NULL DEFAULT 0,
                became_unavailable INTEGER NOT NULL DEFAULT 0,
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
            SELECT price, is_on_sale, sale_end_streak, checked_at
            FROM price_history
            WHERE url = ? AND scrape_status = 'success' AND price IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (url,),
        ).fetchone()

    return dict(row) if row else None


def get_latest_availability_observation(url):
    initialize_history()
    with closing(sqlite3.connect(HISTORY_FILE)) as connection:
        row = connection.execute(
            """
            SELECT availability
            FROM price_history
            WHERE url = ? AND availability IS NOT NULL
              AND availability != 'unknown'
            ORDER BY id DESC
            LIMIT 1
            """,
            (url,),
        ).fetchone()

    return row[0] if row else None


def get_latest_sale_price(url):
    initialize_history()
    with closing(sqlite3.connect(HISTORY_FILE)) as connection:
        row = connection.execute(
            """
            SELECT price
            FROM price_history
            WHERE url = ? AND scrape_status = 'success'
              AND price IS NOT NULL AND is_on_sale = 1
            ORDER BY id DESC
            LIMIT 1
            """,
            (url,),
        ).fetchone()

    return row[0] if row else None


def record_price(
    *, url, name, price, is_on_sale=False, original_price=None,
    scrape_status="success", run_id=None, previous_price=None,
    previous_on_sale=None, price_dropped=None, sale_started=None,
    sale_end_streak=None, sale_ended=None, previous_sale_price=None,
    availability="unknown", previous_availability=None,
    availability_changed=None, back_in_stock=None,
    became_unavailable=None
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

        if is_on_sale:
            sale_end_streak = 0
            sale_ended = False
            previous_sale_price = None
        elif latest:
            latest_streak = latest.get("sale_end_streak") or 0
            if bool(latest["is_on_sale"]):
                sale_end_streak = 1
            elif latest_streak > 0:
                sale_end_streak = latest_streak + 1
            else:
                sale_end_streak = 0

            sale_ended = sale_end_streak == 2
            if sale_end_streak > 0 and previous_sale_price is None:
                previous_sale_price = get_latest_sale_price(url)
        elif previous_on_sale:
            sale_end_streak = 1
            sale_ended = False
            previous_sale_price = previous_price
        else:
            sale_end_streak = 0
            sale_ended = False
            previous_sale_price = None
    else:
        price_change = None
        price_dropped = False
        sale_started = False
        sale_end_streak = 0
        sale_ended = False
        previous_sale_price = None

    availability = availability or "unknown"
    if previous_availability is None:
        previous_availability = get_latest_availability_observation(url)

    known_previous = previous_availability not in {None, "unknown"}
    known_current = availability != "unknown"
    if availability_changed is None:
        availability_changed = (
            known_previous
            and known_current
            and previous_availability != availability
        )

    available_states = {"in_stock", "available_from_other_sellers"}
    unavailable_states = {"out_of_stock", "temporarily_unavailable"}
    if back_in_stock is None:
        back_in_stock = (
            previous_availability in unavailable_states
            and availability in available_states
        )
    if became_unavailable is None:
        became_unavailable = (
            previous_availability in available_states
            and availability in unavailable_states
        )

    with closing(sqlite3.connect(HISTORY_FILE)) as connection:
        connection.execute(
            """
            INSERT INTO price_history (
                url, name, price, is_on_sale, original_price, scrape_status,
                run_id, previous_price, price_change, price_dropped, sale_started
                , sale_end_streak, sale_ended, previous_sale_price
                , availability, previous_availability, availability_changed,
                back_in_stock, became_unavailable
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                url, name, price, int(is_on_sale), original_price, scrape_status,
                run_id, previous_price, price_change, int(price_dropped),
                int(sale_started), sale_end_streak, int(sale_ended),
                previous_sale_price, availability, previous_availability,
                int(availability_changed), int(back_in_stock),
                int(became_unavailable),
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
        "sale_end_streak": sale_end_streak,
        "sale_ended": bool(sale_ended),
        "previous_sale_price": previous_sale_price,
        "availability": availability,
        "previous_availability": previous_availability,
        "availability_changed": bool(availability_changed),
        "back_in_stock": bool(back_in_stock),
        "became_unavailable": bool(became_unavailable),
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
                   sale_started, sale_end_streak, sale_ended,
                   previous_sale_price, availability, previous_availability,
                   availability_changed, back_in_stock,
                   became_unavailable, checked_at
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


def get_products_with_price_drops(active_urls=None):
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
            return set()

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

    return dropped_urls


def count_products_with_price_drops(active_urls=None):
    return len(get_products_with_price_drops(active_urls))
