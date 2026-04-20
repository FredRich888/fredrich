import os
import requests

# 這裡必須保留定義，程式才認識 send_tg
def send_tg(msg):
    token = os.getenv('TG_TOKEN')
    chat_id = os.getenv('TG_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    r = requests.post(url, data=payload)
    print(f"發送狀態: {r.status_code}, 回傳內容: {r.text}")

if __name__ == "__main__":
    # 執行測試
    send_tg("🚀 恭喜！你的雲端篩選系統測試成功！這條訊息代表連線完全正常。")
