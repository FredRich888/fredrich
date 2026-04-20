import os
import requests
import pandas as pd

def send_tg(msg):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("❌ 錯誤：找不到環境變數")
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
        print(f"⚠️ 發生例外: {e}")

def stock_screener():
    """
    從 stocks.xlsx 批次讀取股票並產出報表
    """
    try:
        # 讀取與程式碼同目錄下的 Excel
        df = pd.read_excel("stocks.xlsx")
        
        # 將 stock_id 這一欄轉成清單
        selected_stocks = df['stock_id'].astype(str).tolist()
        
        if selected_stocks:
            result_msg = "🎯 **Excel 批次匯入監控名單：**\n\n" + "\n".join(selected_stocks)
        else:
            result_msg = "⚠️ Excel 檔案內沒有發現股票資料！"
            
    except Exception as e:
        result_msg = f"❌ 讀取 Excel 失敗，請確認檔名是否為 stocks.xlsx\n錯誤訊息: {e}"
        
    return result_msg

if __name__ == "__main__":
    print("🚀 啟動 Excel 批次讀取系統...")
    final_report = stock_screener()
    send_tg(final_report)
    print("✨ 任務完成！")
