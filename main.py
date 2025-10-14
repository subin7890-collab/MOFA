import os
import time
import html
import requests
import xml.etree.ElementTree as ET
from threading import Thread
from flask import Flask

# ===== 설정 =====
RSS_URL = "https://www.mofa.go.kr/www/brd/rss.do?brdId=235"  # 외교부 보도자료 RSS
CHECK_INTERVAL_SEC = 3600  # 1시간마다 확인 (원하면 600=10분 등으로 변경)

# Railway 환경변수에서 읽음 (Dashboard > Variables)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

latest_guid = None  # 최근 본 글의 GUID (프로세스가 재시작되면 초기화됨)

# ===== 텔레그램 전송 =====
def send_telegram(title: str, link: str, pub: str = ""):
    if not (BOT_TOKEN and CHAT_ID):
        print("⚠️ BOT_TOKEN/CHAT_ID가 환경변수에 설정되지 않음")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    msg = f"📰 <b>{html.escape(title)}</b>\n{html.escape(pub)}\n{link}"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": False}
    try:
        r = requests.post(url, data=payload, timeout=10)
        ok = r.status_code == 200 and r.json().get("ok", False)
        if not ok:
            print("⚠️ 텔레그램 전송 실패:", r.status_code, r.text[:500])
    except Exception as e:
        print("⚠️ 텔레그램 에러:", e)

# ===== RSS 파싱 =====
def fetch_latest_item():
    """
    RSS에서 최신 item 1개를 (title, link, guid, pubDate)로 반환
    """
    try:
        r = requests.get(RSS_URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.text)
        item = root.find("./channel/item")
        if item is None:
            return None
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or link).strip()
        pub = (item.findtext("pubDate") or "").strip()
        return {"title": title, "link": link, "guid": guid, "pubDate": pub}
    except Exception as e:
        print("⚠️ RSS 에러:", e)
        return None

# ===== 감시 루프(백그라운드) =====
def watcher_loop():
    global latest_guid
    print(f"🚀 MOFA RSS 감시 시작! 주기: {CHECK_INTERVAL_SEC}초")
    while True:
        item = fetch_latest_item()
        if item:
            if latest_guid is None:
                # 첫 실행은 초기화만 (중복 폭탄 방지)
                latest_guid = item["guid"]
                print(f"✅ 초기화: {item['title']}")
            elif item["guid"] != latest_guid:
                latest_guid = item["guid"]
                print(f"🔔 새 글 발견: {item['title']}")
                send_telegram(item["title"], item["link"], item.get("pubDate",""))
            else:
                print("… 변동 없음")
        else:
            print("⚠️ 최신 항목을 가져오지 못함")
        time.sleep(CHECK_INTERVAL_SEC)

# ===== Flask (헬스체크용, Railway가 포트 바인드 필요) =====
app = Flask(__name__)

@app.get("/")
def home():
    return "MOFA alert is running ✅"

def start_flask():
    port = int(os.environ.get("PORT", 8080))  # Railway가 PORT 제공
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # 감시 스레드 시작
    Thread(target=watcher_loop, daemon=True).start()
    # 웹서버 시작 (프로세스가 살아있도록)
    start_flask()
