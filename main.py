import os
import requests

def send_tg(msg):
    token = os.getenv('TG_TOKEN')
    chat_id = os.getenv('TG_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": msg, 
        "parse_mode": "Markdown"
    }
    r = requests.post(url, data=payload)
    print(f"發送狀態: {r.status_code}, 回傳內容: {r.text}")

if __name__ == "__main__":
    # 這行前面必須有 4 個空格
    send_tg("🚀 恭喜！縮排問題已修復，雲端連線測試中！")
