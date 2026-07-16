import html

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from app import run_tracker
from ai_assistant import ask_shopping_assistant
from config import GROQ_API_KEY
from dashboard_utils import (
    EVENT_DETAILS,
    build_price_timeline,
    build_product_badges,
    chunk_products,
    filter_products,
)
from price_history import (
    get_latest_price_change_events,
    get_price_history,
    get_product_stats,
)
from sale_utils import product_is_on_sale
from storage import load_products
from tracker_status import format_last_successful_run, load_last_successful_run


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
    .product-badges {
        min-height: 26px; display: flex; align-items: center;
        flex-wrap: wrap; gap: 6px; margin-bottom: 7px;
    }
    .product-badge {
        display: inline-flex; align-items: center;
        min-height: 22px; padding: 2px 8px;
        border-radius: 999px; font-size: .72rem;
        font-weight: 700; letter-spacing: .02em;
    }
    .product-badge.sale {
        color: #9a3412; background: #ffedd5; border: 1px solid #fdba74;
    }
    .product-badge.price-drop {
        color: #166534; background: #dcfce7; border: 1px solid #86efac;
    }
    .product-badge.price-increase {
        color: #991b1b; background: #fee2e2; border: 1px solid #fca5a5;
    }
    .product-image-box {
        height: 210px; width: 100%; display: flex;
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
    div[data-testid="stButton"] {margin-top: 0;}
    .st-key-clear_filters_button div[data-testid="stButton"] {
        margin-top: 1.75rem;
    }
    div[data-testid="stButton"] > button {
        min-height: 3rem;
        padding: 0.45rem 0.9rem;
        border: 1px solid transparent;
        border-radius: 8px;
        background: #f0f2f6;
        color: #31333f;
        font-size: 0.9rem;
        font-weight: 600;
        box-shadow: none;
        transition: border-color 0.15s ease, background 0.15s ease;
    }
    div[data-testid="stButton"] > button p {color: #31333f;}
    div[data-testid="stButton"] > button:hover {
        border-color: #d1d5db;
        background: #e6e9ef;
        color: #31333f;
        box-shadow: none;
    }
    div[data-testid="stButton"] > button:hover p {color: #31333f;}
    div[data-testid="stButton"] > button:focus:not(:active) {
        border-color: #9ca3af;
        color: #31333f;
        box-shadow: 0 0 0 2px rgba(156, 163, 175, 0.20);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def money(value):
    return "—" if value is None else f"{value:,.2f} SAR"


def scroll_to_latest_chat_message():
    components.html(
        """
        <script>
        const scrollToLatestMessage = () => {
            const componentFrame = window.frameElement;
            if (componentFrame) {
                componentFrame.scrollIntoView({
                    behavior: "smooth",
                    block: "end"
                });
            }
        };
        window.requestAnimationFrame(() => {
            window.requestAnimationFrame(scrollToLatestMessage);
        });
        </script>
        """,
        height=0,
        scrolling=False,
    )


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


def product_card_html(product, price_change=None):
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

    badges = build_product_badges(product, price_change)
    badges_html = "".join(
        f'<span class="product-badge {badge["kind"]}">'
        f'{html.escape(badge["label"])}</span>'
        for badge in badges
    )

    sale_label = "On sale" if product_is_on_sale(product) else "Regular price"
    return (
        '<div class="product-card">'
        f'<div class="product-badges">{badges_html}</div>'
        f'<div class="product-name" title="{safe_name}">{safe_name}</div>'
        f'<div class="product-image-box">{image_html}</div>'
        f'{sale_price_html(product)}'
        f'<div class="sale-label">{sale_label}</div>'
        f'<a class="amazon-button" href="{safe_product_url}" '
        'target="_blank" rel="noopener noreferrer">View on Amazon</a>'
        '</div>'
    )


st.title("Amazon Wishlist Price Tracker")
st.caption("Current prices and historical trends in one place.")

if "tracker_running" not in st.session_state:
    st.session_state.tracker_running = False

run_now = st.button(
    "Run tracker now",
    key="run_tracker_button",
    disabled=st.session_state.tracker_running,
)
if run_now and not st.session_state.tracker_running:
    st.session_state.tracker_running = True
    try:
        with st.spinner(
            "Synchronizing the wishlist and checking prices..."
        ):
            run_tracker(raise_errors=True)
    except Exception as error:
        st.error(f"Tracker run failed: {error}")
    else:
        st.success("Tracker completed successfully. Dashboard data is updated.")
    finally:
        st.session_state.tracker_running = False

st.caption(format_last_successful_run(load_last_successful_run()))

products = load_products()

if not products:
    st.info("No products are currently tracked. Run the wishlist sync first.")
    st.stop()

sale_count = sum(product_is_on_sale(product) for product in products)
price_change_events = get_latest_price_change_events(
    product["url"] for product in products
)
price_drop_count = sum(change < 0 for change in price_change_events.values())

metric_columns = st.columns(3)
metric_columns[0].metric("Tracked products", len(products))
metric_columns[1].metric("Currently on sale", sale_count)
metric_columns[2].metric("Products with price drops", price_drop_count)

st.subheader("Products")


def clear_product_filters():
    st.session_state.product_search = ""
    st.session_state.product_sort = "Name"

filter_columns = st.columns([3, 2, 1])
search = filter_columns[0].text_input(
    "Search products", placeholder="Product name", key="product_search"
)
sort_by = filter_columns[1].selectbox(
    "Sort by",
    [
        "Name",
        "Price: lowest first",
        "Price: highest first",
        "Largest discount",
    ],
    key="product_sort",
)
filter_columns[2].button(
    "↻ Clear filters",
    key="clear_filters_button",
    on_click=clear_product_filters,
)

visible_products = filter_products(
    products,
    search=search,
    sort_by=sort_by,
)
st.caption(f"Showing {len(visible_products)} of {len(products)} products.")

for product_row in chunk_products(visible_products):
    product_columns = st.columns(3)
    for column, product in zip(product_columns, product_row):
        with column:
            st.markdown(
                product_card_html(
                    product, price_change_events.get(product["url"])
                ),
                unsafe_allow_html=True,
            )

if not visible_products:
    st.info("No products match the selected filters.")

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

observations, timeline_events = build_price_timeline(history_rows)
if observations:
    chart_data = pd.DataFrame(observations)
    chart_data["checked_at"] = pd.to_datetime(chart_data["checked_at"], utc=True)

    price_line = alt.Chart(chart_data).mark_line(
        color="#1677d2", strokeWidth=3
    ).encode(
        x=alt.X("checked_at:T", title="Checked at"),
        y=alt.Y("price:Q", title="Price (SAR)", scale=alt.Scale(zero=False)),
        tooltip=[
            alt.Tooltip("checked_at:T", title="Checked at"),
            alt.Tooltip("price:Q", title="Price", format=",.2f"),
        ],
    )

    chart_layers = [price_line]
    if timeline_events:
        event_data = pd.DataFrame(timeline_events)
        event_data["checked_at"] = pd.to_datetime(
            event_data["checked_at"], utc=True
        )
        event_colors = [
            EVENT_DETAILS[event]["color"] for event in EVENT_DETAILS
        ]
        event_markers = alt.Chart(event_data).mark_point(
            filled=True, size=120, stroke="white", strokeWidth=1
        ).encode(
            x="checked_at:T",
            y="price:Q",
            color=alt.Color(
                "event:N",
                title="Event",
                scale=alt.Scale(
                    domain=list(EVENT_DETAILS), range=event_colors
                ),
            ),
            tooltip=[
                alt.Tooltip("event:N", title="Event"),
                alt.Tooltip("checked_at:T", title="Checked at"),
                alt.Tooltip("previous_price:Q", title="Previous", format=",.2f"),
                alt.Tooltip("price:Q", title="Current", format=",.2f"),
                alt.Tooltip("price_change:Q", title="Change", format="+,.2f"),
            ],
        )
        chart_layers.append(event_markers)

    timeline_chart = alt.layer(*chart_layers).properties(height=360)
    st.altair_chart(timeline_chart, width="stretch")

    st.markdown("#### Price and sale events")
    if timeline_events:
        event_table = pd.DataFrame(timeline_events).sort_values(
            ["checked_at", "event_order"], ascending=[False, True]
        )
        event_table["Date"] = pd.to_datetime(
            event_table["checked_at"], utc=True
        ).dt.strftime("%Y-%m-%d %H:%M UTC")
        event_table["Event"] = event_table["event"]
        event_table["Previous price"] = event_table["previous_price"].map(money)
        event_table["Current price"] = event_table["price"].map(money)
        event_table["Change"] = event_table["price_change"].map(
            lambda value: "—" if value is None else f"{value:+,.2f} SAR"
        )
        st.dataframe(
            event_table[
                ["Date", "Event", "Previous price", "Current price", "Change"]
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No price or sale changes have been recorded for this product yet.")
else:
    st.info("Price history will appear after the next successful tracker run.")

st.subheader("AI Shopping Assistant")
st.caption(
    "Ask naturally about tracked prices, discounts, history, or customer reviews."
)

if not GROQ_API_KEY:
    st.info("Add GROQ_API_KEY to .env to enable the AI assistant.")
else:
    if "ai_chat_messages" not in st.session_state:
        st.session_state.ai_chat_messages = []

    review_product_index = st.selectbox(
        "Product for review questions (optional)",
        [None, *range(len(products))],
        format_func=lambda index: (
            "Automatically detect from my question"
            if index is None else products[index]["name"]
        ),
        key="ai_review_product",
    )
    selected_review_product = (
        products[review_product_index]
        if review_product_index is not None else None
    )

    if st.session_state.ai_chat_messages:
        if st.button(
            "↻ Clear conversation",
            key="clear_ai_conversation",
            type="secondary",
        ):
            st.session_state.ai_chat_messages = []
            st.rerun()

    for message in st.session_state.ai_chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    with st.form("ai_chat_form", clear_on_submit=True):
        user_question = st.text_input(
            "Message",
            placeholder=(
                "Ask something, for example: Summarize the reviews "
                "for the headphones."
            ),
            label_visibility="collapsed",
        )
        send_question = st.form_submit_button("Send")

    user_question = user_question.strip() if send_question else ""
    if user_question:
        prior_messages = list(st.session_state.ai_chat_messages)
        st.session_state.ai_chat_messages.append({
            "role": "user", "content": user_question
        })
        with st.chat_message("user"):
            st.markdown(user_question)

        with st.chat_message("assistant"):
            with st.spinner("Checking your tracker data and reviews..."):
                try:
                    assistant_answer = ask_shopping_assistant(
                        user_question,
                        products,
                        conversation=prior_messages,
                        api_key=GROQ_API_KEY,
                        selected_product=selected_review_product,
                    )
                except Exception as error:
                    error_text = str(error).strip()
                    if "connection" in error_text.casefold():
                        assistant_answer = (
                            "I could not reach the AI service. Please try again. "
                            "If it continues, restart the dashboard."
                        )
                    else:
                        assistant_answer = (
                            f"I could not answer that: {error_text}"
                        )
            st.markdown(assistant_answer)

        st.session_state.ai_chat_messages.append({
            "role": "assistant", "content": assistant_answer
        })
        scroll_to_latest_chat_message()
