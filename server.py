"""
پیام‌رسان - سرور Python
اجرا: python server.py
نیاز به نصب: pip install websockets
"""

import asyncio
import websockets
import json
import http.server
import threading
import os
from datetime import datetime

# ذخیره اتصالات و پیام‌ها
connected_clients = {}  # {websocket: username}
chat_rooms = {
    "عمومی": [],
    "فناوری": [],
    "موزیک": [],
}

HTML_FILE = "client.html"

# سرور HTTP برای ارسال فایل HTML
class HTMLHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # غیرفعال کردن لاگ HTTP

def start_http_server():
    handler = HTMLHandler
    httpd = http.server.HTTPServer(("0.0.0.0", 8080), handler)
    print("🌐 سرور HTTP روی پورت 8080 شروع به کار کرد")
    httpd.serve_forever()

async def broadcast_to_room(room, message, exclude=None):
    """ارسال پیام به همه کاربران یک اتاق"""
    for client, data in list(connected_clients.items()):
        if client != exclude and data.get("room") == room:
            try:
                await client.send(json.dumps(message))
            except:
                pass

async def broadcast_user_list(room):
    """ارسال لیست کاربران آنلاین"""
    users_in_room = [
        data["username"]
        for data in connected_clients.values()
        if data.get("room") == room
    ]
    msg = {"type": "users", "users": users_in_room, "room": room}
    for client, data in list(connected_clients.items()):
        if data.get("room") == room:
            try:
                await client.send(json.dumps(msg))
            except:
                pass

async def handler(websocket):
    username = None
    current_room = None

    try:
        async for raw in websocket:
            data = json.loads(raw)
            msg_type = data.get("type")

            # ورود کاربر
            if msg_type == "join":
                username = data["username"].strip()[:20]
                room = data.get("room", "عمومی")
                if room not in chat_rooms:
                    room = "عمومی"
                current_room = room

                connected_clients[websocket] = {
                    "username": username,
                    "room": room
                }

                # ارسال تاریخچه پیام‌ها
                history = chat_rooms[room][-50:]  # آخرین ۵۰ پیام
                await websocket.send(json.dumps({
                    "type": "history",
                    "messages": history,
                    "room": room,
                    "rooms": list(chat_rooms.keys())
                }))

                # اطلاع‌رسانی ورود
                join_msg = {
                    "type": "system",
                    "text": f"🟢 {username} وارد اتاق شد",
                    "time": datetime.now().strftime("%H:%M"),
                    "room": room
                }
                await broadcast_to_room(room, join_msg)
                await broadcast_user_list(room)
                print(f"✅ {username} به اتاق '{room}' پیوست")

            # تغییر اتاق
            elif msg_type == "switch_room":
                new_room = data.get("room")
                if new_room in chat_rooms and username:
                    old_room = current_room

                    # اطلاع‌رسانی خروج از اتاق قبلی
                    leave_msg = {
                        "type": "system",
                        "text": f"🔴 {username} اتاق را ترک کرد",
                        "time": datetime.now().strftime("%H:%M"),
                        "room": old_room
                    }
                    await broadcast_to_room(old_room, leave_msg, exclude=websocket)

                    current_room = new_room
                    connected_clients[websocket]["room"] = new_room

                    # ارسال تاریخچه اتاق جدید
                    history = chat_rooms[new_room][-50:]
                    await websocket.send(json.dumps({
                        "type": "history",
                        "messages": history,
                        "room": new_room,
                        "rooms": list(chat_rooms.keys())
                    }))

                    # اطلاع‌رسانی ورود به اتاق جدید
                    join_msg = {
                        "type": "system",
                        "text": f"🟢 {username} وارد اتاق شد",
                        "time": datetime.now().strftime("%H:%M"),
                        "room": new_room
                    }
                    await broadcast_to_room(new_room, join_msg)
                    await broadcast_user_list(old_room)
                    await broadcast_user_list(new_room)

            # ارسال پیام
            elif msg_type == "message":
                if username and current_room:
                    text = data.get("text", "").strip()[:500]
                    if text:
                        msg = {
                            "type": "message",
                            "username": username,
                            "text": text,
                            "time": datetime.now().strftime("%H:%M"),
                            "room": current_room
                        }
                        chat_rooms[current_room].append(msg)
                        # نگه‌داری فقط ۲۰۰ پیام آخر
                        if len(chat_rooms[current_room]) > 200:
                            chat_rooms[current_room] = chat_rooms[current_room][-200:]

                        await broadcast_to_room(current_room, msg)
                        print(f"💬 [{current_room}] {username}: {text[:40]}")

            # تایپ کردن
            elif msg_type == "typing":
                if username and current_room:
                    typing_msg = {
                        "type": "typing",
                        "username": username,
                        "room": current_room
                    }
                    await broadcast_to_room(current_room, typing_msg, exclude=websocket)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if websocket in connected_clients:
            del connected_clients[websocket]
        if username and current_room:
            leave_msg = {
                "type": "system",
                "text": f"🔴 {username} خارج شد",
                "time": datetime.now().strftime("%H:%M"),
                "room": current_room
            }
            await broadcast_to_room(current_room, leave_msg)
            await broadcast_user_list(current_room)
            print(f"❌ {username} قطع شد")

async def main():
    print("=" * 45)
    print("   🚀 پیام‌رسان - سرور راه‌اندازی شد")
    print("=" * 45)

    # شروع HTTP server در thread جداگانه
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()

    # شروع WebSocket server
    port = int(os.environ.get("PORT", 8765))
    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"⚡ WebSocket روی پورت {port} آماده است")
        print()
        print("📱 آدرس‌های اتصال:")
        print("   مرورگر همین دستگاه: http://localhost:8080/client.html")
        print("   دستگاه دیگر در شبکه: http://[IP-دستگاه]:8080/client.html")
        print()
        print("💡 برای یافتن IP دستگاه: Settings > WiFi > IP Address")
        print("=" * 45)
        await asyncio.Future()  # اجرای دائمی

if __name__ == "__main__":
    asyncio.run(main())
