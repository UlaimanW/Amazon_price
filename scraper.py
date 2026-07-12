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


def get_product_info(url):
    for attempt in range(3):
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=15
            )

            response.raise_for_status()

            print("Status code:", response.status_code)
            print("Final URL:", response.url)
            print("HTML length:", len(response.text))

            if len(response.text) < 100000:
                print(
                    f"Amazon returned a small page on attempt "
                    f"{attempt + 1}. Retrying..."
                )
                time.sleep(3)
                continue

            

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            title_tag = soup.find(id="productTitle")

            price_selectors = [
                ("span", {"class": "a-price-whole"}),
                ("span", {"class": "a-offscreen"}),
                ("span", {"id": "priceblock_ourprice"}),
                ("span", {"id": "priceblock_dealprice"}),
            ]

            title = (
                title_tag.get_text(strip=True)
                if title_tag
                else "Title not found"
            )

            price = "Price not found"

            for tag_name, attrs in price_selectors:
                price_tag = soup.find(tag_name, attrs)

                if price_tag:
                    price = price_tag.get_text(strip=True)
                    break

            return {
                "title": title,
                "price": price,
                "url": url
            }

        except requests.exceptions.Timeout:
            print(
                f"Request timed out on attempt "
                f"{attempt + 1}."
            )

        except requests.exceptions.ConnectionError:
            print(
                f"Connection error on attempt "
                f"{attempt + 1}."
            )

        except requests.exceptions.HTTPError as error:
            print("HTTP error:", error)
            break

        except requests.exceptions.RequestException as error:
            print("Request failed:", error)
            break

        time.sleep(3)

    return {
        "title": "Title not found",
        "price": "Price not found",
        "url": url
    }