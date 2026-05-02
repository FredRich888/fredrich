import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import time

# --- 核心參數調整 ---
MIN_PRICE = 12
MAX_PRICE = 92
MACD_PARAMS = (6, 12, 2)
VOL_FILTER = 1.0        # 降至 1.0，避免在節前量縮時篩不到股
MIN_SHEETS = 500        # 成交量張數門檻

def calculate_indicators(df):
    df.columns = [str(c).lower() for c in df.columns]
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    df['vol_ma5'] = df['trading_volume'].rolling(5).mean()
    
    ema_f = df['close'].ewm(span=MACD_PARAMS[0], adjust=False).mean()
    ema_s = df['close'].ewm(span=MACD_PARAMS[1], adjust=False).mean()
    df['dif'] = ema_f - ema_s
    df['macd_dea'] = df['dif'].ewm(span=MACD_PARAMS[2], adjust=False).mean()
    df['hist'] = df['dif'] - df['macd_dea']
    
    # K棒實體計算：處理最高等於最低的狀況 (如漲停)
    df['range'] = df['high'] - df['low']
    df['body'] = (df['close'] - df['open']).abs()
    df['k_body'] = np.where(df['range'] > 0, df['body'] / df['range'], 1.0)
    return df

def run_pro_screener_v2():
    api = DataLoader()
    print(f"【啟動】分析區間：{MIN_PRICE} - {MAX_PRICE} 元 | 爆量門檻：{VOL_FILTER}x")
    
    stock_info = api.taiwan_stock_info()
    all_stocks = stock_info[stock_info['stock_id'].str.len() == 4]['stock_id'].tolist()
    start_dt = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d')
    results = []

    # 基準日檢測
    sample = api.taiwan_stock_daily(stock_id="2330", start_date=(datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'))
    if sample.empty: return
    latest_trade_date = sample.iloc[-1]['date']
    print(f"【檢測】分析基準日: {latest_trade_date}")

    for i, stock_id in enumerate(all_stocks):
        try:
            df = api.taiwan_stock_daily(stock_id=stock_id, start_date=start_dt)
            if len(df) < 60: continue
            
            # 價格先行過濾
            curr_price = df.iloc[-1]['close']
            if not (MIN_PRICE <= curr_price <= MAX_PRICE): continue

            df = calculate_indicators(df)
            t = df.iloc[-1]
            t_1 = df.iloc[-2]

            if t['date'] != latest_trade_date: continue

            # --- 邏輯篩選 (保持高勝率核心) ---
            # 1. 趨勢與動能 (核心不能放寬)
            cond_macd = (t['dif'] > 0) and (t['hist'] > t_1['hist'])
            cond_ma = (t['ma5'] > t['ma20']) and (t['ma20'] > t['ma60'])
            
            # 2. 實體強度 (放寬一字線漲停)
            is_limit_up = (t['close'] >= t_1['close'] * 1.095) and (t['close'] == t['high'])
            cond_k = (t['k_body'] > 0.5) or is_limit_up
            
            # 3. 量能過濾
            vol_sheets = t['trading_volume'] / 1000
            cond_vol = (vol_sheets > MIN_SHEETS) and (t['trading_volume'] >= t['vol_ma5'] * VOL_FILTER)

            if cond_macd and cond_ma and cond_k and cond_vol:
                results.append({
                    "代碼": stock_id,
                    "名稱": stock_info[stock_info['stock_id']==stock_id]['stock_name'].values[0],
                    "收盤": t['close'],
                    "漲幅%": round(((t['close']/t_1['close'])-1)*100, 2),
                    "成交量": int(vol_sheets),
                    "實體%": round(t['k_body']*100, 1)
                })
            
            if (i+1) % 500 == 0: print(f"掃描進度: {i+1}/{len(all_stocks)}")
            time.sleep(0.01)
        except: continue

    print("\n" + "🏁"*15 + " 篩選結果 " + "🏁"*15)
    if results:
        res_df = pd.DataFrame(results).sort_values(by="漲幅%", ascending=False)
        print(res_df.to_string(index=False))
    else:
        print(f"今日 ({latest_trade_date}) 市場結構偏弱，無標的同時符合 [均線多排+MACD轉強+實體紅K]。")
    print("🏁"*40 + "\n")

if __name__ == "__main__":
    run_pro_screener_v2()
