# Amazon Wishlist Price Tracker

Tracks products from an Amazon Saudi Arabia wishlist, compares prices, records
price history, and sends Telegram alerts for price drops and newly detected
sales. GitHub Actions runs the tracker daily.

Telegram also alerts when products return to stock or become unavailable. A
sale-ending alert is sent only after two consecutive successful checks confirm
that the sale is gone.

Wishlist synchronization follows Amazon pagination, deduplicates products, and
keeps the existing tracked list when a page fails, repeats, is blocked, points
outside Amazon Saudi Arabia, or returns a suspiciously small product set.

## Commands

```text
python app.py run
python app.py sync
python app.py check
python app.py list
python app.py remove PRODUCT_NUMBER
```

The `list` command also shows the lowest, highest, and average recorded price
once history has been collected.

## Dashboard

Start the read-only dashboard with:

```text
streamlit run streamlit_app.py
```

It shows compact product cards in a responsive three-column grid with names,
pictures, current sale status, Amazon links, historical price charts, and
lowest/highest/average prices. The history chart marks price drops, price
increases, sale starts, and confirmed sale endings. A table below the chart
lists the same events and price changes. The dashboard reads the same
`products.json` and `price_history.db` used by the scheduled tracker.
The product grid can be searched and sorted by name, price, or discount.

## Configuration

Set these values locally in `.env`, or as GitHub Actions secrets:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
WISHLIST_URL=...
```

## Storage

- `products.json` keeps the latest valid state for each tracked product.
- `price_history.db` is created automatically and records every successful or
  failed check with a timestamp.
- Telegram alerts and the dashboard use the same recorded price-change event,
  so their price-drop results remain consistent.
- A failed scrape never replaces a product's last valid price.
- An unexpectedly empty wishlist never erases existing tracked products.

## Tests

```text
python -m unittest discover -s tests -v
```
