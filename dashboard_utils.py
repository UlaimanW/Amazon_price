def chunk_products(products, columns=3):
    return [
        products[start:start + columns]
        for start in range(0, len(products), columns)
    ]


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


def filter_products(products, *, search="", sort_by="Name"):
    """Filter and sort dashboard products without changing their saved data."""
    search = search.strip().casefold()
    filtered = []

    for product in products:
        if search and search not in product.get("name", "").casefold():
            continue
        filtered.append(product)

    sort_keys = {
        "Name": lambda product: product.get("name", "").casefold(),
        "Price: lowest first": lambda product: float(
            product.get("last_price") or float("inf")
        ),
        "Price: highest first": lambda product: -float(
            product.get("last_price") or 0
        ),
        "Largest discount": lambda product: -product_discount_percent(product),
    }
    return sorted(filtered, key=sort_keys.get(sort_by, sort_keys["Name"]))


EVENT_DETAILS = {
    "Price dropped": {"color": "#16a34a", "order": 1},
    "Price increased": {"color": "#dc2626", "order": 2},
    "Sale started": {"color": "#f59e0b", "order": 3},
    "Sale ended": {"color": "#7f1d1d", "order": 4},
}


def build_price_timeline(history_rows):
    """Return successful price observations and their meaningful events."""
    observations = []
    events = []

    for row in history_rows:
        if row.get("scrape_status") != "success" or row.get("price") is None:
            continue

        observation = {
            "checked_at": row["checked_at"],
            "price": float(row["price"]),
        }
        observations.append(observation)

        event_names = []
        price_change = row.get("price_change")
        if row.get("price_dropped"):
            event_names.append("Price dropped")
        elif price_change is not None and float(price_change) > 0:
            event_names.append("Price increased")
        if row.get("sale_started"):
            event_names.append("Sale started")
        if row.get("sale_ended"):
            event_names.append("Sale ended")

        for event_name in event_names:
            events.append({
                **observation,
                "event": event_name,
                "previous_price": row.get("previous_price"),
                "price_change": price_change,
                "event_order": EVENT_DETAILS[event_name]["order"],
            })

    return observations, events
