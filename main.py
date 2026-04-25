import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import time

# --- 核心參數 ---
PRICE_CEILING = 200      # 股價上限
KD_PERIOD = 5            # 短波段 KD 週期
RSI_S, RSI_L = 3, 6      # 極短線 RSI 參數
VOL_MULTIPLIER = 1.2     # 成交量需超過 5 日均量的 1.2 倍 (放量)
MIN_VOLUME_SHEETS = 500  # 最少成交張數門檻

def calculate_technical_indicators(df):
    """計算整合後的技術指標，並處理資料缺失"""
    try:
        df.columns = [str(c).lower() for c in df.columns]
        if 'trading_volume' not in df.columns and 'volume' in df.columns:
            df.rename(columns={'volume': 'trading_volume'}, inplace=True)
        
        # 1. 均線系統 (MA5, MA20)
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        df['vol_ma5'] = df['trading_volume'].rolling(window=5).mean()

        # 2. RSI 指標 (3, 6) - 採用 EMA 平滑法
        for p in [RSI_S, RSI_L]:
            delta = df['close'].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            # alpha = 1 / period -> com = period - 1
            ema_up = up.ewm(com=p-1, adjust=False).mean()
            ema_down = down.ewm(com=p-1, adjust=False).mean()
            rs = ema_up / ema_down.replace(0, np.nan)
            df[f'rsi{p}'] = 100 - (100 / (1 + rs))

        # 3. KD 指標 (5, 3, 3)
        low_min = df['low'].rolling(window=KD_PERIOD).min()
        high_max = df['high'].rolling(window=KD_PERIOD).max()
        rsv = (df['close'] - low_min) / (high_max - low_min).replace(0, np.nan) * 100
        df['k'] = rsv.ewm(com=2, adjust=False).mean()
        df['d'] = df['k'].ewm(com=2, adjust=False).mean()

        return df
    except Exception:
        return None

def run_integrated_screener():
    api = DataLoader()
    
    # 1. 自動抓取全市場普通股代碼
    print("Step 1: 正在獲取全台灣上市櫃股票清單...")
    stock_info = api.taiwan_stock_info()
    # 僅篩選代碼為 4 碼的普通股 (排除權證、ETF)
    all_stocks = stock_info[stock_info['stock_id'].str.len() == 4]['stock_id'].tolist()
    
    start_dt = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
    results = []

    print(f"Step 2: 開始掃描 {len(all_stocks)} 檔標的 (設定: 價格 < {PRICE_CEILING})...")

    # 為了演示速度，此處取樣或您可以直接跑全量
    # all_stocks = all_stocks[:300] 

    for i, stock_id in enumerate(all_stocks):
        try:
            df = api.taiwan_stock_daily(stock_id=stock_id, start_date=start_dt)
            
            # 基本門檻過濾：資料量需足夠且價格在 200 以下
            if df.empty or len(df) < 20: continue
            current_price = df.iloc[-1]['close']
            if current_price >= PRICE_CEILING or current_price < 10: continue

            df = calculate_technical_indicators(df)
            if df is None: continue
            
            t = df.iloc[-1]   # 今日資料
            t_1 = df.iloc[-2] # 昨日資料

            # --- 嚴格強勢股篩選邏輯 ---
            # A. 均線多頭：現價 > MA5 且 MA5 > MA20 (或是 MA5 剛上穿 MA20)
            cond_ma = t['close'] > t['ma5'] and t['ma5'] > t['ma20'] * 0.98
            
            # B. 動能爆發：RSI(3) 高於 RSI(6) 且 K > D
            cond_momentum = t[f'rsi{RSI_S}'] > t[f'rsi{RSI_L}'] and t['k'] > t['d']
            
            # C. 量能突破：成交量 > 5日均量的 1.2 倍 且 至少有 500 張
            vol_sheets = t['trading_volume'] / 1000
            cond_vol = (t['trading_volume'] > t['vol_ma5'] * VOL_MULTIPLIER) and (vol_sheets > MIN_VOLUME_SHEETS)

            # D. 實體紅棒：收盤 > 開盤 (非假漲)
            cond_red_k = t['close'] > t['open']

            if cond_ma and cond_momentum and cond_vol and cond_red_k:
                results.append({
                    "代碼": stock_id,
                    "收盤": t['close'],
                    "漲幅%": round(((t['close']/t_1['close'])-1)*100, 2),
                    "成交量(張)": int(vol_sheets),
                    "K值(5)": round(t['k'], 1),
                    "RSI(3)": round(t[f'rsi{RSI_S}'], 1),
                    "狀態": "量價齊揚"
                })
            
            # 每 50 支顯示一次進度，避免畫面太冷清
            if (i + 1) % 50 == 0:
                print(f"進度: {i+1}/{len(all_stocks)}...")
            
            # 遵守 API 頻率限制
            time.sleep(0.05)

        except Exception:
            continue

    # --- 輸出最終戰報 ---
    print("\n" + "★"*20 + " 強勢選股掃描報告 " + "★"*20)
    if results:
        res_df = pd.DataFrame(results)
        # 優先顯示漲幅最高者
        res_df = res_df.sort_values(by="漲幅%", ascending=False)
        print(res_df.to_string(index=False))
        print(f"\n今日共選出 {len(results)} 檔符合「主升段」特徵之股票。")
    else:
        print("今日市場未發現完全符合「極短線爆發」條件之個股。")
    print("★"*60 + "\n")

if __name__ == "__main__":
    run_integrated_screener()


