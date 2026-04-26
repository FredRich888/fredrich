import os  # 系統環境變數
import requests  # 發送 Telegram
import pandas as pd  # 資料處理
import numpy as np  # 數學運算
from FinMind.data import DataLoader  # 抓取台股資料
from datetime import datetime, timedelta  # 時間處理

def send_tg(msg):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg}
    requests.post(url, data=payload)

def calculate_ema(df, period):
    return df['close'].ewm(span=period, adjust=False).mean()

def get_stock_analysis(stock_id, dl):
    try:
        # --- 格式修正：確保代號正確 ---
        sid = str(stock_id).split('.')[0].strip() # 處理如 4755.TW 或 4755
        
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        data = dl.taiwan_stock_daily(stock_id=sid, start_date=start_date, end_date=end_date)
        
        if len(data) < 30: return None
        
        # --- 技術指標：EMA 均線 ---
        data['ema5'] = calculate_ema(data, 5)
        data['ema10'] = calculate_ema(data, 10)
        data['ema20'] = calculate_ema(data, 20)
        
        # --- 因子 1：均線糾結度 (昨日狀態) ---
        ma_list = [data['ema5'].iloc[-2], data['ema10'].iloc[-2], data['ema20'].iloc[-2]]
        tangle_pct = (max(ma_list) - min(ma_list)) / min(ma_list) * 100
        
        # --- 因子 2：量能噴發 (今日量 vs 10日均量) ---
        avg_vol = data['Trading_Volume'].iloc[-11:-1].mean()
        last_vol = data['Trading_Volume'].iloc[-1]
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1
        
        # --- 因子 3：價格強度 (今日漲幅) ---
        change_pct = (data['close'].iloc[-1] - data['close'].iloc[-2]) / data['close'].iloc[-2] * 100
        
        # --- 🛡️ 修正後的 AI 評分邏輯 (不再採用「一刀切」，改用累積分數) ---
        score = 0
        
        # A. 糾結加分：越糾結分越高 (最高 200分)
        score += max(0, (6 - tangle_pct) * 33) 
        
        # B. 量能加分：量增倍數越多分越高 (最高 300分)
        score += min(vol_ratio * 50, 300) 
        
        # C. 漲幅加分：漲越多分越高 (最高 300分)
        score += min(change_pct * 30, 300)
        
        # D. 站上均線加倍 (核心條件加乘)
        if data['close'].iloc[-1] > max(ma_list):
            score *= 1.5 # 只要站上所有糾結線，總分直接放大 1.5 倍
            
        # E. 趨勢紅K加分
        if data['close'].iloc[-1] > data['open'].iloc[-1]: score += 50

        # 設定一個基本的「進榜門檻」，避免把跌的股票也選進來
        if change_pct < 1.0 or score < 200: return None 

        return {
            "name": f"{sid}", 
            "price": data['close'].iloc[-1], 
            "score": int(score),
            "change": round(change_pct, 1), 
            "vol_ratio": round(vol_ratio, 1), 
            "tangle": round(tangle_pct, 1)
        }
    except: return None

def main():
    print("🚀 啟動修正版 AI 動能選股系統...")
    df = pd.read_excel("stocks.xlsx")
    monitor_list = df['stock_id'].astype(str).tolist()
    
    dl = DataLoader()
    fm_token = os.getenv('FINMIND_TOKEN')
    if fm_token: dl.login_by_token(fm_token)
    
    all_candidates = []
    for s in monitor_list:
        res = get_stock_analysis(s, dl)
        if res: all_candidates.append(res)
    
    # --- 取前 5 強，即便市場普普通通也會選出相對強勢的 ---
    top_5 = sorted(all_candidates, key=lambda x: x['score'], reverse=True)[:5]
    
    if top_5:
        msg = "🤖 AI 多因子強勢股篩選報告\n\n"
        for i, item in enumerate(top_5, 1):
            msg += f"{i}. {item['name']} | 價: {item['price']} | 漲: {item['change']}%\n"
            msg += f"   📊 量比: {item['vol_ratio']}倍 | 🎯 AI分: {item['score']}\n"
            msg += f"   (糾結度: {item['tangle']}%)\n\n"
    else:
        msg = "⚠️ 今日市場極度低迷，監控名單中無符合基本動能之股票。"
    
    send_tg(msg)
    print("✅ 報告已送出")

if __name__ == "__main__":
    main()
