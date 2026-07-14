import json


PRODUCTS_FILE = "products.json"


def load_products():
    try:
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as error:
        raise ValueError(f"{PRODUCTS_FILE} contains invalid JSON") from error

    if not isinstance(data, list):
        raise ValueError(f"{PRODUCTS_FILE} must contain a JSON list")

    return data


def save_products(products):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as file:
        json.dump(products, file, indent=4, ensure_ascii=False)


def product_exists(url):
    products = load_products()

    for product in products:
        if product["url"] == url:
            return True

    return False


def add_product(product):
    products = load_products()
    products.append(product)
    save_products(products)


def remove_product(index):
    products = load_products()

    if index < 1 or index > len(products):
        return False

    products.pop(index - 1)
    save_products(products)

    return True





def add_wishlist_product(product):
    products = load_products()

    for existing_product in products:
        if existing_product["url"] == product["url"]:
            return False

    products.append(product)
    save_products(products)

    return True

def replace_products(products):
    save_products(products)
