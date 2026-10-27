"""
Telegram kurulum yardımcısı
1) Telegram'da botuna herhangi bir mesaj at ("merhaba")
2) python telegram_test.py
   → chat id'ni bulur, .env'de TELEGRAM_CHAT_ID yoksa ekler ve test mesajı yollar
"""
import os
import sys

import requests
from dotenv import load_dotenv

DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(DIR, ".env")
load_dotenv(ENV_FILE)

token = os.getenv("TELEGRAM_TOKEN")
if not token:
    sys.exit(".env içinde TELEGRAM_TOKEN yok. @BotFather'dan aldığın token'ı ekle.")

api = f"https://api.telegram.org/bot{token}"
me = requests.get(f"{api}/getMe", timeout=10).json()
if not me.get("ok"):
    sys.exit(f"Token geçersiz: {me.get('description')}")
print(f"Bot: @{me['result']['username']}")

chat_id = os.getenv("TELEGRAM_CHAT_ID")
if not chat_id:
    updates = requests.get(f"{api}/getUpdates", timeout=10).json().get("result", [])
    chats = [u["message"]["chat"] for u in updates if "message" in u]
    if not chats:
        sys.exit(f"Mesaj bulunamadı. Telegram'da @{me['result']['username']} botuna "
                 "bir mesaj at ve bu scripti tekrar çalıştır.")
    chat = chats[-1]
    chat_id = str(chat["id"])
    print(f"Chat id bulundu: {chat_id} ({chat.get('first_name') or chat.get('title')})")
    with open(ENV_FILE, "a", encoding="utf-8") as f:
        f.write(f"\nTELEGRAM_CHAT_ID={chat_id}\n")
    print(".env dosyasına TELEGRAM_CHAT_ID eklendi.")

r = requests.post(f"{api}/sendMessage",
                  data={"chat_id": chat_id, "text": "✅ Telegram bağlantısı çalışıyor. Al-sat bildirimleri buraya gelecek."},
                  timeout=10).json()
print("Test mesajı gönderildi." if r.get("ok") else f"Gönderilemedi: {r.get('description')}")
