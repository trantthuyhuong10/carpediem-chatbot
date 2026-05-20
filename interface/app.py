import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.chatbot import ChatBot

st.set_page_config(
    page_title="Carpe Diem",
    layout="wide",
)

if "bot" not in st.session_state:
    try:
        st.session_state.bot = ChatBot()
    except Exception as e:
        st.error(f"Không thể khởi tạo ChatBot: {e}")
        st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_image" not in st.session_state:
    st.session_state.pending_image = None

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0


def clear_pending_image():
    st.session_state.pending_image = None
    st.session_state.uploader_key += 1


def render_product_card(product, key):
    with st.container(border=True):
        cols = st.columns([1, 3])
        with cols[0]:
            img_url = product.get("image", "")
            if img_url:
                st.image(img_url, use_container_width=True)
            else:
                st.markdown("🕯️")
        with cols[1]:
            st.markdown(f"**{product['name']}**")
            price = product.get("price", "Liên hệ")
            original = product.get("original_price", "")
            discount = product.get("discount", "")
            if original and original != price:
                st.markdown(f"~~{original}~~ → **{price}**")
                if discount:
                    st.caption(discount)
            else:
                st.markdown(f"**{price}**")
            cats = product.get("categories", [])
            if cats:
                st.caption(" | ".join(cats))
            st.markdown(f"[Xem sản phẩm →]({product['url']})")


def get_stats():
    try:
        return st.session_state.bot.get_stats()
    except Exception:
        return {"products": "N/A", "categories": "N/A", "chat_messages": len(st.session_state.messages)}


def process_message(prompt, image_bytes=None):
    st.session_state.messages.append({"role": "user", "content": prompt, "image": image_bytes})
    with st.chat_message("assistant"):
        with st.spinner("Đang xử lý..."):
            try:
                answer, results = st.session_state.bot.chat(prompt, image=image_bytes)
                st.markdown(answer)
                if results:
                    st.markdown("**Sản phẩm gợi ý:**")
                    cols = st.columns(min(len(results), 3))
                    for i, product in enumerate(results):
                        with cols[i % 3]:
                            render_product_card(product, f"result_{i}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "results": results,
                })
            except Exception as e:
                error_msg = f"Lỗi: {e}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg,
                    "results": [],
                })


with st.sidebar:
    st.header("Carpe Diem")
    st.caption("“THỦ CÔNG, AN TOÀN, THÂN THIỆN”")

    st.divider()

    stats = get_stats()
    st.subheader("Thống kê")
    st.metric("Sản phẩm", stats["products"])
    st.metric("Danh mục", stats["categories"])
    st.metric("Tin nhắn", stats["chat_messages"])

    st.divider()

    if st.button("Xóa lịch sử chat", use_container_width=True):
        st.session_state.bot.reset_history()
        st.session_state.messages = []
        clear_pending_image()
        st.rerun()

    st.divider()
    st.caption("Gợi ý:")
    suggestions = [
        "Gợi ý nến thơm dưới 500k",
        "Quà sinh nhật cho bạn gái",
        "Tinh dầu thư giãn",
        "Giftset tân gia",
        "Carpediem là thương hiệu gì?",
    ]
    for s in suggestions:
        if st.button(s, use_container_width=True, type="secondary"):
            process_message(s)
            st.rerun()

st.title("Carpe Diem")
st.caption("“Thủ công, an toàn, thân thiện”")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("image"):
            st.image(msg["image"], width=200)
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("results"):
            st.markdown("**Sản phẩm gợi ý:**")
            cols = st.columns(min(len(msg["results"]), 3))
            for i, product in enumerate(msg["results"]):
                with cols[i % 3]:
                    render_product_card(product, f"prod_{id(msg)}_{i}")

st.divider()

if st.session_state.pending_image:
    col_preview, col_clear = st.columns([5, 2])
    with col_preview:
        st.image(st.session_state.pending_image, width=150)
    with col_clear:
        if st.button("✕", key="clear_img"):
            clear_pending_image()
            st.rerun()

col_attach, col_input = st.columns([4, 11])

with col_attach:
    uploaded = st.file_uploader(
        "📎",
        type=["png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
        key=f"uploader_{st.session_state.uploader_key}",
    )
    if uploaded and not st.session_state.pending_image:
        st.session_state.pending_image = uploaded.read()
        st.rerun()

with col_input:
    prompt = st.chat_input("Nhập câu hỏi", key="chat_input_main")

if prompt:
    image_bytes = st.session_state.pending_image
    process_message(prompt, image_bytes)
    clear_pending_image()
    st.rerun()
