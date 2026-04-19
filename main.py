import os
import requests
import pandas as pd
from FinMind.data import DataLoader

# 設定參數
FINMIND_TOKEN = os.getenv('FINMIND_TOKEN')
TG_TOKEN = os.getenv('TG_TOKEN')
TG_CHAT_ID = os.getenv('TG_CHAT_ID')

def get_data(sid):
    dl = DataLoader()
    dl.login_token(token=FINMIND_TOKEN)
    # 抓取近 100 天數據
    df = dl.taiwan_stock_daily(stock_id=sid, start_date='2025-12-01')
    return df

def resonance_score(df):
    if len(df) < 60: return 0
    score = 0
    close = df['close']
    
    # 1. 趨勢：MA5 > MA20 > MA60
    ma5 = close.rolling(5).mean().iloc[-1]
    ma20 = close.rolling(20).mean().iloc[-1]
    ma60 = close.rolling(60).mean().iloc[-1]
    if ma5 > ma20 > ma60: score += 4
    
    # 2. VCP 波動收縮：近 5 日振幅 < 5%
    high_5 = df['high'].tail(5).max()
    low_5 = df['low'].tail(5).min()
    price_range = (high_5 - low_5) / close.iloc[-2]
    if price_range < 0.05: score += 4
    
    # 3. 量能確認
    vol_ma20 = df['volume'].rolling(20).mean().iloc[-1]
    if df['volume'].iloc[-1] > vol_ma20 * 1.2: score += 2
    
    return score

def send_tg(msg):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    # 這裡可以修改成你想追蹤的族群，或全市場掃描
    test_list = ['2330', '3230', '3615', '2338', '4416', '3628', '3317', '6465', '1721'] 
    hits = []
    for sid in test_list:
        try:
            data = get_data(sid)
            s = resonance_score(data)
            if s >= 8: hits.append(f"{sid} (得分:{s})")
        except: continue
    
    if hits:
        send_tg(f"🎯 **波段精選名單**:\n" + "\n".join(hits))
    else:
        send_tg("今日無符合共振標的，繼續耐心等待。")
if __name__ == "__main__":
    send_tg("測試訊息：哈囉！雲端系統已連線！")
