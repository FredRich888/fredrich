import pandas as pd
import numpy as np
from FinMind.data import DataLoader

# --- 參數設定 ---
STOCK_LIST = ["2330", "2317", "2454", "2303", "2382", "3231"] 
VOL_FILTER = 500  

def calculate_indicators(df):
    """計算均線、KD、RSI (注意 FinMind 欄位為小寫)"""
    # 1. 均線
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()

    # 2. RSI (6日)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
    rs = gain / loss
    df['rsi6'] = 100 - (100 / (1 + rs))

    # 3. KD (9, 3, 3)
    low_min = df['low'].rolling(window=9).min()
    high_max = df['high'].rolling(window=9).max()
    df['rsv'] = (df['close'] - low_min) / (high_max - low_min) * 100
    df['k'] = df['rsv'].ewm(com=2).mean() 
    df['d'] = df['k'].ewm(com=2).mean()
    
    return df

def screen_stocks():
    api = DataLoader()
    results = []

    for stock_id in STOCK_LIST:
        try:
            # 獲取股價資料
            df = api.taiwan_stock_daily(stock_id=stock_id, start_date='2026-01-01')
            if df.empty or len(df) < 60: continue
            
            # 獲取籌碼資料
            chip = api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date='2026-01-01')
            if not chip.empty:
                chip = chip[chip['name'] == 'Foreign_Investor'].groupby('date')['buy'].sum() - \
                       chip[chip['name'] == 'Foreign_Investor'].groupby('date')['sell'].sum()
                chip.name = 'foreign_net_buy'
                df = df.merge(chip, on='date', how='left').fillna(0)
            else:
                df['foreign_net_buy'] = 0
                
            df = calculate_indicators(df)
            
            # 取得最新資料
            t = df.iloc[-1]      
            t_1 = df.iloc[-2]    
            t_2 = df.iloc[-3]    

            # --- 條件實作 (改為小寫欄位) ---
            cond1 = t_1['close'] > t_1['ma5']
            cond2 = t_1['ma60'] > t_2['ma60']
            cond3 = (t_1['ma5'] > t_1['ma20']) and (t_2['ma5'] <= t_2['ma20'])
            cond4 = t_1['foreign_net_buy'] > 0
            cond5 = t_1['Volume'] > (t_2['Volume'] * 1.5)
            cond6 = t_1['rsi6'] > 50
            cond7 = t_1['k'] > 50
            cond8 = t['close'] >= (t['open'] * 1.03)
            cond9 = (t_1['Volume'] / 1000) > VOL_FILTER 

            if (cond1 or cond3) and cond4 and cond8 and cond9:
                results.append({
                    "股票": stock_id,
                    "收盤價": t['close'],
                    "漲幅%": round(((t['close']/t_1['close'])-1)*100, 2),
                    "外資買超": t_1['foreign_net_buy'],
                    "RSI": round(t['rsi6'], 2),
                    "K值": round(t['k'], 2)
                })

        except Exception as e:
            print(f"處理 {stock_id} 時發生錯誤: {e}")

    if results:
        print("\n=== 多頭強勢攻擊訊號 篩選結果 ===")
        print(pd.DataFrame(results))
    else:
        print("\n今日無符合條件個股")

if __name__ == "__main__":
    screen_stocks()

if __name__ == "__main__":
    main()
