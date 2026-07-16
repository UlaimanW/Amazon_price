# Amazon Wishlist Price Tracker

An automated price-monitoring project for Amazon Saudi Arabia wishlists. It
synchronizes wishlist products, checks prices and availability, records a
historical timeline, sends Telegram alerts, provides a Streamlit dashboard,
and includes an AI shopping assistant for questions about tracked data and
accessible customer-review samples.

## Main features

- Synchronizes products from a public Amazon Saudi Arabia wishlist.
- Supports multi-page wishlists and rejects unsafe or incomplete pagination.
- Tracks current price, original price, discount, product image, sale status,
  and availability.
- Preserves the last valid price when Amazon returns a blocked or incomplete
  page.
- Records successful and failed checks in SQLite.
- Sends Telegram alerts for important price, sale, and availability events.
- Displays compact product cards, price history, event markers, filters, and
  summary metrics in Streamlit.
- Shows the last successful tracker run in Saudi Arabia time.
- Runs the same complete tracker workflow from the command line, dashboard,
  Docker container, or GitHub Actions.
- Uses Groq to answer questions about tracked products and summarize a limited
  public sample of Amazon reviews.
- Includes automated tests for scraping, history, alerts, wishlist safety,
  dashboard helpers, reviews, and AI grounding.

## Architecture

```text
Amazon wishlist
      |
      v
 wishlist.py  ---- validates pagination and synchronizes products
      |
      v
 products.json
      |
      v
 price_checker.py ----> scraper.py ----> Amazon product pages
      |                    |
      |                    +---- price, discount, image, availability
      |
      +---- sale_utils.py
      +---- price_history.py ----> price_history.db
      +---- notifier.py ---------> Telegram
      +---- tracker_status.py ---> tracker_status.json
                  |
                  v
          streamlit_app.py
                  |
          dashboard + AI assistant
                  |
        ai_assistant.py + review_scraper.py
                  |
        Groq API + public Amazon review samples
```

`app.py` is the main tracker entry point. Its `run` workflow first synchronizes
the wishlist, then checks every tracked product, and finally records the
successful completion time. The dashboard and GitHub Actions call this same
workflow, so they do not have separate price-checking logic.

## Project structure

```text
Amazon_price/
|-- .github/
|   `-- workflows/
|       `-- price-tracker.yml
|-- tests/
|   |-- fixtures/
|   `-- test_tracker.py
|-- .dockerignore
|-- .env
|-- .gitignore
|-- Dockerfile
|-- README.md
|-- ai_assistant.py
|-- app.py
|-- compose.yaml
|-- config.py
|-- constants.py
|-- dashboard_utils.py
|-- notifier.py
|-- price_checker.py
|-- price_history.db
|-- price_history.py
|-- products.json
|-- requirements.txt
|-- review_scraper.py
|-- sale_utils.py
|-- scraper.py
|-- storage.py
|-- streamlit_app.py
|-- tracker_status.json
|-- tracker_status.py
`-- wishlist.py
```

### Application files

| File | Responsibility |
| --- | --- |
| `app.py` | Provides the command-line interface and complete tracker workflow. |
| `config.py` | Loads environment variables and validates required tracker configuration. |
| `constants.py` | Stores shared browser-like HTTP request headers. |
| `wishlist.py` | Reads wishlist pages, validates pagination, normalizes Amazon URLs, and synchronizes tracked products. |
| `scraper.py` | Downloads and parses Amazon product pages for title, price, discount, original price, image, and availability. |
| `price_checker.py` | Compares current and previous product state, records observations, updates product data, and decides when to alert. |
| `sale_utils.py` | Confirms genuine product-level discounts and calculates discount percentages. |
| `price_history.py` | Owns the SQLite schema, observations, price events, availability events, statistics, and dashboard history queries. |
| `storage.py` | Reads and writes the current product catalog in `products.json`. |
| `notifier.py` | Sends formatted Telegram messages through the Telegram Bot API. |
| `tracker_status.py` | Saves and formats the most recent successful run time. |
| `streamlit_app.py` | Renders the dashboard, manual tracker button, product cards, filters, history chart, event table, and AI chat. |
| `dashboard_utils.py` | Contains reusable card badges, filtering, sorting, grid, and timeline helpers. |
| `ai_assistant.py` | Matches questions to products, builds grounded tracker/review context, and calls Groq. |
| `review_scraper.py` | Retrieves anonymous public review samples, parses multiple Amazon layouts, and manages review caching. |

### Runtime and automation files

| File | Responsibility |
| --- | --- |
| `requirements.txt` | Pins the Python dependencies used by the project. |
| `Dockerfile` | Builds the Python 3.13 Streamlit image and defines its health check and startup process. |
| `compose.yaml` | Defines the `amazon_price` image and container, port, runtime environment, restart behavior, and persistent data mounts. |
| `.dockerignore` | Prevents secrets, local environments, caches, tests, and development files from entering the image build context. |
| `.github/workflows/price-tracker.yml` | Runs the tracker automatically twice per day and saves updated tracker data back to the repository. |
| `.gitignore` | Excludes local secrets, virtual environments, caches, temporary database files, and debugging output. |

### Tests

`tests/test_tracker.py` contains the automated test suite. The files under
`tests/fixtures/` are saved HTML examples used to test availability,
pagination, CAPTCHA detection, and old/current Amazon review layouts without
depending on live pages during unit tests.

## Requirements

- Python 3.13 is the project runtime used by Docker and GitHub Actions.
- A public or accessible Amazon Saudi Arabia wishlist URL.
- A Telegram bot token and chat ID for tracker alerts.
- A Groq API key if the AI assistant will be used.
- Internet access for Amazon, Telegram, and Groq requests.
- Docker Desktop is optional for containerized operation.

## Configuration

Create a local `.env` file in the project root:

```dotenv
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
WISHLIST_URL=https://www.amazon.sa/hz/wishlist/ls/your_wishlist_id
GROQ_API_KEY=your_groq_api_key
```

### Environment variables

| Variable | Required | Used for |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Yes for tracker runs | Authenticating requests to the Telegram Bot API. |
| `TELEGRAM_CHAT_ID` | Yes for tracker runs | Selecting the Telegram conversation that receives alerts. |
| `WISHLIST_URL` | Yes for synchronization | Identifying the Amazon Saudi Arabia wishlist to track. |
| `GROQ_API_KEY` | Only for AI features | Enabling the dashboard AI shopping assistant. |

The `.env` file is ignored by Git and Docker image builds. Docker Compose reads
it only when the container starts. GitHub Actions uses repository secrets
instead of the local file.

## Local installation

Create and activate a virtual environment in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
python -m pip install -r requirements.txt
```

If PowerShell prevents activation for the current window:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Command-line interface

The command-line entry point is `app.py`.

```powershell
python app.py run
python app.py sync
python app.py check
python app.py list
python app.py remove PRODUCT_NUMBER
```

| Command | Behavior |
| --- | --- |
| `run` | Synchronizes the wishlist, checks all products, sends alerts, and records the successful run time. |
| `sync` | Synchronizes the wishlist without running the full price check. |
| `check` | Checks prices for the products already stored in `products.json`. |
| `list` | Lists tracked products and available lowest, highest, average, and observation statistics. |
| `remove` | Removes a product by the number shown by the `list` command. |

## Streamlit dashboard

Start the local dashboard with:

```powershell
streamlit run streamlit_app.py
```

The dashboard is available at `http://localhost:8501` and includes:

- Total tracked products.
- Products currently confirmed as on sale.
- Products whose latest real price movement was a decrease.
- Search and sort controls.
- Responsive three-column product cards.
- Product images, current prices, discounts, list prices, badges, and Amazon
  links.
- A manual **Run tracker now** button with a loading state.
- The last successful run time displayed in Saudi Arabia time.
- A product selector with current, lowest, highest, and average prices.
- A historical price chart with price and sale event markers.
- A chronological price and sale event table.
- An AI shopping assistant at the bottom of the page.

The page opens at the top. After the user submits an AI message and receives a
response, the dashboard smoothly scrolls to the latest chat message.

## Wishlist synchronization

Wishlist synchronization follows every available page up to a safety limit. It
normalizes product links to canonical Amazon Saudi Arabia `/dp/ASIN` URLs and
deduplicates repeated products.

The existing tracked list is preserved when:

- Amazon returns a CAPTCHA or robot-check page.
- A wishlist page request fails.
- Pagination points outside Amazon Saudi Arabia.
- Pagination repeats and creates a loop.
- The maximum page limit is reached before completion.
- The wishlist unexpectedly returns no products.
- The result contains fewer than half of the currently tracked products.

This prevents a temporary Amazon block or incomplete page from deleting valid
tracked products.

## Price and sale tracking

For each product, the tracker retrieves:

- Product title.
- Current price in SAR.
- Original or list price when available.
- Amazon discount text.
- Product image URL.
- Availability status.

A product is considered on sale only when Amazon provides product-level
evidence:

- A valid discount percentage, or
- An original price that is greater than the current price.

Unrelated promotional badges elsewhere on an Amazon page do not mark the
product as on sale.

### Sale savings versus price-drop savings

These are two different comparisons:

- **Sale savings** compares the current price with Amazon's displayed original
  or list price.
- **Price-drop savings** compares the current price with the product's previous
  successful tracked price.

A product can be on sale without a new tracked price drop, and a product can
drop in price without Amazon displaying a formal sale.

### Persistent price movement badges

The dashboard remembers the most recent real price movement:

- A decrease produces a green price-drop badge.
- An increase produces a red price-increase badge.
- Unchanged or failed checks do not remove the latest movement badge.
- A later real price change replaces the previous badge and amount.

## Telegram alerts

The bot sends an alert when one or more of these events occur:

1. The current price is lower than the previous successful price.
2. A confirmed sale starts.
3. A sale is confirmed to have ended.
4. A product returns to stock.
5. A product becomes unavailable.

Messages can include the current price, previous price, price-drop savings,
original price, total sale savings, discount percentage, availability change,
previous sale price, and Amazon link.

### Sale-ending confirmation

A missing sale is not announced immediately. The tracker requires two
consecutive successful checks showing that the sale is gone. A failed scrape
does not advance this confirmation. If the sale returns before the second
successful check, the pending confirmation is reset.

Sale-ending state is internal to the tracker and is not added to product cards.
Confirmed historical events can still be represented in the product history
timeline.

## Availability tracking

The scraper recognizes these states:

- In stock.
- Out of stock.
- Temporarily unavailable.
- Available from other sellers.
- Unknown.

Availability changes are recorded in history and used by Telegram alerts. A
page that provides reliable availability but no price can still update the
availability state without replacing the last valid product price.

## Price history

`price_history.db` is an SQLite database containing observations from tracker
runs. Each observation can include:

- Product URL and name.
- Price and currency.
- Sale and original-price information.
- Scrape status.
- Availability state.
- Previous price and price-change amount.
- Price-drop, sale-start, and confirmed sale-end events.
- Back-in-stock and became-unavailable events.
- Run identifier and check timestamp.

Failed observations are stored for health information but are excluded from
lowest, highest, and average price statistics. The dashboard and Telegram bot
read the same event history, keeping their price-drop results consistent.

## AI shopping assistant

The dashboard AI assistant uses Groq's `llama-3.3-70b-versatile` model. It can:

- Compare tracked prices and discounts.
- Explain product price history.
- Identify tracked products from natural-language questions.
- Summarize an accessible sample of public Amazon customer reviews.
- Use an explicitly selected product when a question is ambiguous.

The assistant receives structured tracker data instead of unrestricted access
to project files. Review instructions require it to avoid inventing customer
opinions. A theme is described as repeated only when it appears in at least two
different sampled reviews.

### Review collection and caching

Amazon can return different review layouts or temporarily block automated
requests. The review scraper therefore tries:

- Multiple product-page variants.
- Generic Amazon Saudi Arabia review pages.
- English and Arabic review-page variants.
- Both older and current Amazon review HTML selectors.

Only review title, rating, and body are collected; reviewer identity is not
stored. Successful samples are treated as fresh for six hours. An anonymous
sample saved in `.review_cache.json` can be used for up to seven days during a
temporary Amazon block, and the assistant discloses when stale cached data is
being used. If no sample is available, the assistant reports that limitation
instead of fabricating a summary.

## Stored data

| File | Contents | Persistence |
| --- | --- | --- |
| `products.json` | Latest valid product name, URL, price, sale data, image, and availability. | Tracked and mounted into Docker. |
| `price_history.db` | SQLite observations, statistics, price events, sale events, and availability events. | Tracked and mounted into Docker. |
| `tracker_status.json` | Timestamp of the most recent successful complete tracker run. | Tracked and mounted into Docker. |
| `.review_cache.json` | Anonymous cached review samples used by the AI assistant. | Local only and ignored by Git and Docker builds. |

The Docker container uses bind mounts for the three primary tracker data files.
Updates made by the container are therefore written directly to the matching
files in the project directory and survive container replacement.

## Docker design

The containerized application uses:

- Image name: `amazon_price:latest`.
- Container name: `amazon_price`.
- Python 3.13 slim base image.
- Streamlit bound to `0.0.0.0` on port `8501`.
- A built-in health check against Streamlit's health endpoint.
- Runtime variables loaded from `.env` without copying that file into the
  image.
- Read-write mounts for `products.json`, `price_history.db`, and
  `tracker_status.json`.
- Automatic restart unless the container was intentionally stopped.

`Dockerfile` defines how the image is built and started. `compose.yaml` records
how the container is named, configured, connected, and given persistent data.
`.dockerignore` keeps development files and secrets outside the image context.

## GitHub Actions automation

The workflow in `.github/workflows/price-tracker.yml` runs at:

- 12:00 AM Saudi Arabia time.
- 12:00 PM Saudi Arabia time.

It can also be started manually from the GitHub Actions interface. The workflow
uses Python 3.13, installs `requirements.txt`, executes the complete tracker,
and saves updates to:

- `products.json`
- `price_history.db`
- `tracker_status.json`

Only one tracker workflow runs at a time. GitHub repository secrets provide the
Telegram and wishlist configuration without committing the local `.env` file.

## Testing

Run the complete test suite with:

```powershell
python -m unittest discover -s tests -v
```

The suite covers:

- Price parsing and failed-scrape behavior.
- Product images, discounts, and sale confirmation.
- Availability detection and alerts.
- Two-check sale-ending confirmation.
- SQLite history migration, statistics, and event persistence.
- Dashboard price-drop counts, badges, grids, filters, and timelines.
- Safe multi-page wishlist synchronization.
- CAPTCHA, pagination loop, external URL, and suspicious reduction protection.
- Review parsing, locale fallbacks, caching, and CAPTCHA handling.
- AI product matching, review grounding, and API-key validation.
- Successful-run timestamps and Saudi time formatting.

## Failure handling and data safety

- A failed price scrape never overwrites the last valid price.
- Invalid prices are recorded as failed observations instead of being used in
  statistics.
- Failed availability checks do not create false stock alerts.
- Failed checks do not confirm that a sale ended.
- Incomplete wishlist synchronization never replaces the existing catalog.
- The dashboard reports AI and review-access failures without stopping the
  price tracker.
- The last successful run timestamp changes only after the complete tracker
  workflow finishes.

## Troubleshooting

### PowerShell cannot activate `.venv`

Confirm that `.venv` exists and that it was created with the installed Python
version. A temporary `Process` execution-policy change can allow activation in
the current terminal without permanently changing the computer policy.

### NumPy or another compiled package cannot import

This usually means the environment contains packages built for a different
Python version. Recreate `.venv` with one Python version and reinstall all
dependencies without reusing the broken environment.

### Amazon returns no price or reviews

Amazon may serve CAPTCHA, regional, incomplete, or dynamically loaded pages.
The tracker keeps the previous valid product price, records the failed attempt,
and tries again on a later run. Review questions use a recent cached anonymous
sample when allowed; otherwise the limitation is shown to the user.

### Telegram alerts are missing

Check that the bot token and chat ID are correct, that the bot can message the
selected chat, and that the tracker configuration validates successfully.
Remember that unchanged prices do not send alerts and sale endings require two
successful confirmations.

### Dashboard data appears unchanged

The dashboard reads `products.json` and `price_history.db`. Run the complete
tracker successfully, then allow Streamlit to rerun or refresh the page. The
last successful run label helps confirm which tracker execution produced the
current data.

## Security and privacy

- Never commit `.env` or paste real tokens into documentation.
- Store automation credentials as GitHub repository secrets.
- The Docker image does not contain `.env`.
- Review samples exclude reviewer identity.
- Amazon links are restricted to the `amazon.sa` domain during wishlist
  pagination.
- The dashboard is designed as a private application and does not add its own
  authentication layer.

## Current limitations

- Amazon can change its HTML structure at any time.
- CAPTCHA and anti-automation responses can temporarily prevent live scraping.
- Review summaries represent only the accessible sample, not every customer
  review.
- The AI assistant requires an external Groq connection.
- SQLite is appropriate for this single-user tracker but is not intended for
  high-concurrency multi-user deployment.
