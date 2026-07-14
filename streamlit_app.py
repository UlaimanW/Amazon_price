import html

import pandas as pd
import streamlit as st

from dashboard_utils import chunk_products
from price_history import (
    count_products_with_price_drops,
    get_price_history,
    get_product_stats,
)
from storage import load_products


st.set_page_config(page_title="Amazon Price Tracker", page_icon="🛒", layout="wide")

st.markdown(
    """
    <style>
    .block-container {max-width: 1180px; padding-top: 2rem;}
    [data-testid="stMetric"] {
        background: #ffffff; border: 1px solid #e5e7eb;
        border-radius: 14px; padding: 16px;
        box-shadow: 0 3px 12px rgba(15, 23, 42, 0.04);
    }
    .product-card {
        height: 500px; width: 100%; box-sizing: border-box;
        display: flex; flex-direction: column;
        padding: 18px; margin-bottom: 18px;
        border: 1px solid #d1d5db; border-radius: 12px;
        background: #ffffff;
    }
    .product-image-box {
        height: 225px; width: 100%; display: flex;
        align-items: center; justify-content: center; margin: 4px 0 10px;
    }
    .product-image-box img {
        display: block; width: 100%; height: 100%; object-fit: contain;
    }
    .image-placeholder {color: #9ca3af; font-size: .85rem; text-align: center;}
    .product-price {display: flex; align-items: baseline; gap: 12px; margin: 4px 0;}
    .current-price {font-size: 1.65rem; font-weight: 650; color: #111827;}
    .current-price sup {font-size: .8rem; vertical-align: super; margin-left: 2px;}
    .currency {font-size: .85rem; color: #4b5563; margin-right: 4px;}
    .discount {font-size: 1.3rem; color: #e11d48; font-weight: 500;}
    .list-price {
        min-height: 1.35rem; font-size: .86rem;
        color: #6b7280; margin-bottom: 8px;
    }
    .list-price s {margin-left: 5px;}
    .product-name {
        font-size: 1.02rem; font-weight: 650; line-height: 1.35;
        height: 2.7em; margin-bottom: 8px;
        display: -webkit-box; -webkit-line-clamp: 2;
        -webkit-box-orient: vertical; overflow: hidden;
    }
    .sale-label {font-size: .9rem; color: #6b7280; margin-top: 2px;}
    .amazon-button {
        display: block; width: 100%; box-sizing: border-box;
        margin-top: auto; padding: 10px 12px; border: 1px solid #d1d5db;
        border-radius: 9px; color: #111827 !important;
        text-align: center; text-decoration: none !important;
    }
    .amazon-button:hover {border-color: #f59e0b; color: #92400e !important;}
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value):
    return "—" if value is None else f"{value:,.2f} SAR"


def sale_price_html(product):
    price = float(product["last_price"])
    whole, decimal = f"{price:,.2f}".split(".")
    discount = product.get("discount_text")
    original_price = product.get("original_price")

    price_line = (
        '<div class="product-price">'
        f'<span class="current-price"><span class="currency">SAR</span>'
        f'{whole}<sup>{decimal}</sup></span>'
    )
    if discount:
        price_line += f'<span class="discount">{discount}</span>'
    price_line += "</div>"

    if original_price is not None and float(original_price) > price:
        price_line += (
            '<div class="list-price">List price: '
            f'<s>{float(original_price):,.2f} SAR</s></div>'
        )
    else:
        price_line += '<div class="list-price">&nbsp;</div>'

    return price_line


def product_card_html(product):
    safe_name = html.escape(product["name"], quote=True)
    safe_product_url = html.escape(product["url"], quote=True)
    image_url = product.get("image_url")

    if image_url:
        safe_image_url = html.escape(image_url, quote=True)
        image_html = (
            f'<img src="{safe_image_url}" alt="{safe_name}" loading="lazy">'
        )
    else:
        image_html = '<span class="image-placeholder">Image available after the next check.</span>'

    sale_label = "On sale" if product.get("was_on_sale") else "Regular price"
    return (
        '<div class="product-card">'
        f'<div class="product-name" title="{safe_name}">{safe_name}</div>'
        f'<div class="product-image-box">{image_html}</div>'
        f'{sale_price_html(product)}'
        f'<div class="sale-label">{sale_label}</div>'
        f'<a class="amazon-button" href="{safe_product_url}" '
        'target="_blank" rel="noopener noreferrer">View on Amazon</a>'
        '</div>'
    )


products = load_products()

st.title("Amazon Wishlist Price Tracker")
st.caption("Current prices and historical trends in one place.")

if not products:
    st.info("No products are currently tracked. Run the wishlist sync first.")
    st.stop()

sale_count = sum(bool(product.get("was_on_sale")) for product in products)
price_drop_count = count_products_with_price_drops(
    product["url"] for product in products
)

metric_columns = st.columns(3)
metric_columns[0].metric("Tracked products", len(products))
metric_columns[1].metric("Currently on sale", sale_count)
metric_columns[2].metric("Products with price drops", price_drop_count)

st.subheader("Products")
for product_row in chunk_products(products):
    product_columns = st.columns(3)
    for column, product in zip(product_columns, product_row):
        with column:
            st.markdown(product_card_html(product), unsafe_allow_html=True)

st.subheader("Product history")
selected_index = st.selectbox(
    "Choose a product",
    range(len(products)),
    format_func=lambda index: products[index]["name"],
)
selected = products[selected_index]
stats = get_product_stats(selected["url"])
history_rows = get_price_history(selected["url"])

detail_columns = st.columns(4)
detail_columns[0].metric("Current", money(float(selected["last_price"])))
detail_columns[1].metric("Lowest", money(stats["lowest_price"]))
detail_columns[2].metric("Highest", money(stats["highest_price"]))
detail_columns[3].metric("Average", money(stats["average_price"]))

successful_rows = [
    row for row in history_rows
    if row["scrape_status"] == "success" and row["price"] is not None
]
if successful_rows:
    chart_data = pd.DataFrame(successful_rows)
    chart_data["checked_at"] = pd.to_datetime(chart_data["checked_at"], utc=True)
    chart_data = chart_data.set_index("checked_at")
    st.line_chart(chart_data[["price"]], y_label="Price (SAR)", x_label="Checked at")
else:
    st.info("Price history will appear after the next successful tracker run.")
