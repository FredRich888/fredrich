import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import time

# --- 核心參數設定 ---
MIN_PRICE = 12           # 價格下限
MAX_PRICE = 92           # 價格上限
MACD_PARAMS = (6, 12, 2)
VOL_FILTER = 1.2
MIN_SHEETS = 500         # 基本量能門檻

def calculate_indicators(df):
    """計算所有核心指標：MA, MACD, K-Body"""
    df.columns = [str(c).lower() for c in df.columns]
    # 均線系統
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    df['vol_ma5'] = df['trading_volume'].rolling(5).mean()
    
    # 極速 MACD (6, 12, 2)
    ema_f = df['close'].ewm(span=6, adjust=False).mean()
    ema_s = df['close'].ewm(span=12, adjust=False).mean()
    df['dif'] = ema_f - ema_s
    df['macd_dea'] = df['dif'].ewm(span=2, adjust=False).mean()
    df['hist'] = df['dif'] - df['macd_dea']
    
    # K-Body Ratio (實體紅棒佔比，過濾長上影線)
    df['k_body'] = (df['close'] - df['open']) / (df['high'] - df['low'] + 0.00001)
    return df

def run_targeted_price_screener():
    api = DataLoader()
    # 如有 Token 建議在此登入: api.login_by_token(token='...')
    
    print(f"【啟動】目標區間：{MIN_PRICE} - {MAX_PRICE} 元，正在掃描最新交易日數據...")
    stock_info = api.taiwan_stock_info()
    all_stocks = stock_info[stock_info['stock_id'].str.len() == 4]['stock_id'].tolist()
    
    # 抓取 100 天資料確保指標精準度
    start_dt = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d')
    results = []

    # 確定最新交易日
    sample = api.taiwan_stock_daily(stock_id="2330", start_date=(datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'))
    if sample.empty:
        print("❌ 無法取得市場數據，請檢查 FinMind API 連線。")
        return
    latest_trade_date = sample.iloc[-1]['date']
    print(f"【檢測】當前分析基準日: {latest_trade_date}")

    for i, stock_id in enumerate(all_stocks):
        try:
            df = api.taiwan_stock_daily(stock_id=stock_id, start_date=start_dt)
            if df.empty or len(df) < 60: continue
            
            # 1. 價格條件先行過濾
            curr_price = df.iloc[-1]['close']
            if not (MIN_PRICE <= curr_price <= MAX_PRICE): continue

            df = calculate_indicators(df)
            t = df.iloc[-1]
            t_1 = df.iloc[-2]
            
            # 確保資料是最新日期的
            if t['date'] != latest_trade_date: continue

            # --- 勝率 > 65% 之篩選邏輯 ---
            # A. MACD 動能：DIF 在零軸之上且柱狀體轉強
            cond_macd = (t['dif'] > 0) and (t['hist'] > t_1['hist'])
            
            # B. 結構強度：5MA > 20MA > 60MA (主升段排列)
            cond_ma = (t['ma5'] > t['ma20']) and (t['ma20'] > t['ma60'])
            
            # C. K線品質：實體紅棒 > 50% (拒絕長上影線誘多)
            cond_k = t['k_body'] > 0.5
            
            # D. 量能爆發
            vol_sheets = t['trading_volume'] / 1000
            cond_vol = (vol_sheets > MIN_SHEETS) and (t['trading_volume'] > t['vol_ma5'] * VOL_FILTER)

            if cond_macd and cond_ma and cond_k and cond_vol:
                results.append({
                    "代碼": stock_id,
                    "收盤": t['close'],
                    "漲幅%": round(((t['close']/t_1['close'])-1)*100, 2),
                    "張數": int(vol_sheets),
                    "DIF": round(t['dif'], 2),
                    "K棒實體%": round(t['k_body']*100, 1)
                })
            
            if (i+1) % 200 == 0: print(f"進度: {i+1}/{len(all_stocks)}")
            time.sleep(0.01)

        except Exception:
            continue

    # --- 輸出結果 ---
    print("\n" + "🚀"*15 + f" {MIN_PRICE}-{MAX_PRICE} 元 強勢股清單 " + "🚀"*15)
    if results:
        res_df = pd.DataFrame(results).sort_values(by="漲幅%", ascending=False)
        print(res_df.to_string(index=False))
        print(f"\n符合所有共振條件標的共：{len(results)} 檔。")
    else:
        print(f"今日在 {MIN_PRICE}-{MAX_PRICE} 元區間內無符合條件之標的。")
    print("🚀"*50 + "\n")

if __name__ == "__main__":
    run_targeted_price_screener()
