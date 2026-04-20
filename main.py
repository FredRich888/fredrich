import os
import requests
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta

def send_tg(msg):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        print("❌ 錯誤：找不到環境變數")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # 關鍵修正：拿掉 Markdown 模式，改用純文本發送，確保 100% 成功
    payload = {"chat_id": chat_id, "text": msg}
    
    r = requests.post(url, data=payload)
    print(f"發送狀態: {r.status_code}, 回傳內容: {r.text}")

def get_stock_score(stock_id, dl):
    try:
        sid = str(stock_id).split()[0].strip()
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d')
        
        data = dl.taiwan_stock_daily(stock_id=sid, start_date=start_date, end_date=end_date)
        if len(data) < 5: return None
        
        # 簡易 AI 篩選模型
        price_change = (data['close'].iloc[-1] - data['close'].iloc[-5]) / data['close'].iloc[-5]
        vol_ratio = data['Trading_Volume'].iloc[-1] / data['Trading_Volume'].mean()
        score = (price_change * 100 * 0.7) + (vol_ratio * 0.3)
        
        return {"name": stock_id, "price": data['close'].iloc[-1], "change": round(price_change*100, 2), "score": score}
    except:
        return None

def main():
    print("🚀 啟動 AI 雲端篩選系統...")
    try:
        df = pd.read_excel("stocks.xlsx")
        monitor_list = df['stock_id'].astype(str).tolist()
    except Exception as e:
        send_tg(f"❌ 讀取 Excel 失敗: {e}")
        return

    dl = DataLoader()
    fm_token = os.getenv('FINMIND_TOKEN')
    if fm_token: dl.login_by_token(fm_token)
    
    results = []
    for s in monitor_list:
        res = get_stock_score(s, dl)
        if res: results.append(res)
    
    # AI 排序選出最強 5 檔
    top_5 = sorted(results, key=lambda x: x['score'], reverse=True)[:5]
    
    if top_5:
        msg = "🤖 AI 雲端強勢股篩選 Top 5\n\n"
        for i, item in enumerate(top_5, 1):
            msg += f"{i}. {item['name']}\n   價格: {item['price']} | 5日漲幅: {item['change']}%\n"
    else:
        msg = "⚠️ 篩選完成，今日無符合條件之強勢股。"
    
    send_tg(msg)

if __name__ == "__main__":
    main()
