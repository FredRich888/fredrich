import os
import requests

def send_tg(msg):
    # 從 GitHub Secrets 獲取變數
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    # 檢查變數是否為空
    if not token or not chat_id:
        print("❌ 錯誤：找不到環境變數！請檢查 GitHub Secrets 是否有設定 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID")
        return

    # 正確的 Telegram API 網址構造
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "Markdown"
    }
    
    try:
        r = requests.post(url, data=payload)
        if r.status_code == 200:
            print(f"✅ 發送成功！回應內容: {r.text}")
        else:
            print(f"❌ 發送失敗！狀態碼: {r.status_code}, 內容: {r.text}")
    except Exception as e:
        print(f"⚠️ 發生例外狀況: {e}")

if __name__ == "__main__":
    # 這是最後測試，如果這封有收到，代表你的篩選器代碼也能發送了
    send_tg("🚀 **終極測試成功！**\n\n這條訊息證明你的 GitHub Actions、Secrets 與 Telegram 機器人已經完全打通了！")
