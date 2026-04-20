import pandas as pd
import numpy as np
from FinMind.data import DataLoader

# --- 參數設定 ---
# 測試包含你 XQ 截圖中的績優股，確保能選出東西
STOCK_LIST = ["1605", "2330", "2317", "2454", "3024", "6205", "8048", "6275", "1609", "3322"] 

def calculate_indicators(df):
    """計算指標前，先進行嚴格的欄位格式化"""
    # 1. 強制所有欄位轉小寫
    df.columns = [str(c).lower() for c in df.columns]
    
    # 2. 處理成交量欄位名稱不一的問題 (FinMind 可能叫 trading_volume 或 volume)
    if 'trading_volume' not in df.columns and 'volume' in df.columns:
        df.rename(columns={'volume': 'trading_volume'}, inplace=True)
    
    # 3. 確保必要欄位都存在，否則跳過該股
    required = ['close', 'open', 'high', 'low', 'trading_volume']
    if not all(col in df.columns for col in required):
        return None

    # --- 開始計算指標 ---
    # 均線
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()

    # RSI (6)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
    df['rsi6'] = 100 - (100 / (1 + (gain / loss.replace(0, np.inf))))

    # KD (9, 3, 3)
    low_min = df['low'].rolling(window=9).min()
    high_max = df['high'].rolling(window=9).max()
    df['rsv'] = (df['close'] - low_min) / (high_max - low_min + 0.0001) * 100
    df['k'] = df['rsv'].ewm(com=2).mean() 
    
    return df

def screen_stocks():
    api = DataLoader()
    results = [] # 確保初始化

    print(f"正在從 FinMind 抓取 {len(STOCK_LIST)} 檔個股數據...")

    for stock_id in STOCK_LIST:
        try:
            # 抓取近期資料
            df = api.taiwan_stock_daily(stock_id=stock_id, start_date='2026-03-01')
            if df.empty or len(df) < 20:
                continue
            
            # 計算指標，若回傳 None 代表欄位有問題
            df = calculate_indicators(df)
            if df is None:
                continue
            
            # 取得最新一筆與前一筆
            t = df.iloc[-1]
            t_1 = df.iloc[-2]

            # --- 篩選邏輯 (參考 XQ 強勢股條件) ---
            # 1. 價格站上 5MA 且 5MA > 20MA
            cond_ma = (t['close'] > t['ma5']) and (t['ma5'] > t['ma20'])
            # 2. 今日實體漲幅 > 1.5% (排除跳空後收黑)
            cond_attack = t['close'] > (t['open'] * 1.015)
            # 3. 成交量過濾 ( FinMind 單位是股，除以 1000 為張 )
            vol_total = t['trading_volume'] / 1000
            cond_vol = vol_total > 300 # 設定 300 張門檻

            if cond_ma and cond_attack and cond_vol:
                results.append({
                    "股票": stock_id,
                    "日期": t['date'],
                    "收盤": t['close'],
                    "漲幅%": round(((t['close']/t_1['close'])-1)*100, 2),
                    "張數": int(vol_total),
                    "K值": round(t['k'], 1),
                    "RSI": round(t['rsi6'], 1)
                })

        except Exception as e:
            # 單一股票出錯不中斷整個程序
            continue

    # --- 輸出結果 ---
    print("\n" + "="*50)
    if results:
        res_df = pd.DataFrame(results)
        print(f"篩選成功！資料日期：{results[0]['date']}")
        print(res_df.to_string(index=False))
    else:
        print("今日無符合條件個股，或當日盤後數據尚未完全匯入。")
    print("="*50 + "\n")

if __name__ == "__main__":
    screen_stocks()
