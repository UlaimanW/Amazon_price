import json
import re
import time
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from constants import HEADERS


REVIEW_CACHE_SECONDS = 6 * 60 * 60
STALE_REVIEW_CACHE_SECONDS = 7 * 24 * 60 * 60
REVIEW_CACHE_FILE = Path(".review_cache.json")
PRODUCT_PAGE_ATTEMPTS = 5
REVIEW_RETRY_SECONDS = 1
_review_cache = {}

REVIEW_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept-Language": HEADERS["Accept-Language"],
}

REVIEW_BODY_SELECTORS = (
    '[data-hook="review-body"]',
    '[data-hook="reviewText"]',
    '[data-hook="reviewTextContainer"]',
    ".review-text-content",
)
REVIEW_TITLE_SELECTORS = (
    '[data-hook="review-title"]',
    '[data-hook="reviewTitle"]',
)
REVIEW_RATING_SELECTORS = (
    '[data-hook="review-star-rating"]',
    '[data-hook="cmps-review-star-rating"]',
)


class ReviewFetchError(RuntimeError):
    pass


class ReviewSample(list):
    def __init__(self, reviews, *, saved_at=None, using_stale_cache=False):
        super().__init__(reviews)
        self.saved_at = saved_at
        self.using_stale_cache = using_stale_cache


def extract_asin(product_url):
    match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", product_url)
    if not match:
        raise ValueError("Could not identify the Amazon product ID.")
    return match.group(1)


def build_review_url(product_url):
    asin = extract_asin(product_url)
    return (
        f"https://www.amazon.sa/product-reviews/{quote(asin)}/"
        "?sortBy=recent"
    )


def build_review_urls(product_url):
    asin = quote(extract_asin(product_url))
    base_path = f"product-reviews/{asin}/"
    query = "ie=UTF8&reviewerType=all_reviews&sortBy=recent&pageNumber=1"
    return [
        f"https://www.amazon.sa/{base_path}?{query}",
        f"https://www.amazon.sa/-/en/{base_path}?{query}",
        f"https://www.amazon.sa/-/ar/{base_path}?{query}",
    ]


def canonical_product_url(product_url):
    parsed = urlsplit(product_url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def build_product_page_urls(product_url):
    asin = quote(extract_asin(product_url))
    return [
        f"https://www.amazon.sa/dp/{asin}",
        f"https://www.amazon.sa/dp/{asin}?th=1",
        f"https://www.amazon.sa/-/en/dp/{asin}?th=1",
        f"https://www.amazon.sa/-/ar/dp/{asin}?th=1",
        f"https://www.amazon.sa/dp/{asin}?language=en_AE",
    ]


def first_matching_element(element, selectors):
    for selector in selectors:
        match = element.select_one(selector)
        if match:
            return match
    return None


def parse_rating(text):
    if not text:
        return None
    normalized = str(text).replace("٫", ".").replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", normalized)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def parse_reviews(html_text, max_reviews=20):
    soup = BeautifulSoup(html_text, "html.parser")
    page_text = soup.get_text(" ", strip=True).lower()
    if "robot check" in page_text or "enter the characters you see" in page_text:
        raise ReviewFetchError("Amazon blocked the review request with a CAPTCHA.")

    reviews = []
    seen_bodies = set()
    for review in soup.select('[data-hook="review"]'):
        body_element = first_matching_element(review, REVIEW_BODY_SELECTORS)
        if not body_element:
            continue

        body = body_element.get_text(" ", strip=True)
        if not body or body in seen_bodies:
            continue
        seen_bodies.add(body)

        title_element = first_matching_element(review, REVIEW_TITLE_SELECTORS)
        rating_element = first_matching_element(review, REVIEW_RATING_SELECTORS)
        rating = parse_rating(
            rating_element.get_text(" ", strip=True)
            if rating_element else None
        )

        reviews.append({
            "title": (
                title_element.get_text(" ", strip=True)
                if title_element else ""
            ),
            "rating": rating,
            "body": body[:1500],
        })
        if len(reviews) >= max_reviews:
            break

    return reviews


def create_review_session():
    session = requests.Session()
    session.headers.update(REVIEW_HEADERS)
    return session


def fetch_review_source(source_url, max_reviews, session=None):
    session = session or create_review_session()
    try:
        response = session.get(source_url, timeout=20)
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        raise ReviewFetchError(f"Request failed: {error}") from error

    return parse_reviews(response.text, max_reviews=max_reviews)


def fetch_product_reviews(
    product_url,
    max_reviews=20,
    session=None,
    product_page_attempts=PRODUCT_PAGE_ATTEMPTS,
    retry_sleep=time.sleep,
):
    session = session or create_review_session()
    source_errors = []
    product_url = canonical_product_url(product_url)
    product_page_urls = build_product_page_urls(product_url)

    for attempt, source_url in enumerate(
        product_page_urls[:product_page_attempts], start=1
    ):
        try:
            reviews = fetch_review_source(
                source_url, max_reviews, session=session
            )
        except ReviewFetchError as error:
            source_errors.append(f"product page attempt {attempt}: {error}")
        else:
            if reviews:
                return reviews
            source_errors.append(
                f"product page attempt {attempt}: no review snippets found"
            )

        if attempt < product_page_attempts:
            retry_sleep(REVIEW_RETRY_SECONDS)

    for source_number, source_url in enumerate(
        build_review_urls(product_url), start=1
    ):
        try:
            reviews = fetch_review_source(
                source_url, max_reviews, session=session
            )
        except ReviewFetchError as error:
            source_errors.append(f"review page {source_number}: {error}")
            continue

        if reviews:
            return reviews
        source_errors.append(
            f"review page {source_number}: no review snippets found"
        )

    raise ReviewFetchError(
        "No accessible customer reviews were found. " + "; ".join(source_errors)
    )


def get_cached_product_reviews(product_url, max_reviews=20, now=None):
    now = time.time() if now is None else now
    cache_key = f"{canonical_product_url(product_url)}|{max_reviews}"
    cached = _review_cache.get(cache_key)

    if cached is None:
        disk_cache = load_review_cache()
        cached = disk_cache.get(cache_key)
        if cached:
            _review_cache[cache_key] = cached

    cache_age = (
        now - float(cached["saved_at"])
        if cached and cached.get("saved_at") is not None else None
    )
    if cache_age is not None and cache_age < REVIEW_CACHE_SECONDS:
        return ReviewSample(
            cached["reviews"], saved_at=cached["saved_at"]
        )

    try:
        reviews = fetch_product_reviews(product_url, max_reviews=max_reviews)
    except ReviewFetchError:
        if (
            cache_age is not None
            and cache_age < STALE_REVIEW_CACHE_SECONDS
            and cached.get("reviews")
        ):
            return ReviewSample(
                cached["reviews"],
                saved_at=cached["saved_at"],
                using_stale_cache=True,
            )
        raise

    entry = {"saved_at": now, "reviews": list(reviews)}
    _review_cache[cache_key] = entry
    save_review_cache_entry(cache_key, entry)
    return ReviewSample(reviews, saved_at=now)


def load_review_cache():
    try:
        data = json.loads(REVIEW_CACHE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_review_cache_entry(cache_key, entry):
    disk_cache = load_review_cache()
    disk_cache[cache_key] = entry
    temporary_file = REVIEW_CACHE_FILE.with_name(
        f"{REVIEW_CACHE_FILE.name}.tmp"
    )
    temporary_file.write_text(
        json.dumps(disk_cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_file.replace(REVIEW_CACHE_FILE)
