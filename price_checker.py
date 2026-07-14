from notifier import send_telegram_message
from price_history import record_price
from scraper import get_product_info, parse_price
from storage import load_products, save_products


def shorten_name(name, max_length=70):
    if len(name) <= max_length:
        return name

    return name[:max_length].rstrip() + "..."


def check_prices():
    products = load_products()

    for product in products:
        name = product["name"]
        short_name = shorten_name(name)

        url = product["url"]

        last_price = float(product["last_price"])
        was_on_sale = product.get("was_on_sale", False)

        print(f"\nChecking: {name}")

        product_info = get_product_info(url)

        current_price_text = product_info["price"]
        scrape_status = product_info.get("status", "failed")
        is_on_sale = product_info.get("is_on_sale", False)
        discount_text = product_info.get("discount_text")
        original_price = product_info.get("original_price")
        image_url = product_info.get("image_url")

        print("Current price:", current_price_text)
        print("Last price:", last_price)
        print("Previously on sale:", was_on_sale)
        print("Currently on sale:", is_on_sale)

        if (
            scrape_status != "success"
            or
            current_price_text == "Price not found"
            or current_price_text is None
        ):
            print("Could not get price; keeping the last valid price.")
            record_price(
                url=url, name=name, price=None, scrape_status="failed"
            )
            continue

        current_price = parse_price(current_price_text)

        if current_price is None:
            print("Price format invalid, skipping...")
            record_price(
                url=url, name=name, price=None,
                scrape_status="invalid_price"
            )
            continue

        record_price(
            url=url,
            name=name,
            price=current_price,
            is_on_sale=is_on_sale,
            original_price=original_price,
        )

        price_dropped = current_price < last_price

        sale_started = (
            is_on_sale
            and not was_on_sale
        )

        if price_dropped or sale_started:
            alert_reasons = []

            if price_dropped:
                alert_reasons.append("📉 Price dropped")

            if sale_started:
                alert_reasons.append("🔥 Sale started")

            message_lines = [
                "🛒 Amazon Price Tracker",
                "",
                f"📦 {short_name}",
                "",
                *alert_reasons,
                "",
                f"💰 Current price: {current_price:.2f} SAR",
            ]

            if price_dropped:
                price_drop_savings = last_price - current_price

                message_lines.append(
                    f"📉 Previous price: {last_price:.2f} SAR"
                )

                message_lines.append(
                    f"💵 Price drop savings: "
                    f"{price_drop_savings:.2f} SAR"
                )

            if original_price is not None:
                total_savings = original_price - current_price

                message_lines.append(
                    f"🏷️ Original price: "
                    f"{original_price:.2f} SAR"
                )

                if total_savings > 0:
                    message_lines.append(
                        f"💸 You save: "
                        f"{total_savings:.2f} SAR"
                    )

            if discount_text:
                message_lines.append(
                    f"🔖 Discount: {discount_text}"
                )

            message_lines.extend([
                "",
                f"🔗 {url}"
            ])

            message = "\n".join(message_lines)

            send_telegram_message(message)

            if price_dropped and sale_started:
                print(
                    "Telegram alert sent for price drop "
                    "and new sale."
                )
            elif price_dropped:
                print(
                    "Telegram alert sent for price drop."
                )
            else:
                print(
                    "Telegram alert sent for new sale."
                )

        else:
            print(
                "No price drop or new sale detected."
            )

        product["last_price"] = current_price
        product["was_on_sale"] = is_on_sale
        product["original_price"] = original_price
        product["discount_text"] = discount_text
        if image_url:
            product["image_url"] = image_url

    save_products(products)

    print("\nDone checking all products.")
