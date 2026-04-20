import os
import requests
import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta

def send_tg(msg):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg}
    requests.post(url, data=payload)

def calculate_ema(df, period):
    if len(df) < period: return pd.Series([None] * len(df))
    # 使用 NumPy 加速 EMA 計算， com=(N-1)/2, N=N => com=(N-1)/2
    return df['close'].ewm(span=period, adjust=False).mean()

def calculate_kd(df):
    try:
        low_list = df['low'].rolling(9).min()
        high_list = df['high'].rolling(9).max()
        rsv = (df['close'] - low_list) / (high_list - low_list) * 100
        # pandas data with nan will cause ewm calculation issue, so backfill
        rsv = rsv.fillna(50)
        df['K'] = rsv.ewm(com=2, adjust=False).mean()
        df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    except:
        pass

def get_stock_score_tangle(stock_id, dl):
    try:
        sid = str(stock_id).split()[0].strip()
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
        data = dl.taiwan_stock_daily(stock_id=sid, start_date=start_date, end_date=end_date)
        if len(data) < 30: return None
        
        # 1. 計算 EMA
        ema5 = calculate_ema(data, 5)
        ema10 = calculate_ema(data, 10)
        ema20 = calculate_ema(data, 20)
        ema60 = calculate_ema(data, 60)
        ema120 = calculate_ema(data, 120)
        
        # 2. 計算 KD
        calculate_kd(data)
        
        # 3. 糾結度計算 (前 5 天均線差距百分比)
        # 取前 5 天(不含突破當天)
        past_data_idx = -6 # 當天是-1，前1天-2...
        tangle_ma = pd.concat([ema5.iloc[past_data_idx:-1], ema10.iloc[past_data_idx:-1], ema20.iloc[past_data_idx:-1], ema60.iloc[past_data_idx:-1]], axis=1)
        tangle_min = tangle_ma.min(axis=1).min()
        tangle_max = tangle_ma.max(axis=1).max()
        tangle_pct = (tangle_max - tangle_min) / tangle_min * 100
        
        # 4. 條件篩選 (關鍵部分！)
        change_pct = (data['close'].iloc[-1] - data['close'].iloc[-2]) / data['close'].iloc[-2] * 100
        
        # 當天量能因子 (今日量 / 前 10 天均量)
        avg_vol = data['Trading_Volume'].iloc[-11:-1].mean()
        last_vol = data['Trading_Volume'].iloc[-1]
        vol_ratio = last_vol / avg_vol if avg_vol > 0 else 1
        
        # --- 核心突破條件：均線糾結 < 5% && 帶量大於 2.5倍 && 漲幅 > 5% ---
        is_tangle_breakout = (
            tangle_pct < 5 and  # 均線糾結條件
            last_vol > avg_vol * 2.5 and # 帶量突破
            change_pct > 5 and # 漲幅 > 5%
            data['close'].iloc[-1] > data['open'].iloc[-1] and # 陽線
            data['close'].iloc[-1] > max(ema5.iloc[-1], ema10.iloc[-1], ema20.iloc[-1], ema60.iloc[-1]) # 突破 all MA
        )
        
        if not is_tangle_breakout: return None
        
        # 5. 簡易 AI 綜合評分
        score = 100 # 基礎分
        
        # 漲幅加分
        score += min(change_pct, 10) * 15
        
        # 量能加分
        score += min(vol_ratio, 10) * 25
        
        # 糾結度加分
        score += max(100 - tangle_pct * 12, 0)
        
        # 均線排列加分 (EMA5>10>20>60)
        is_bullish = ema5.iloc[-1] > ema10.iloc[-1] > ema20.iloc[-1] > ema60.iloc[-1]
        if is_bullish: score += 50
        
        # 長期趨勢加分 (EMA60>EMA120)
        if ema60.iloc[-1] > ema120.iloc[-1]: score += 30
        
        # KD金叉加分 (K>D, 前1天K<D)
        if data['K'].iloc[-1] > data['D'].iloc[-1] and data['K'].iloc[-2] < data['D'].iloc[-2]: score += 20
        
        return {
            "name": stock_id, 
            "price": data['close'].iloc[-1], 
            "change": round(change_pct, 1),
            "vol_ratio": round(vol_ratio, 1),
            "tangle": round(tangle_pct, 1),
            "bullish": is_bullish,
            "kd_gold": data['K'].iloc[-1] > data['D'].iloc[-1] and data['K'].iloc[-2] < data['D'].iloc[-2],
            "ma60_120": ema60.iloc[-1] > ema120.iloc[-1],
            "score": score
        }
    except:
        return None

def main():
    print(" 啟動多因子 AI 均線突破選股系統...")
    df = pd.read_excel("stocks.xlsx")
    monitor_list = df['stock_id'].astype(str).tolist()
    
    dl = DataLoader()
    fm_token = os.getenv('FINMIND_TOKEN')
    if fm_token: dl.login_by_token(fm_token)
    
    results = []
    print(f"開始篩選 {len(monitor_list)} 檔股票...")
    for s in monitor_list:
        res = get_stock_score_tangle(s, dl)
        if res: results.append(res)
    
    # 選出綜合評分最強的前 5 檔
    top_5 = sorted(results, key=lambda x: x['score'], reverse=True)[:5]
    
    if top_5:
        msg = " **AI 多因子均線突破 Top 5**\n\n"
        for i, item in enumerate(top_5, 1):
            msg += f"{i}. `{item['name']}` (價: {item['price']}, 漲: {item['change']}%)\n   🚀 **量增: {item['vol_ratio']}倍** | 💯 **AI評分: {item['score']}分**\n   (糾結度: {item['tangle']}% | 均線多頭:{item['bullish']} | KD金叉:{item['kd_gold']})\n\n"
    else:
        msg = " 今日市場趨勢較弱，監控名單中暫無強勢突破標的。"
    
    send_tg(msg)
    print(" 多因子篩選報告已傳送到 Telegram")

if __name__ == "__main__":
    main()
