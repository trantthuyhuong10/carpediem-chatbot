#!/usr/bin/env python3
"""
Demo CLI cho Carpediem Chatbot
Chạy: python scripts/demo_cli.py
"""

import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

import json
from dotenv import load_dotenv

load_dotenv()

BANNER = """
╔══════════════════════════════════════════════════════╗
║         CARPEDEIM CHATBOT - DEMO CLI                 ║
║         Nến thơm · Tinh dầu · Quà tặng               ║
╚══════════════════════════════════════════════════════╝
"""

COMMANDS = """
Commands đặc biệt:
  /stats      - Xem thống kê graph database
  /reset      - Xóa lịch sử chat
  /image <path> - Gửi ảnh để phân tích
  /help       - Hiện danh sách lệnh
  /exit       - Thoát
"""

def print_product_results(results):
    if not results:
        return
    print("\n  ┌─ Sản phẩm gợi ý ──────────────────────────┐")
    for i, p in enumerate(results, 1):
        print(f"  │ {i}. {p['name']}")
        print(f"  │    Giá: {p.get('price', 'N/A')}")
        if p.get('original_price'):
            print(f"  │    Giá gốc: {p['original_price']}")
        if p.get('discount'):
            print(f"  │    {p['discount']}")
        cats = ", ".join(p.get("categories", []))
        if cats:
            print(f"  │    Danh mục: {cats}")
        print(f"  │    Link: {p['url']}")
        if i < len(results):
            print(f"  │ {'─' * 42}")
    print("  └────────────────────────────────────────────┘\n")


def main():
    print(BANNER)

    try:
        from src.chatbot import ChatBot
    except Exception as e:
        print(f"[LỖI] Không thể import ChatBot: {e}")
        print("Kiểm tra: pip install -r requirements.txt")
        print("          Neo4j đang chạy tại localhost:7687")
        print("          GEMINI_API_KEY đã được set trong .env")
        sys.exit(1)

    try:
        bot = ChatBot()
    except Exception as e:
        print(f"[LỖI] Không thể khởi tạo ChatBot: {e}")
        sys.exit(1)

    print("[OK] Chatbot đã sẵn sàng!")
    print("     Gõ câu hỏi hoặc /help để xem lệnh")
    print()

    while True:
        try:
            user_input = input("Bạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[BYE] Tạm biệt!")
            bot.close()
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()

            if cmd == "/exit" or cmd == "/quit":
                print("[BYE] Tạm biệt!")
                bot.close()
                break

            elif cmd == "/help":
                print(COMMANDS)

            elif cmd == "/stats":
                stats = bot.get_stats()
                print(f"\n  Thống kê:")
                print(f"     Sản phẩm: {stats['products']}")
                print(f"     Danh mục: {stats['categories']}")
                print(f"     Tin nhắn: {stats['chat_messages']}")
                print()

            elif cmd == "/reset":
                bot.reset_history()
                print("[OK] Đã xóa lịch sử chat\n")

            elif cmd == "/image":
                if len(parts) < 2:
                    print("[LỖI] Usage: /image <đường_dẫn_ảnh>\n")
                    continue
                image_path = parts[1]
                if not os.path.exists(image_path):
                    print(f"[LỖI] Không tìm thấy ảnh: {image_path}\n")
                    continue
                print("\n[AI] Đang phân tích ảnh...")
                try:
                    answer, results = bot.handle_image(image_path)
                    print(f"\n  {answer}\n")
                    if results:
                        print_product_results(results)
                except Exception as e:
                    print(f"[LỖI] Không thể phân tích ảnh: {e}\n")

            else:
                print(f"[LỖI] Lệnh không hợp lệ: {cmd}")
                print(COMMANDS)

            continue

        print("\n[AI] Đang xử lý...")
        try:
            answer, results = bot.chat(user_input)
            print(f"\n  {answer}")
            if results:
                print_product_results(results)
        except Exception as e:
            print(f"\n[LỖI] {e}")
            print("Thử lại hoặc gõ /help để xem lệnh\n")


if __name__ == "__main__":
    main()
