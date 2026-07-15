import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from constants import HEADERS
from scraper import get_product_info, parse_price
from sale_utils import is_confirmed_sale
from storage import load_products, replace_products


@dataclass
class WishlistResult:
    links: list
    complete: bool
    pages: int
    error: str = None


def normalize_product_url(url):
    match = re.search(r"/dp/([A-Z0-9]{10})", url)

    if not match:
        return None

    asin = match.group(1)

    return f"https://www.amazon.sa/dp/{asin}"


def is_safe_amazon_url(url):
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    return (
        parsed.scheme in {"http", "https"}
        and (hostname == "amazon.sa" or hostname.endswith(".amazon.sa"))
    )


def is_blocked_wishlist_page(soup):
    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    return (
        "robot check" in title
        or soup.select_one("#captchacharacters") is not None
        or soup.select_one("form[action*='validateCaptcha']") is not None
    )


def find_next_page_url(soup, current_url):
    selectors = [
        "li.a-last a[href]",
        "a[aria-label='Next'][href]",
        "a[aria-label='التالي'][href]",
        "a[data-action='next-page'][href]",
    ]
    for selector in selectors:
        next_link = soup.select_one(selector)
        if next_link:
            return urljoin(current_url, next_link["href"])
    return None


def get_wishlist_links(url, max_pages=20):
    current_url = url
    visited_pages = set()
    links = []
    pages_read = 0

    while current_url:
        if current_url in visited_pages:
            return WishlistResult(
                links, False, pages_read, "Pagination loop detected"
            )
        if not is_safe_amazon_url(current_url):
            return WishlistResult(
                links, False, pages_read, "Unsafe pagination URL"
            )

        visited_pages.add(current_url)
        try:
            response = requests.get(
                current_url,
                headers=HEADERS,
                timeout=15,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as error:
            return WishlistResult(
                links, False, pages_read,
                f"Wishlist page request failed: {error}",
            )

        soup = BeautifulSoup(response.text, "html.parser")
        pages_read += 1

        if is_blocked_wishlist_page(soup):
            return WishlistResult(
                links, False, pages_read, "Amazon returned a CAPTCHA page"
            )

        page_links = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if "/dp/" not in href:
                continue
            normalized_url = normalize_product_url(href)
            if normalized_url and normalized_url not in page_links:
                page_links.append(normalized_url)
            if normalized_url and normalized_url not in links:
                links.append(normalized_url)

        print(f"Wishlist page {pages_read}: {len(page_links)} products")

        next_url = find_next_page_url(soup, response.url or current_url)
        if next_url is None:
            return WishlistResult(links, True, pages_read)
        if next_url in visited_pages:
            return WishlistResult(
                links, False, pages_read, "Pagination loop detected"
            )
        if not is_safe_amazon_url(next_url):
            return WishlistResult(
                links, False, pages_read, "Unsafe pagination URL"
            )
        if pages_read >= max_pages:
            return WishlistResult(
                links, False, pages_read, "Maximum wishlist pages reached"
            )

        current_url = next_url

    return WishlistResult(links, True, pages_read)


def sync_wishlist(wishlist_url):
    print("Reading Amazon wishlist...\n")

    result = get_wishlist_links(wishlist_url)
    links = result.links

    if not result.complete:
        print(
            f"Wishlist synchronization incomplete: {result.error}. "
            "Keeping all existing products."
        )
        return False

    print(f"\nProducts found in wishlist: {len(links)}")

    tracked_products = load_products()

    if not links and tracked_products:
        print(
            "Wishlist returned no products. Keeping all existing products "
            "because the page may be blocked, private, or incomplete."
        )
        return False

    if tracked_products and len(links) * 2 < len(tracked_products):
        print(
            "Wishlist returned less than half of the tracked products. "
            "Keeping all existing products as a safety precaution."
        )
        return False

    tracked_lookup = {
        product["url"]: product
        for product in tracked_products
    }

    updated_products = []

    added_count = 0
    skipped_count = 0
    failed_count = 0
    removed_count = 0

    for index, link in enumerate(links, start=1):
        print(
            f"\nChecking wishlist product "
            f"{index}/{len(links)}"
        )
        print(link)

        # Keep all existing product data,
        # including price history and sale status.
        if link in tracked_lookup:
            existing_product = tracked_lookup[link]

            existing_product.setdefault(
                "was_on_sale",
                False
            )

            updated_products.append(existing_product)

            print("Product is already being tracked.")
            skipped_count += 1
            continue

        # Only scrape products that are new
        # to the wishlist tracker.
        product_info = get_product_info(link)

        if (
            product_info["title"] == "Title not found"
            or product_info["price"] == "Price not found"
        ):
            print("Could not retrieve product information.")
            failed_count += 1
            continue

        price = parse_price(product_info["price"])

        if price is None:
            print("Invalid price.")
            failed_count += 1
            continue

        new_product = {
            "name": product_info["title"],
            "url": link,
            "last_price": price,
            "was_on_sale": is_confirmed_sale(
                price,
                product_info.get("discount_text"),
                product_info.get("original_price"),
            ),
            "image_url": product_info.get("image_url"),
            "original_price": product_info.get("original_price"),
            "discount_text": product_info.get("discount_text"),
            "availability": product_info.get("availability", "unknown"),
        }

        updated_products.append(new_product)

        print("Product added.")
        added_count += 1

    wishlist_urls = set(links)

    for product in tracked_products:
        if product["url"] not in wishlist_urls:
            print(
                f"\nRemoved from tracking: "
                f"{product['name']}"
            )
            removed_count += 1

    replace_products(updated_products)

    print("\nSync completed.")
    print(f"Added   : {added_count}")
    print(f"Skipped : {skipped_count}")
    print(f"Removed : {removed_count}")
    print(f"Failed  : {failed_count}")
    return True
