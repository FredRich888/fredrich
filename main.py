import pandas as pd
import numpy as np
from FinMind.data import DataLoader

# --- 參數設定 ---
# 測試包含你截圖中出現的股票 (如 1605, 8048 等)
STOCK_LIST = ["1605", "2330", "2317", "2454", "3024", "6205", "8048", "6275"] 
VOL_FILTER = 500  

def calculate_indicators(df):
    # 【強制統一欄位】將所有欄位名稱轉為小寫
    df.columns = [str(c).lower() for c in df.columns]
    
    # 【檢查必要欄位】
    required = ['close', 'open', 'high', 'low', 'trading_volume']
    for col in required:
        if col not in df.columns:
            # 有些版本 trading_volume 可能叫 volume
            if col == 'trading_volume' and 'volume' in df.columns:
                df.rename(columns={'volume': 'trading_volume'}, inplace=True)
            else:
                raise ValueError(f"缺少必要欄位: {col}")

    # 均線計算
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()

    # RSI (3)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
    df['rsi6'] = 100 - (100 / (1 + (gain / loss.replace(0, np.inf))))

    # KD (5, 3, 3)
    low_min = df['low'].rolling(window=9).min()
    high_max = df['high'].rolling(window=9).max()
    df['rsv'] = (df['close'] - low_min) / (high_max - low_min + 0.0001) * 100
    df['k'] = df['rsv'].ewm(com=2).mean() 
    return df

def screen_stocks():
    api = DataLoader()
    results = [] # 確保變數在一開始就建立

    for stock_id in STOCK_LIST:
        try:
            # 抓取股價 (多抓一點資料確保指標穩定)
            df = api.taiwan_stock_daily(stock_id=stock_id, start_date='2026-02-01')
            if df.empty or len(df) < 10: 
                continue
            
            # 計算指標 (內部已處理大小寫)
            df = calculate_indicators(df)
            
            # 取得最新一筆 (T) 與 前一筆 (T-1)
            t = df.iloc[-1]      
            t_1 = df.iloc[-2]    

            # --- 選股邏輯 (參考 XQ 常用強勢股條件) ---
            # 1. 價格站上 5MA 且 5MA 向上
            cond_price = t['close'] > t['ma5']
            # 2. 今日漲幅實體 (收盤 > 開盤 1.5%) -> 捕捉強勢攻擊
            cond_attack = t['close'] >= (t['open'] * 1.015)
            # 3. 5MA > 20MA (短期多頭)
            cond_ma = t['ma5'] > t['ma20']
            # 4. 成交量過濾 (Trading_volume 單位是股，除以 1000 變張)
            vol_shares = t.get('trading_volume', 0)
            cond_vol = (vol_shares / 1000) > 200 # 門檻下修到 200 張增加獲選率

            # 符合條件就加入清單
            if cond_price and cond_attack and cond_ma and cond_vol:
                results.append({
                    "股票代碼": stock_id,
                    "日期": t['date'],
                    "收盤價": t['close'],
                    "漲幅%": round(((t['close']/t_1['close'])-1)*100, 2),
                    "成交量(張)": int(vol_shares/1000),
                    "K值": round(t['k'], 1),
                    "RSI": round(t['rsi3'], 1)
                })

        except Exception as e:
            print(f"處理 {stock_id} 時跳過，原因: {e}")

    # --- 輸出結果 ---
    print("-" * 30)
    if results:
        print(f"=== 多頭強勢攻擊選股結果 (資料日期: {results[0]['日期']}) ===")
        print(pd.DataFrame(results))
    else:
        print("今日無符合條件個股 (可能是數據源尚未更新當日收盤價)")
    print("-" * 30)

if __name__ == "__main__":
    screen_stocks()
