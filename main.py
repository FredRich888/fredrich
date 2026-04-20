import os
import requests
import pandas as pd
from FinMind.data import DataLoader

def send_tg(msg):
    """
    負責發送 Telegram 訊息的函數
    """
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("❌ 錯誤：環境變數缺失")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": msg, 
        "parse_mode": "Markdown"
    }
    
    try:
        r = requests.post(url, data=payload)
        print(f"發送狀態: {r.status_code}")
    except Exception as e:
        print(f"發送例外: {e}")

def stock_screener():
    """
    你的選股邏輯寫在這裡
    """
    # 範例：使用 FinMind 抓取資料 (需確保 Secret 有設定 FINMIND_TOKEN)
    # api_token = os.getenv('FINMIND_TOKEN')
    # dl = DataLoader()
    # dl.login_by_token(api_token)
    
    # --- 這裡放你原本的選股策略代碼 ---
    # 假設選出了兩檔股票
    selected_stocks = ["2330 台積電", "6488 環球晶", "3234 光環", "4903 聯光通", "8048 德勝", "4960 誠美材", "3321 同泰", "6465 威潤"] 
    # -------------------------------

    if selected_stocks:
        result_msg = "🎯 **今日選股結果：**\n\n" + "\n".join(selected_stocks)
    else:
        result_msg = "今天沒有符合條件的股票 😴"
    
    return result_msg

if __name__ == "__main__":
    print("🚀 啟動選股系統...")
    
    # 1. 執行選股
    final_report = stock_screener()
    
    # 2. 發送結果回 Telegram
    send_tg(final_report)
    
    print("✨ 任務完成！")
