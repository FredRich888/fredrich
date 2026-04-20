import pandas as pd
import numpy as np
from FinMind.data import DataLoader

# --- 參數設定 ---
STOCK_LIST = ["2330", "2317", "2454", "2303", "2382", "3231"]  # 這裡放你想監控的股票代碼
VOL_FILTER = 500  # 最小成交量(張)

def calculate_indicators(df):
    """計算均線、KD、RSI"""
    # 1. 均線
    df['ma5'] = df['Close'].rolling(window=5).mean()
    df['ma20'] = df['Close'].rolling(window=20).mean()
    df['ma60'] = df['Close'].rolling(window=60).mean()

    # 2. RSI (6日)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
    rs = gain / loss
    df['rsi6'] = 100 - (100 / (1 + rs))

    # 3. KD (9, 3, 3)
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    df['rsv'] = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['k'] = df['rsv'].ewm(com=2).mean() # 權數3對應 com=2
    df['d'] = df['k'].ewm(com=2).mean()
    
    return df

def screen_stocks():
    api = DataLoader()
    results = []

    for stock_id in STOCK_LIST:
        try:
            # 獲取股價資料 (抓取近120天確保均線計算正確)
            df = api.taiwan_stock_daily(stock_id=stock_id, start_date='2024-01-01')
            if df.empty or len(df) < 60: continue
            
            # 獲取籌碼資料 (外資買賣超)
            chip = api.taiwan_stock_institutional_investors(stock_id=stock_id, start_date='2024-01-01')
            chip = chip[chip['name'] == 'Foreign_Investor'].groupby('date')['buy'].sum() - \
                   chip[chip['name'] == 'Foreign_Investor'].groupby('date')['sell'].sum()
            chip.name = 'foreign_net_buy'
            
            # 合併資料
            df = df.merge(chip, on='date', how='left').fillna(0)
            df = calculate_indicators(df)
            
            # 取得最新兩筆資料進行邏輯判斷 (T 與 T-1)
            t = df.iloc[-1]      # 當日 (或最新盤中)
            t_1 = df.iloc[-2]    # 昨日
            t_2 = df.iloc[-3]    # 前日

            # --- 條件實作 ---
            # 1. 昨收 > 5MA
            cond1 = t_1['Close'] > t_1['ma5']
            # 2. 60MA 趨勢向上
            cond2 = t_1['ma60'] > t_2['ma60']
            # 3. 5MA 向上穿過 20MA (昨日黃金交叉)
            cond3 = (t_1['ma5'] > t_1['ma20']) and (t_2['ma5'] <= t_2['ma20'])
            # 4. 外資昨日買超
            cond4 = t_1['foreign_net_buy'] > 0
            # 5. 量增 (昨日量 > 前日量 * 1.5)
            cond5 = t_1['Volume'] > (t_2['Volume'] * 1.5)
            # 6. RSI > 50
            cond6 = t_1['rsi6'] > 50
            # 7. K > 50
            cond7 = t_1['k'] > 50
            # 8. 今日實體紅K漲幅超過 3% (攻擊訊號)
            cond8 = t['Close'] >= (t['Open'] * 1.03)
            # 9. 昨量過濾
            cond9 = (t_1['Volume'] / 1000) > VOL_FILTER # FinMind 量通常是原始張數或股數，依據資料調整

            # --- 篩選邏輯 ---
            # 符合 (站上均線 OR 均線金叉) AND 外資買超 AND 今日攻擊 AND 量能過濾
            if (cond1 or cond3) and cond4 and cond8 and cond9:
                results.append({
                    "股票代碼": stock_id,
                    "當前價格": t['Close'],
                    "漲幅": round(((t['Close']/t_1['Close'])-1)*100, 2),
                    "昨日外資買超": t_1['foreign_net_buy'],
                    "RSI": round(t['rsi6'], 2),
                    "K值": round(t['k'], 2)
                })

        except Exception as e:
            print(f"處理 {stock_id} 時發生錯誤: {e}")

    # 輸出結果
    if results:
        print("\n=== 多頭強勢攻擊訊號 篩選結果 ===")
        print(pd.DataFrame(results))
    else:
        print("\n今日無符合條件個股")

if __name__ == "__main__":
    screen_stocks()

if __name__ == "__main__":
    main()
