import re


def is_confirmed_sale(current_price, discount_text=None, original_price=None):
    """Return True only when product-level pricing proves there is a sale."""
    if discount_text:
        match = re.search(r"-?\s*(\d+(?:\.\d+)?)\s*%", str(discount_text))
        if match and float(match.group(1)) > 0:
            return True

    try:
        return (
            current_price is not None
            and original_price is not None
            and float(original_price) > float(current_price)
        )
    except (TypeError, ValueError):
        return False


def product_is_on_sale(product):
    return is_confirmed_sale(
        product.get("last_price"),
        product.get("discount_text"),
        product.get("original_price"),
    )


def product_discount_percent(product):
    discount_text = str(product.get("discount_text") or "").strip()
    if discount_text:
        try:
            return abs(float(discount_text.replace("%", "")))
        except ValueError:
            pass

    current_price = product.get("last_price")
    original_price = product.get("original_price")
    if current_price is None or original_price is None:
        return 0.0

    current_price = float(current_price)
    original_price = float(original_price)
    if original_price <= 0 or original_price <= current_price:
        return 0.0
    return ((original_price - current_price) / original_price) * 100
