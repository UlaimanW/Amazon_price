from notifier import send_telegram_message
from scraper import get_product_info, parse_price
from storage import load_products, save_products


def check_prices():
    products = load_products()

    for product in products:
        name = product["name"]
        url = product["url"]
        last_price = float(product["last_price"])

        print(f"\nChecking: {name}")

        product_info = get_product_info(url)
        current_price_text = product_info["price"]

        print("Current price:", current_price_text)
        print("Last price:", last_price)

        if (
            current_price_text == "Price not found"
            or current_price_text is None
        ):
            print("Could not get price, skipping...")
            continue

        current_price = parse_price(current_price_text)

        if current_price is None:
            print("Price format invalid, skipping...")
            continue

        if current_price < last_price:
            message = (
                f"Price drop detected!\n\n"
                f"{name}\n"
                f"Old price: {last_price} SAR\n"
                f"New price: {current_price} SAR\n\n"
                f"{url}"
            )

            send_telegram_message(message)
            print("Telegram alert sent for price drop.")
        else:
            print("No price drop detected.")

        product["last_price"] = current_price

    save_products(products)

    print("\nDone checking all products.")