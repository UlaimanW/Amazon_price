import argparse

from config import WISHLIST_URL, validate_config
from price_checker import check_prices
from storage import load_products, remove_product
from wishlist import sync_wishlist


def list_products():
    products = load_products()

    if not products:
        print("\nNo products are being tracked.")
        return

    print("\n" + "=" * 70)
    print("               Amazon Wishlist Price Tracker")
    print("=" * 70)

    for index, product in enumerate(products, start=1):
        print(f"\nProduct #{index}")
        print("-" * 70)
        print(f"Name         : {product['name']}")
        print(f"Current Price: {product['last_price']} SAR")
        print(f"URL          : {product['url']}")

    print("\n" + "=" * 70)


def run_tracker():
    try:
        validate_config()
    except ValueError as error:
        print(error)
        return

    print("\nStarting wishlist synchronization...\n")
    sync_wishlist(WISHLIST_URL)

    print("\nStarting price check...\n")
    check_prices()

    print("\nTracker run completed.")


def main():
    parser = argparse.ArgumentParser(
        description="Amazon Wishlist Price Tracker"
    )

    parser.add_argument(
        "command",
        choices=[
            "run",
            "sync",
            "check",
            "list",
            "remove",
        ],
        help="Command to run"
    )

    parser.add_argument(
        "value",
        nargs="?",
        help="Product number for remove"
    )

    args = parser.parse_args()

    if args.command == "run":
        run_tracker()

    elif args.command == "sync":
        try:
            validate_config()
        except ValueError as error:
            print(error)
            return

        sync_wishlist(WISHLIST_URL)

    elif args.command == "check":
        check_prices()

    elif args.command == "list":
        list_products()

    elif args.command == "remove":
        if not args.value:
            print("Please provide the product number.")
            return

        try:
            product_number = int(args.value)
        except ValueError:
            print("Product number must be an integer.")
            return

        if remove_product(product_number):
            print("Product removed successfully.")
        else:
            print("Invalid product number.")


if __name__ == "__main__":
    main()