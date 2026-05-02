import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import time
import os
import requests

# --- 核心參數 ---
MIN_PRICE = 12
MAX_PRICE = 250
VOL_FILTER = 1.2
MIN_SHEETS = 500

def send_telegram_msg(message):
    """發送訊息至 Telegram"""
    # 從 GitHub Secrets 讀取 Token，避免外洩
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        print("⚠️ 未設定 Telegram Token 或 Chat ID，跳過發送。")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram 發送失敗: {e}")

def calculate_indicators(df):
    df.columns = [str(c).lower() for c in df.columns]
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    df['vol_ma5'] = df['trading_volume'].rolling(5).mean()
    
    ema_f = df['close'].ewm(span=6, adjust=False).mean()
    ema_s = df['close'].ewm(span=12, adjust=False).mean()
    df['dif'] = ema_f - ema_s
    df['hist'] = df['dif'] - df['dif'].ewm(span=2, adjust=False).mean()
    
    df['range'] = df['high'] - df['low']
    df['body'] = (df['close'] - df['open']).abs()
    df['k_body'] = np.where(df['range'] > 0, df['body'] / df['range'], 1.0)
    return df

def run_final_system():
    api = DataLoader()
    token = os.getenv("FINMIND_TOKEN")
    if token: api.login_by_token(token)

    stock_info = api.taiwan_stock_info()
    all_stocks = stock_info[stock_info['stock_id'].str.len() == 4]['stock_id'].tolist()
    start_dt = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d')
    results = []

    # 獲取基準日
    sample = api.taiwan_stock_daily(stock_id="2330", start_date=(datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'))
    latest_trade_date = sample.iloc[-1]['date']

    for stock_id in all_stocks:
        try:
            df = api.taiwan_stock_daily(stock_id=stock_id, start_date=start_dt)
            if len(df) < 60: continue
            
            curr_price = df.iloc[-1]['close']
            if not (MIN_PRICE <= curr_price <= MAX_PRICE): continue

            df = calculate_indicators(df)
            t, t_1 = df.iloc[-1], df.iloc[-2]
            if t['date'] != latest_trade_date: continue

            # 篩選邏輯
            cond_macd = (t['dif'] > 0) and (t['hist'] > t_1['hist'])
            cond_ma = (t['ma5'] > t['ma20']) and (t['ma20'] > t['ma60'])
            is_limit_up = (t['close'] >= t_1['close'] * 1.095) and (t['close'] == t['high'])
            cond_k = (t['k_body'] > 0.5) or is_limit_up
            vol_sheets = t['trading_volume'] / 1000
            cond_vol = (vol_sheets > MIN_SHEETS) and (t['trading_volume'] >= t['vol_ma5'] * VOL_FILTER)

            if cond_macd and cond_ma and cond_k and cond_vol:
                name = stock_info[stock_info['stock_id']==stock_id]['stock_name'].values[0]
                results.append(f"✅ {stock_id} {name} | 價:{t['close']} | 漲:{round(((t['close']/t_1['close'])-1)*100, 2)}%")
        except: continue

    # --- 執行通知 ---
    header = f"🚀 *{latest_trade_date} 選股報表 ({MIN_PRICE}-{MAX_PRICE}元)*\n"
    if results:
        msg = header + "\n".join(results)
    else:
        msg = header + "今日無符合標的，保護本金優先。盤勢偏弱。"
    
    print(msg)
    send_telegram_msg(msg)

if __name__ == "__main__":
    run_final_system()
