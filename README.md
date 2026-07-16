# Amazon Wishlist Price Tracker

Tracks products from an Amazon Saudi Arabia wishlist, compares prices, records
price history, and sends Telegram alerts for price drops and newly detected
sales. GitHub Actions runs the tracker daily.

Telegram also alerts when products return to stock or become unavailable. A
sale-ending alert is sent only after two consecutive successful checks confirm
that the sale is gone.

A product is counted as on sale only when Amazon provides product-level
discount evidence: a discount percentage or a list price above the current
price. Unrelated deal badges elsewhere on the page are ignored.

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

The private dashboard includes a **Run tracker now** button that performs the
same wishlist synchronization and price check as `python app.py run`, including
normal Telegram alerts.

The AI shopping assistant treats `summarize PRODUCT` as a review-summary
request. It tries several public Amazon product-page variants because review
sections can be loaded inconsistently, supports both old and current review
markup, and then falls back to Amazon Saudi's generic, English, and Arabic
review pages. An optional product selector resolves ambiguous requests.
Successful samples are cached for six hours, and reviews are never invented
when no public sample is accessible. Successful anonymous samples are also
cached locally (and excluded from Git); if Amazon is temporarily blocked, a
sample saved within the previous seven days can be used with a clear stale-cache
disclosure.

The dashboard also includes a natural-language AI shopping assistant powered
by Groq's `llama-3.3-70b-versatile`. It can explain tracked prices and history
or summarize a limited, accessible sample of Amazon reviews. Review samples are
cached for six hours and unavailable reviews are reported rather than invented.

It shows compact product cards in a responsive three-column grid with names,
pictures, current sale status, Amazon links, historical price charts, and
lowest/highest/average prices. The history chart marks price drops, price
increases, sale starts, and confirmed sale endings. A table below the chart
lists the same events and price changes. The dashboard reads the same
`products.json` and `price_history.db` used by the scheduled tracker.
The product grid can be searched and sorted by name, price, or discount.
Sale products have an orange badge. The most recent real price movement stays
visible through unchanged or failed checks: decreases use a green badge and
increases use a red badge. A later price change replaces the previous badge.

## Configuration

Set these values locally in `.env`, or as GitHub Actions secrets:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
WISHLIST_URL=...
GROQ_API_KEY=...
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
