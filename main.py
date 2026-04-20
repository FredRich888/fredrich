import pandas as pd
import numpy as np
from FinMind.data import DataLoader

# --- 參數設定 ---
# 這裡我增加了一些你 XQ 截圖中的績優股來測試
STOCK_LIST = ["1605", "2330", "2317", "2454", "3024", "6205", "8048", "6275"] 
VOL_FILTER = 500  

def calculate_indicators(df):
    # 確保欄位都是小寫
    df.columns = [c.lower() for c in df.columns]
    
    # 均線
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()

    # RSI (6)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
    df['rsi6'] = 100 - (100 / (1 + (gain / loss)))

    # KD (9, 3, 3)
    low_min = df['low'].rolling(window=9).min()
    high_max = df['high'].rolling(window=9).max()
    df['rsv'] = (df['close'] - low_min) / (high_max - low_min) * 100
    df['k'] = df['rsv'].ewm(com=2).mean() 
    return df

def screen_stocks():
    api = DataLoader()
    results = []

    for stock_id in STOCK_LIST:
        try:
            # 抓取股價
            df = api.taiwan_stock_daily(stock_id=stock_id, start_date='2026-01-01')
            if df.empty or len(df) < 10: continue
            
            # 修正欄位名稱 (FinMind 的成交量叫 trading_volume)
            df = calculate_indicators(df)
            
            # 取得最新數據
            t = df.iloc[-1]      
            t_1 = df.iloc[-2]    
            t_2 = df.iloc[-3]    

            # --- 調整後的條件 ---
            # 1. 價格高於 5MA
            cond_price = t['close'] > t['ma5']
            # 2. 漲幅條件 (稍微放寬到 2% 試試看，因為 FinMind 數據可能有落差)
            cond_attack = t['close'] >= (t['open'] * 1.02)
            # 3. 均線多頭排列或剛站上
            cond_ma = t['close'] > t['ma20']
            # 4. 成交量過濾 (Trading_volume 單位是股，除以 1000 變張)
            cond_vol = (t['trading_volume'] / 1000) > 100

            # 綜合判斷 (先不強求外資，先求有清單)
            if cond_price and cond_attack and cond_vol:
                results.append({
                    "股票": stock_id,
                    "收盤": t['close'],
                    "漲幅%": round(((t['close']/t_1['close'])-1)*100, 2),
                    "成交量(張)": int(t['trading_volume']/1000),
                    "K值": round(t['k'], 1),
                    "RSI": round(t['rsi6'], 1)
                })

        except Exception as e:
            print(f"處理 {stock_id} 錯誤: {e}")

    if results:
        print(f"\n=== 篩選結果 (更新日期: {df.iloc[-1]['date']}) ===")
        print(pd.DataFrame(results))
    else:
        print("\n今日數據尚未更新或無符合個股，請稍後再試。")

if __name__ == "__main__":
    screen_stocks()

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
