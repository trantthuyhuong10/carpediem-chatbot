import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.chatbot import ChatBot

BOT_AVATAR = "interface/assets/chatbot_ava.webp"
USER_AVATAR = "interface/assets/user_ava.webp"

st.set_page_config(
    page_title="Carpe Diem",
    page_icon="interface/assets/chatbot_ava.webp",
    layout="wide",
)

# --- Custom CSS ---
st.markdown("""
<style>
/* Chat container */
.stChatMessage {
    padding: 8px 12px;
    margin: 4px 0;
}

/* User message bubble - right aligned by Streamlit default */
div[data-testid="stChatMessage"][data-testid="stChatMessage-user"] div[data-testid="stChatMessageContent"] {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 18px 18px 4px 18px;
    padding: 12px 16px;
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

/* Bot message bubble - left aligned by Streamlit default */
div[data-testid="stChatMessage"][data-testid="stChatMessage-assistant"] div[data-testid="stChatMessageContent"] {
    background: #f0f2f6;
    color: #1a1a2e;
    border-radius: 18px 18px 18px 4px;
    padding: 12px 16px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

/* Avatar styling */
div[data-testid="stChatMessage"] img {
    border-radius: 50%;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}

/* Input area centering */
.input-container {
    display: flex;
    justify-content: center;
    align-items: flex-end;
    gap: 8px;
    padding: 12px 0;
    max-width: 800px;
    margin: 0 auto;
}

/* Product card styling */
.product-card {
    background: white;
    border-radius: 12px;
    padding: 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s, box-shadow 0.2s;
}
.product-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* Hide default streamlit footer */
footer {visibility: hidden;}
footer:after {visibility: hidden;}

/* Main chat area background */
.main .block-container {
    background: linear-gradient(180deg, #f8f9fa 0%, #ffffff 100%);
    border-radius: 16px;
}

/* Suggestion buttons */
div[data-testid="stSidebar"] button[kind="secondary"] {
    text-align: left;
    font-size: 0.85rem;
    padding: 8px 12px;
    border-radius: 8px;
}

/* Divider styling */
hr {
    border: none;
    border-top: 1px solid #e0e0e0;
    margin: 8px 0;
}
</style>
""", unsafe_allow_html=True)

# --- Init state ---
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

def process_message(prompt, image_bytes=None):
    st.session_state.messages.append({"role": "user", "content": prompt, "image": image_bytes})

    avatar = USER_AVATAR if os.path.exists(USER_AVATAR) else "👤"
    with st.chat_message("user", avatar=avatar):
        if image_bytes:
            st.image(image_bytes, width=200)
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=BOT_AVATAR if os.path.exists(BOT_AVATAR) else "🕯️"):
        with st.spinner():
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


# --- Sidebar ---
with st.sidebar:
    st.header("Carpe Diem")
    st.caption("THỦ CÔNG, AN TOÀN, THÂN THIỆN")

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

# --- Main chat area ---
st.title("Carpe Diem")
st.caption("Thủ công, an toàn, thân thiện")

# Render messages from history
for msg in st.session_state.messages:
    if msg["role"] == "user":
        avatar = USER_AVATAR if os.path.exists(USER_AVATAR) else "👤"
        with st.chat_message("user", avatar=avatar):
            if msg.get("image"):
                st.image(msg["image"], width=200)
            st.markdown(msg["content"])
    else:
        avatar = BOT_AVATAR if os.path.exists(BOT_AVATAR) else "🕯️"
        with st.chat_message("assistant", avatar=avatar):
            st.markdown(msg["content"])
            if msg.get("results"):
                st.markdown("**Sản phẩm gợi ý:**")
                cols = st.columns(min(len(msg["results"]), 3))
                for i, product in enumerate(msg["results"]):
                    with cols[i % 3]:
                        render_product_card(product, f"prod_{id(msg)}_{i}")

# --- Image preview ---
if st.session_state.pending_image:
    st.divider()
    col_preview, col_clear = st.columns([5, 1])
    with col_preview:
        st.image(st.session_state.pending_image, width=150)
    with col_clear:
        if st.button("✕ Xóa ảnh", key="clear_img"):
            clear_pending_image()
            st.rerun()

# --- Input area (centered) ---
st.divider()
col_left, col_input, col_right = st.columns([1, 10, 1])
with col_input:
    uploaded = st.file_uploader(
        "Đính kèm ảnh",
        type=["png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
        key=f"uploader_{st.session_state.uploader_key}",
    )
    if uploaded and not st.session_state.pending_image:
        st.session_state.pending_image = uploaded.read()
        st.rerun()

    prompt = st.chat_input("Nhập câu hỏi", key="chat_input_main")

if prompt:
    image_bytes = st.session_state.pending_image
    process_message(prompt, image_bytes)
    clear_pending_image()
    st.rerun()
