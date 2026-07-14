
import time
import re

import requests
from bs4 import BeautifulSoup

from constants import HEADERS


def parse_price(price_text):
    if price_text is None:
        return None

    cleaned_price = str(price_text)

    cleaned_price = cleaned_price.replace(",", "")
    cleaned_price = cleaned_price.replace("SAR", "")
    cleaned_price = cleaned_price.replace("ريال", "")
    cleaned_price = cleaned_price.strip()

    match = re.search(r"\d+(?:\.\d+)?", cleaned_price)

    if not match:
        return None

    return float(match.group())


def find_first_text(soup, selectors):
    for selector in selectors:
        element = soup.select_one(selector)

        if element:
            text = element.get_text(" ", strip=True)

            if text:
                return text

    return None


def detect_product_image(soup):
    image_selectors = [
        "#landingImage",
        "#imgBlkFront",
        "#main-image",
        "img.a-dynamic-image",
    ]

    for selector in image_selectors:
        image = soup.select_one(selector)
        if not image:
            continue

        image_url = image.get("data-old-hires") or image.get("src")
        if image_url and image_url.startswith("http"):
            return image_url

    return None


def detect_discount_text(soup):
    discount_selectors = [
        "span.savingsPercentage",
        "span.a-size-large.a-color-price.savingPriceOverride",
        "span.a-color-price.savingPriceOverride",
        "span.a-size-base.a-color-price",
        "#dealprice_savings",
        "#regularprice_savings",
    ]

    for selector in discount_selectors:
        elements = soup.select(selector)

        for element in elements:
            text = element.get_text(" ", strip=True)

            match = re.search(
                r"-?\s*\d+(?:\.\d+)?\s*%",
                text
            )

            if match:
                return match.group().replace(" ", "")

    return None


def detect_deal_badge(soup):
    deal_selectors = [
        "#dealBadge_feature_div",
        "#dealBadgeSupportingText",
        "span.dealBadge",
        "span.dealBadgeTextColor",
        "span.a-badge-text",
        "span.badge-text",
        "div.a-section.a-spacing-none.aok-align-center",
    ]

    deal_keywords = [
        "limited time deal",
        "today's deal",
        "deal of the day",
        "prime deal",
        "عرض لفترة محدودة",
        "عرض اليوم",
        "صفقة اليوم",
    ]

    for selector in deal_selectors:
        elements = soup.select(selector)

        for element in elements:
            text = element.get_text(
                " ",
                strip=True
            ).lower()

            if any(
                keyword in text
                for keyword in deal_keywords
            ):
                return True

    page_text = soup.get_text(
        " ",
        strip=True
    ).lower()

    return any(
        keyword in page_text
        for keyword in deal_keywords
    )


def detect_original_price(soup, current_price):
    original_price_selectors = [
        "span.a-price.a-text-price span.a-offscreen",
        "span.basisPrice span.a-offscreen",
        "#listPrice",
        "#priceblock_listprice",
        "#priceblock_saleprice",
        "span[data-a-strike='true'] span.a-offscreen",
    ]

    for selector in original_price_selectors:
        elements = soup.select(selector)

        for element in elements:
            original_price_text = element.get_text(
                " ",
                strip=True
            )

            original_price = parse_price(
                original_price_text
            )

            if original_price is None:
                continue

            if (
                current_price is None
                or original_price > current_price
            ):
                return original_price

    return None


def get_product_info(url, max_attempts=6):
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=20
            )

            response.raise_for_status()

            print("Status code:", response.status_code)
            print("Final URL:", response.url)
            print("HTML length:", len(response.text))
            print(f"Attempt: {attempt}/{max_attempts}")

            if len(response.text) < 100000:
                print("Amazon returned a small page.")

                if attempt < max_attempts:
                    wait_time = attempt * 3

                    print(
                        f"Waiting {wait_time} seconds "
                        f"before retrying..."
                    )

                    time.sleep(wait_time)

                continue

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            title_tag = soup.find(id="productTitle")

            title = (
                title_tag.get_text(strip=True)
                if title_tag
                else "Title not found"
            )

            price_selectors = [
                "#corePrice_feature_div "
                "span.a-price span.a-offscreen",

                "#corePriceDisplay_desktop_feature_div "
                "span.a-price span.a-offscreen",

                "#apex_desktop "
                "span.a-price span.a-offscreen",

                "#price_inside_buybox",
                "#priceblock_dealprice",
                "#priceblock_ourprice",
                "span.a-price span.a-offscreen",
                "span.a-price-whole",
            ]

            price_text = find_first_text(
                soup,
                price_selectors
            )

            if price_text is None:
                print("Price was not found in the page.")

                if attempt < max_attempts:
                    wait_time = attempt * 3

                    print(
                        f"Waiting {wait_time} seconds "
                        f"before retrying..."
                    )

                    time.sleep(wait_time)

                continue

            current_price = parse_price(price_text)

            if current_price is None:
                print("The detected price was invalid.")

                if attempt < max_attempts:
                    wait_time = attempt * 3
                    time.sleep(wait_time)

                continue

            discount_text = detect_discount_text(soup)
            deal_badge_found = detect_deal_badge(soup)

            original_price = detect_original_price(
                soup,
                current_price
            )

            has_discount_percentage = (
                discount_text is not None
            )

            has_lower_price = (
                original_price is not None
                and original_price > current_price
            )

            is_on_sale = (
                deal_badge_found
                or has_discount_percentage
                or has_lower_price
            )

            print("Product title:", title)
            print("Current price:", current_price)
            print("On sale:", is_on_sale)
            print("Discount:", discount_text)
            print("Original price:", original_price)

            return {
                "title": title,
                "price": price_text,
                "status": "success",
                "image_url": detect_product_image(soup),
                "is_on_sale": is_on_sale,
                "discount_text": discount_text,
                "original_price": original_price,
                "url": response.url
            }

        except requests.exceptions.Timeout:
            print(
                f"Request timed out on attempt "
                f"{attempt}/{max_attempts}."
            )

        except requests.exceptions.ConnectionError:
            print(
                f"Connection error on attempt "
                f"{attempt}/{max_attempts}."
            )

        except requests.exceptions.HTTPError as error:
            print(
                f"HTTP error on attempt "
                f"{attempt}/{max_attempts}: {error}"
            )

        except requests.exceptions.RequestException as error:
            print(
                f"Request failed on attempt "
                f"{attempt}/{max_attempts}: {error}"
            )

        if attempt < max_attempts:
            wait_time = attempt * 3

            print(
                f"Waiting {wait_time} seconds "
                f"before retrying..."
            )

            time.sleep(wait_time)

    print(
        f"Failed to retrieve product information "
        f"after {max_attempts} attempts."
    )

    return {
        "title": "Title not found",
        "price": "Price not found",
        "status": "failed",
        "image_url": None,
        "is_on_sale": False,
        "discount_text": None,
        "original_price": None,
        "url": url
    }

