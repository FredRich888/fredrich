import os
import requests
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta

def send_tg(msg):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # 這裡暫時拿掉 Markdown，避免特殊字元造成 400 錯誤
    payload = {"chat_id": chat_id, "text": msg}
    r = requests.post(url, data=payload)
    print(f"發送狀態: {r.status_code}, 回傳內容: {r.text}")

def get_stock_score(stock_id, dl):
    try:
        # 抓取近 15 天數據進行雲端篩選
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d')
        
        sid = str(stock_id).split()[0].strip() # 確保只拿數字部分
        data = dl.taiwan_stock_daily(stock_id=sid, start_date=start_date, end_date=end_date)
        
        if len(data) < 5: return None
        
        # 簡易 AI 評分模型：結合漲幅 (70%) 與 量能變化 (30%)
        price_change = (data['close'].iloc[-1] - data['close'].iloc[-5]) / data['close'].iloc[-5]
        vol_ratio = data['Trading_Volume'].iloc[-1] / data['Trading_Volume'].mean()
        
        score = (price_change * 100 * 0.7) + (vol_ratio * 0.3)
        return {
            "name": stock_id, 
            "price": data['close'].iloc[-1], 
            "change": round(price_change * 100, 2), 
            "score": score
        }
    except:
        return None

def main():
    print(" 啟動 AI 雲端篩選系統...")
    try:
        df = pd.read_excel("stocks.xlsx")
        monitor_list = df['stock_id'].astype(str).tolist()
    except Exception as e:
        send_tg(f"❌ 讀取 stocks.xlsx 失敗: {e}")
        return

    dl = DataLoader()
    fm_token = os.getenv('FINMIND_TOKEN')
    if fm_token: dl.login_by_token(fm_token)
    
    results = []
    for s in monitor_list:
        res = get_stock_score(s, dl)
        if res: results.append(res)
    
    # --- AI 強勢度排序，選出前 5 檔 ---
    top_5 = sorted(results, key=lambda x: x['score'], reverse=True)[:5]
    
    if top_5:
        msg = " AI 雲端強勢股篩選 Top 5\n\n"
        for i, item in enumerate(top_5, 1):
            msg += f"{i}. {item['name']}\n   💰 價格: {item['price']} | 📈 5日漲幅: {item['change']}%\n"
    else:
        msg = " 篩選完成，但目前名單中無符合強勢條件的股票。"
    
    send_tg(msg)

if __name__ == "__main__":
    main()
