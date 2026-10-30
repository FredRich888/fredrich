import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

# 網頁標題與介面設計
st.title("📱 V4 策略手機選股判斷器")
st.write("輸入台股代號（例如：2330、8099），立刻為您檢視是否符合強勢突破條件！")

# 使用者輸入股票代號
stock_input = st.text_input("請輸入台股代號 (例如 2330):", "2330")

if st.button("開始判斷"):
    with st.spinner('正在抓取資料並計算指標中...'):
        try:
            # 清理使用者輸入的代號
            ticker = stock_input.strip().upper()
            
            # 建立要嘗試下載的清單（如果使用者沒加後綴，則依序嘗試上市 .TW 與上櫃 .TWO）
            if ticker.endswith(".TW") or ticker.endswith(".TWO"):
                symbols_to_try = [ticker]
            else:
                symbols_to_try = [f"{ticker}.TW", f"{ticker}.TWO"]
            
            df = pd.DataFrame()
            used_symbol = ""
            
            # 依序嘗試下載，直到成功抓取足夠的資料為止
            for sym in symbols_to_try:
                temp_df = yf.download(sym, period="1y", interval="1d", progress=False)
                if not temp_df.empty and len(temp_df) >= 120:
                    df = temp_df
                    used_symbol = sym
                    break
            
            if df.empty or len(df) < 120:
                st.error("找不到該股票資料，或歷史資料不足 120 天，請確認代號是否正確（支援台股上市櫃純數字）。")
            else:
                # 修正 MultiIndex 欄位問題（yfinance常見格式）
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                # --- 開始 V4 策略計算邏輯 ---
                close = df['Close']
                high = df['High']
                low = df['Low']
                open_p = df['Open']
                volume = df['Volume']

                # 1. 均線 EMA
                ema5 = close.ewm(span=5, adjust=False).mean()
                ema20 = close.ewm(span=20, adjust=False).mean()
                ema60 = close.ewm(span=60, adjust=False).mean()

                # 2. 均量
                mavol5 = volume.rolling(window=5).mean()
                mavol10 = volume.rolling(window=10).mean()

                # 3. RSI
                def calc_rsi(series, period):
                    delta = series.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
                    rs = gain / loss
                    return 100 - (100 / (1 + rs))

                rsi3 = calc_rsi(close, 3)
                rsi6 = calc_rsi(close, 6)

                # 4. MACD
                w_close = (high + low + close * 2) / 4
                ema6 = w_close.ewm(span=6, adjust=False).mean()
                ema12 = w_close.ewm(span=12, adjust=False).mean()
                dif = ema6 - ema12
                macd = dif.ewm(span=2, adjust=False).mean()
                osc = (dif - macd) * 2

                # 5. OBV
                obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()

                # 取最後一天數據
                i = -1
                prior_high = high.iloc[-21:-1].max() # 前20日高點

                # 各項條件判定
                breakout_ok = (close.iloc[i] > prior_high) and (close.iloc[i] > open_p.iloc[i]) and (close.iloc[i] >= open_p.iloc[i] * 1.03)
                trend_ok = (ema5.iloc[i] > ema20.iloc[i]) and (ema5.iloc[i] > ema5.iloc[i-1]) and (ema20.iloc[i] > ema20.iloc[i-1]) and (close.iloc[i] > ema5.iloc[i])
                volume_ok = (volume.iloc[i] >= mavol5.iloc[i] * 2.0) and (mavol5.iloc[i] >= mavol10.iloc[i])
                macd_ok = (dif.iloc[i] > macd.iloc[i]) and (osc.iloc[i] > 0) and (osc.iloc[i] > osc.iloc[i-1])
                obv_ok = (obv.iloc[i] > obv.iloc[i-1]) and (obv.iloc[i] > obv.iloc[i-5:i].mean())
                rsi_ok = (rsi6.iloc[i] >= 50) and (rsi6.iloc[i] <= 99) and (rsi3.iloc[i] <101)
                gap_ratio = close.iloc[i] / ema5.iloc[i] if ema5.iloc[i] > 0 else 0
                price_ok = (gap_ratio > 1.0) and (gap_ratio <= 1.15)

                is_selected = bool(breakout_ok and trend_ok and volume_ok and macd_ok and obv_ok and rsi_ok and price_ok)

                # --- 顯示結果到手機介面 ---
                st.subheader(f"📊 股票代號：{used_symbol} 檢視結果")
                
                if is_selected:
                    st.success("🎉 【符合】此檔股票符合 V4 強勢多頭突破進場條件！")
                else:
                    st.warning("⚠️ 【不符合】目前未達到 V4 的全面突破標準。")

                # 展開各項細節數據供核對
                with st.expander("查看詳細技術指標數據"):
                    st.write(f"- 收盤價: {round(close.iloc[i], 2)} (前20日高: {round(prior_high, 2)}) -> 突破: {'✅' if breakout_ok else '❌'}")
                    st.write(f"- 均線多頭 (EMA5>EMA20): {'✅' if trend_ok else '❌'}")
                    st.write(f"- 成交量放大 (>= 2倍5日均量): {'✅' if volume_ok else '❌'}")
                    st.write(f"- MACD 動能增強: {'✅' if macd_ok else '❌'}")
                    st.write(f"- OBV 籌碼向上: {'✅' if obv_ok else '❌'}")
                    st.write(f"- RSI 區間 (50~99): {'✅' if rsi_ok else '❌'}")
                    st.write(f"- 乖離率控制 (收盤/EMA5 <=1.15): {'✅' if price_ok else '❌'}")

        except Exception as e:
            st.error(f"發生錯誤，請確認股票代號是否正確或稍後再試。詳細錯誤: {e}")
