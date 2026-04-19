import os
import requests

def send_tg(msg):
    token = os.getenv('TG_TOKEN')
    chat_id = os.getenv('TG_CHAT_ID')
    
    # 這裡增加檢查，避免抓到空值
    if not token or not chat_id:
        print("❌ 錯誤：找不到 TG_TOKEN 或 TG_CHAT_ID，請檢查 GitHub Secrets 設定！")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": msg, 
        "parse_mode": "Markdown"
    }
    
    try:
        r = requests.post(url, data=payload)
        # 這行非常重要，它會告訴我們 Telegram 為什麼不收訊息
        print(f"📡 嘗試發送至 ID: {chat_id}")
        print(f"📬 Telegram 回傳狀態碼: {r.status_code}")
        print(f"💬 Telegram 回傳內容: {r.text}")
    except Exception as e:
        print(f"📡 連線發生異常: {e}")

if __name__ == "__main__":
    send_tg("🔔 測試連線中！如果你看到這條訊息，代表全自動系統正式通車了！")
