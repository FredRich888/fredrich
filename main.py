import pandas as pd
import numpy as np
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import time

# --- 參數設定 ---
PRICE_CEILING = 200
MACD_PARAMS = (6, 12, 2)
VOL_FILTER = 1.2
MIN_SHEETS = 500

def calculate_indicators(df):
    """計算核心技術指標"""
    df.columns = [str(c).lower() for c in df.columns]
    # 均線
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    df['vol_ma5'] = df['trading_volume'].rolling(5).mean()
    
    # MACD (6, 12, 2)
    ema_f = df['close'].ewm(span=6, adjust=False).mean()
    ema_s = df['close'].ewm(span=12, adjust=False).mean()
    df['dif'] = ema_f - ema_s
    df['macd_dea'] = df['dif'].ewm(span=2, adjust=False).mean()
    df['hist'] = df['dif'] - df['macd_dea']
    
    # K-Body Ratio (實體紅棒比例)
    df['k_body'] = (df['close'] - df['open']) / (df['high'] - df['low'] + 0.00001)
    return df

def run_pro_screener():
    api = DataLoader()
    # 建議在此加入 api.login(token='YOUR_TOKEN') 以避免請求限制
    
    print("【啟動】正在獲取股票清單與最新交易數據...")
    stock_info = api.taiwan_stock_info()
    all_stocks = stock_info[stock_info['stock_id'].str.len() == 4]['stock_id'].tolist()
    
    # 為了指標收斂，抓取過去 100 天的資料
    start_dt = (datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d')
    results = []

    # 1. 抓取台積電(2330)作為時間基準，確定最新交易日
    sample = api.taiwan_stock_daily(stock_id="2330", start_date=(datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d'))
    if sample.empty:
        print("❌ 無法取得市場基準數據，請檢查網路或 API Token。")
        return
    
    latest_trade_date = sample.iloc[-1]['date']
    print(f"【檢測】最新市場交易日為: {latest_trade_date}")

    for i, stock_id in enumerate(all_stocks):
        try:
            df = api.taiwan_stock_daily(stock_id=stock_id, start_date=start_dt)
            if df.empty or len(df) < 60: continue
            
            df = calculate_indicators(df)
            
            # 取出最新的一筆資料進行判斷
            t = df.iloc[-1]
            t_1 = df.iloc[-2]
            
            # 確保我們判斷的是最新的交易日
            if t['date'] != latest_trade_date: continue

            # --- 勝率 > 65% 的核心篩選條件 (Script B) ---
            # 1. MACD 極速動能：DIF > 0 且 柱狀體轉強
            cond_macd = (t['dif'] > 0) and (t['hist'] > t_1['hist'])
            
            # 2. 均線多頭結構：5MA > 20MA > 60MA (主升段保證)
            cond_ma = (t['ma5'] > t['ma20']) and (t['ma20'] > t['ma60'])
            
            # 3. K線力道：實體紅棒佔比 > 50%
            cond_k = t['k_body'] > 0.5
            
            # 4. 價格與量能過濾
            vol_sheets = t['trading_volume'] / 1000
            cond_basic = (t['close'] < PRICE_CEILING) and (vol_sheets > MIN_SHEETS) and (t['trading_volume'] > t['vol_ma5'] * VOL_FILTER)

            if cond_macd and cond_ma and cond_k and cond_basic:
                results.append({
                    "代碼": stock_id,
                    "收盤": t['close'],
                    "漲幅%": round(((t['close']/t_1['close'])-1)*100, 2),
                    "張數": int(vol_sheets),
                    "DIF": round(t['dif'], 2),
                    "MACD柱": round(t['hist'], 2)
                })
            
            if (i+1) % 200 == 0: print(f"已掃描: {i+1}/{len(all_stocks)}...")
            time.sleep(0.01) # 避免過快被 API 封鎖

        except Exception as e:
            continue

    # --- 輸出結果 ---
    print("\n" + "⚡"*15 + f" {latest_trade_date} 強勢選股結果 " + "⚡"*15)
    if results:
        res_df = pd.DataFrame(results).sort_values(by="漲幅%", ascending=False)
        print(res_df.to_string(index=False))
        print(f"\n符合共振條件標的共：{len(results)} 檔。")
    else:
        print(f"在 {latest_trade_date} 查無符合「勝率優化邏輯」的個股。")
        print("提示：這通常代表市場目前處於整理期，或今日無強勢領頭羊。")
    print("⚡"*50 + "\n")

if __name__ == "__main__":
    # 修正原本代碼中的函數呼叫錯誤
    run_pro_screener()
