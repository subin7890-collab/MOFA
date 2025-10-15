import os
import time
import html
import requests
import xml.etree.ElementTree as ET
from threading import Thread
from flask import Flask
from datetime import datetime

# === 기본 설정 ===
RSS_URL = "https://www.mofa.go.kr/www/brd/rss.do?brdId=235"
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
CHECK_INTERVAL = 3600  # 1시간 (초 단위)

latest_guid = None

# === 텔레그램 전송 ===
def send_telegram(text: str):
    if not (BOT_TOKEN and CHAT_ID):
        print("⚠️ BOT_TOKEN 또는 CHAT_ID 비어 있음")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code != 200:
            print("⚠️ 텔레그램 전송 실패:", r.text[:200])
    except Exception as e:
        print("⚠️ 텔레그램 에러:", e)

# === RSS 최신 글 가져오기 ===
def get_latest_rss():
    try:
        r = requests.get(RSS_URL, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        item = root.find("./channel/item")
        if item is None:
            return None
        title = item.findtext("title") or ""
        link = (item.findtext("link") or "").replace("&", "&amp;")
        guid = item.findtext("guid") or link
        return {"title": title.strip(), "link": link.strip(), "guid": guid.strip()}
    except Exception as e:
        print("⚠️ RSS 에러:", e)
        return None

# === 1시간 주기 체크 루프 ===
def watcher_loop():
    global latest_guid
    print("🚀 MOFA RSS 감시 시작 (1시간 주기 확인)")

    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"⏰ {now} - RSS 확인 중...")

        item = get_latest_rss()
        if not item:
            send_telegram("⚠️ 외교부 RSS를 불러오지 못했습니다.")
        elif latest_guid is None:
            latest_guid = item["guid"]
            print(f"✅ 초기화 완료: {item['title']}")
        elif item["guid"] != latest_guid:
            latest_guid = item["guid"]
            msg = f"📢 새 외교부 보도자료!\n\n📰 {html.escape(item['title'])}\n🔗 {item['link']}"
            send_telegram(msg)
            print(f"🔔 새 글 알림: {item['title']}")
        else:
            send_telegram("ℹ️ 새 외교부 보도자료가 없습니다. (최근 1시간 내 업데이트 없음)")
            print("변동 없음 (1시간 주기 알림 전송)")

        time.sleep(CHECK_INTERVAL)  # 1시간 대기

# === Flask (Render용 웹서버) ===
app = Flask(__name__)

@app.get("/")
def home():
    return "MOFA alert (1시간 주기 확인 버전) ✅"

if __name__ == "__main__":
    Thread(target=watcher_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
