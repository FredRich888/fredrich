import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import time

# --- 參數設定 ---
PRICE_CEILING = 200      # 價格 200 以下
KD_PERIOD = 5            # KD 週期
RSI_S, RSI_L = 3, 6      # RSI 週期
MACD_FAST, MACD_SLOW, MACD_SIG = 6, 12, 2 # 你指定的 MACD 參數
VOL_MULTIPLIER = 1.2     # 成交量爆發倍數
MIN_VOL_SHEETS = 500     # 成交量張數門檻

def calculate_full_indicators(df):
    """計算所有核心技術指標，並處理異常值"""
    try:
        df.columns = [str(c).lower() for c in df.columns]
        if 'trading_volume' not in df.columns and 'volume' in df.columns:
            df.rename(columns={'volume': 'trading_volume'}, inplace=True)
        
        # 1. 均線
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['vol_ma5'] = df['trading_volume'].rolling(window=5).mean()

        # 2. RSI (3, 6)
        for p in [RSI_S, RSI_L]:
            delta = df['close'].diff()
            up, down = delta.clip(lower=0), -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=p-1, adjust=False).mean()
            ema_down = down.ewm(com=p-1, adjust=False).mean()
            df[f'rsi{p}'] = 100 - (100 / (1 + (ema_up / ema_down.replace(0, np.nan))))

        # 3. KD (5, 3, 3)
        low_min = df['low'].rolling(window=KD_PERIOD).min()
        high_max = df['high'].rolling(window=KD_PERIOD).max()
        rsv = (df['close'] - low_min) / (high_max - low_min).replace(0, np.nan) * 100
        df['k'] = rsv.ewm(com=2, adjust=False).mean()
        df['d'] = df['k'].ewm(com=2, adjust=False).mean()

        # 4. MACD (6, 12, 2)
        ema_fast = df['close'].ewm(span=MACD_FAST, adjust=False).mean()
        ema_slow = df['close'].ewm(span=MACD_SLOW, adjust=False).mean()
        df['dif'] = ema_fast - ema_slow
        df['macd_dea'] = df['dif'].ewm(span=MACD_SIG, adjust=False).mean()
        df['macd_hist'] = df['dif'] - df['macd_dea']

        # 5. OBV (能量潮)
        direction = np.where(df['close'] > df['close'].shift(1), 1, -1)
        direction[df['close'] == df['close'].shift(1)] = 0
        df['obv'] = (direction * df['trading_volume']).cumsum()
        df['obv_ma5'] = df['obv'].rolling(window=5).mean()

        return df
    except Exception:
        return None

def run_final_screener():
    api = DataLoader()
    
    print("【啟動】抓取全市場股票清單中...")
    stock_info = api.taiwan_stock_info()
    all_stocks = stock_info[stock_info['stock_id'].str.len() == 4]['stock_id'].tolist()
    
    # 抓取 90 天資料確保 MACD 平滑性
    start_dt = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    results = []

    print(f"【執行】開始掃描，條件：MACD(6,12,2) > 0 且 柱狀體轉強...")

    for i, stock_id in enumerate(all_stocks):
        try:
            df = api.taiwan_stock_daily(stock_id=stock_id, start_date=start_dt)
            if df.empty or len(df) < 30: continue
            
            # 價格過濾
            curr_price = df.iloc[-1]['close']
            if curr_price >= PRICE_CEILING or curr_price < 10: continue

            df = calculate_full_indicators(df)
            if df is None: continue
            
            t = df.iloc[-1]   # 今日
            t_1 = df.iloc[-2] # 昨日

            # --- 邏輯判斷區 ---
            # 1. MACD 核心條件
            # DIF > 0 且 柱狀體連續增加 (紅柱增長或綠柱縮短，即今日 Hist > 昨日 Hist)
            cond_macd_zero = t['dif'] > 0
            cond_macd_hist = t['macd_hist'] > t_1['macd_hist']
            
            # 2. 短線動能 (KD & RSI)
            cond_momentum = (t['k'] > t['d']) and (t[f'rsi{RSI_S}'] > t[f'rsi{RSI_L}'])
            
            # 3. OBV 資金流
            cond_obv = t['obv'] > t['obv_ma5']
            
            # 4. 量價基礎 (爆量紅 K 且站上 MA5)
            vol_sheets = t['trading_volume'] / 1000
            cond_vol = (t['trading_volume'] > t['vol_ma5'] * VOL_MULTIPLIER) and (vol_sheets > MIN_VOL_SHEETS)
            cond_price = (t['close'] > t['open']) and (t['close'] > t['ma5'])

            if cond_macd_zero and cond_macd_hist and cond_momentum and cond_obv and cond_vol and cond_price:
                results.append({
                    "代碼": stock_id,
                    "收盤": t['close'],
                    "漲幅%": round(((t['close']/t_1['close'])-1)*100, 2),
                    "張數": int(vol_sheets),
                    "MACD柱": round(t['macd_hist'], 2),
                    "DIF": round(t['dif'], 2),
                    "K值": round(t['k'], 1)
                })
            
            if (i + 1) % 100 == 0: print(f"已掃描: {i+1}/{len(all_stocks)}...")
            time.sleep(0.01)

        except Exception:
            continue

    # --- 報表輸出 ---
    print("\n" + "⚡"*15 + " MACD 共振強勢選股 " + "⚡"*15)
    if results:
        res_df = pd.DataFrame(results).sort_values(by="漲幅%", ascending=False)
        print(res_df.to_string(index=False))
        print(f"\n符合條件標的共：{len(results)} 檔。")
    else:
        print("今日市場無符合共振條件之標的。")
    print("⚡"*50 + "\n")

if __name__ == "__main__":
    run_final_screener()
