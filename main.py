import os
import time
import html
import requests
import xml.etree.ElementTree as ET
from threading import Thread
from flask import Flask
from datetime import datetime

RSS_URL = "https://www.mofa.go.kr/www/brd/rss.do?brdId=235"
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

latest_guid = None
last_run_hour = None  # 마지막으로 실행된 시각(시간 단위)

def send_telegram(text: str):
    if not (BOT_TOKEN and CHAT_ID):
        print("⚠️ BOT_TOKEN 또는 CHAT_ID 비어 있음")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print("⚠️ 텔레그램 에러:", e)

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

def watcher_loop():
    global latest_guid, last_run_hour
    print("🚀 MOFA RSS 감시 시작 (정시 자동 감시 + 슬립 복원 대응)")

    while True:
        now = datetime.now()
        current_hour = now.hour

        # 현재 시각이 새로운 정시라면 실행
        if last_run_hour != current_hour and now.minute == 0:
            last_run_hour = current_hour
            print(f"⏰ {current_hour}시 정시 실행")

            item = get_latest_rss()
            if not item:
                send_telegram("⚠️ 외교부 RSS를 불러오지 못했습니다.")
                time.sleep(60)
                continue

            if latest_guid is None:
                latest_guid = item["guid"]
                print(f"✅ 초기화 완료: {item['title']}")
            elif item["guid"] != latest_guid:
                latest_guid = item["guid"]
                msg = f"📢 새 외교부 보도자료!\n\n📰 {html.escape(item['title'])}\n🔗 {item['link']}"
                send_telegram(msg)
                print(f"🔔 새 글 알림: {item['title']}")
            else:
                send_telegram("ℹ️ 새 외교부 보도자료가 없습니다. (이번 정시 업데이트 없음)")
                print("변동 없음 (정시 알림 전송)")

        # 1분마다 현재 시간 확인 (슬립 복원 대응)
        time.sleep(60)

app = Flask(__name__)

@app.get("/")
def home():
    return "MOFA alert (정시 모드, 슬립 복원 대응) ✅"

if __name__ == "__main__":
    Thread(target=watcher_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
