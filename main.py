import os
import requests
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta

def send_tg(msg):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg}
    requests.post(url, data=payload)

def get_stock_score(stock_id, dl):
    try:
        sid = str(stock_id).split()[0].strip()
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        data = dl.taiwan_stock_daily(stock_id=sid, start_date=start_date, end_date=end_date)
        if len(data) < 20: return None # 確保有足夠資料計算月線
        
        # 1. 漲幅因子 (近5日)
        change_5d = (data['close'].iloc[-1] - data['close'].iloc[-5]) / data['close'].iloc[-5]
        
        # 2. 量能因子 (今日成交量 / 5日平均成交量)
        avg_vol = data['Trading_Volume'].iloc[-5:].mean()
        last_vol = data['Trading_Volume'].iloc[-1]
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1
        
        # 3. 趨勢因子 (價格是否在月線 20MA 之上)
        ma20 = data['close'].rolling(20).mean().iloc[-1]
        on_ma20 = 1.2 if data['close'].iloc[-1] > ma20 else 0.8
        
        # 綜合 AI 評分：(漲幅*70 + 量能*30) * 趨勢加權
        score = (change_5d * 100 * 70 + vol_ratio * 30) * on_ma20
        
        return {
            "name": stock_id, 
            "price": data['close'].iloc[-1], 
            "change": round(change_5d * 100, 2),
            "vol_ratio": round(vol_ratio, 2),
            "score": score
        }
    except:
        return None

def main():
    print("🚀 啟動多因子 AI 選股系統...")
    df = pd.read_excel("stocks.xlsx")
    monitor_list = df['stock_id'].astype(str).tolist()
    
    dl = DataLoader()
    fm_token = os.getenv('FINMIND_TOKEN')
    if fm_token: dl.login_by_token(fm_token)
    
    results = []
    for s in monitor_list:
        res = get_stock_score(s, dl)
        if res: results.append(res)
    
    # 只要分數大於 0 就列入考慮，並選出最強前 5 檔
    qualified = [r for r in results if r['score'] > 0]
    top_5 = sorted(qualified, key=lambda x: x['score'], reverse=True)[:5]
    
    if top_5:
        msg = "🤖 AI 多因子強勢股 Top 5\n\n"
        for i, item in enumerate(top_5, 1):
            msg += f"{i}. {item['name']}\n   價: {item['price']} | 5日漲: {item['change']}% | 量增: {item['vol_ratio']}倍\n"
    else:
        msg = "⚠️ 市場趨勢較弱，監控名單中暫無強勢標的。"
    
    send_tg(msg)

if __name__ == "__main__":
    main()
