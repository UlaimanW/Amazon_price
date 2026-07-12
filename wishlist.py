import re

import requests
from bs4 import BeautifulSoup

from constants import HEADERS
from scraper import get_product_info, parse_price
from storage import load_products, replace_products


def normalize_product_url(url):
    match = re.search(r"/dp/([A-Z0-9]{10})", url)

    if not match:
        return None

    asin = match.group(1)

    return f"https://www.amazon.sa/dp/{asin}"


def get_wishlist_links(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=15
    )

    response.raise_for_status()

    print("Status Code:", response.status_code)
    print("HTML Length:", len(response.text))

    soup = BeautifulSoup(response.text, "html.parser")

    links = []

    for tag in soup.find_all("a", href=True):
        href = tag["href"]

        if "/dp/" not in href:
            continue

        normalized_url = normalize_product_url(href)

        if normalized_url and normalized_url not in links:
            links.append(normalized_url)

    return links


def sync_wishlist(wishlist_url):
    print("Reading Amazon wishlist...\n")

    try:
        links = get_wishlist_links(wishlist_url)
    except requests.exceptions.RequestException as error:
        print(f"Could not read the Amazon wishlist: {error}")
        return

    print(f"\nProducts found in wishlist: {len(links)}")

    tracked_products = load_products()

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
        print(f"\nChecking wishlist product {index}/{len(links)}")
        print(link)

        # Keep existing product data, including its custom target price.
        if link in tracked_lookup:
            updated_products.append(tracked_lookup[link])
            print("Product is already being tracked.")
            skipped_count += 1
            continue

        # Only scrape products that are new to the wishlist tracker.
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
            "last_price": price
        }

        updated_products.append(new_product)

        print("Product added.")
        added_count += 1

    wishlist_urls = set(links)

    for product in tracked_products:
        if product["url"] not in wishlist_urls:
            print(f"\nRemoved from tracking: {product['name']}")
            removed_count += 1

    replace_products(updated_products)

    print("\nSync completed.")
    print(f"Added   : {added_count}")
    print(f"Skipped : {skipped_count}")
    print(f"Removed : {removed_count}")
    print(f"Failed  : {failed_count}")