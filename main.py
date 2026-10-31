import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

# 網頁標題與介面設計
st.title("📱 逢茗手機選股判斷器")
st.write("輸入台股代號（例如：4526、4568），立刻為您檢視是否符合強勢突破條件！")

# 使用者輸入股票代號
stock_input = st.text_input("請輸入台股代號 (例如 4526):", "4526")

if st.button("開始判斷"):
    with st.spinner('正在精算台股結算與技術指標中...'):
        try:
            ticker = stock_input.strip().upper()
            
            # 自動判斷上市櫃 (.TWO 優先於 .TW)
            if ticker.endswith(".TW") or ticker.endswith(".TWO"):
                symbols_to_try = [ticker]
            else:
                symbols_to_try = [f"{ticker}.TWO", f"{ticker}.TW"]
            
            df = pd.DataFrame()
            used_symbol = ""
            
            for sym in symbols_to_try:
                temp_df = yf.download(sym, period="1y", interval="1d", progress=False)
                if not temp_df.empty and len(temp_df) >= 120:
                    if isinstance(temp_df.columns, pd.MultiIndex):
                        temp_df.columns = temp_df.columns.get_level_values(0)
                    if 'Close' in temp_df.columns and not temp_df['Close'].dropna().empty:
                        df = temp_df
                        used_symbol = sym
                        break
            
            if df.empty or len(df) < 120 or 'Close' not in df.columns:
                st.error("找不到該股票資料，或歷史資料不足 120 天，請確認代號是否正確。")
            else:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                df = df.dropna(subset=['Close', 'Volume'])
                
                close = df['Close']
                high = df['High']
                low = df['Low']
                open_p = df['Open']
                volume = df['Volume'] / 1000.0  # 轉換為張數

                # 1. 均線 EMA (精準對齊看盤軟體的遞迴邏輯)
                def calc_ema(series, span):
                    # 使用 min_periods 確保初始化穩定
                    return series.ewm(span=span, adjust=False, min_periods=span).mean()

                ema5 = calc_ema(close, 5)
                ema20 = calc_ema(close, 20)
                ema60 = calc_ema(close, 60)

                # 2. 均量
                mavol5 = volume.rolling(window=5).mean()
                mavol10 = volume.rolling(window=10).mean()

                # 3. RSI (標準 Wells Wilder 平滑法)
                def calc_rsi(series, period):
                    delta = series.diff()
                    gain = delta.where(delta > 0, 0.0)
                    loss = -delta.where(delta < 0, 0.0)
                    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
                    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
                    rs = avg_gain / avg_loss
                    return 100 - (100 / (1 + rs))

                rsi3 = calc_rsi(close, 3)
                rsi6 = calc_rsi(close, 6)

                # 4. MACD (對齊 XQ 的 DIF 6-12 參數)
                ema6 = calc_ema(close, 6)
                ema12 = calc_ema(close, 12)
                dif = ema6 - ema12
                macd = calc_ema(dif, 2)
                osc = (dif - macd) * 2

                # 5. OBV
                obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()

                # 取最後一天數據
                i = -1
                last_date = df.index[i].strftime('%Y-%m-%d')
                prior_high = high.iloc[-21:-1].max() # 前20日高點

                # 各項條件判定
                breakout_ok = (close.iloc[i] > prior_high) and (close.iloc[i] > open_p.iloc[i]) and (close.iloc[i] >= open_p.iloc[i] * 1.03)
                trend_ok = (ema5.iloc[i] > ema20.iloc[i]) and (ema5.iloc[i] > ema5.iloc[i-1]) and (ema20.iloc[i] > ema20.iloc[i-1]) and (close.iloc[i] > ema5.iloc[i])
                volume_ok = (volume.iloc[i] >= mavol5.iloc[i] * 2.0) and (mavol5.iloc[i] >= mavol10.iloc[i])
                macd_ok = (dif.iloc[i] > macd.iloc[i]) and (osc.iloc[i] > 0) and (osc.iloc[i] > osc.iloc[i-1])
                obv_ok = (obv.iloc[i] > obv.iloc[i-1]) and (obv.iloc[i] > obv.iloc[i-5:i].mean())
                
                rsi_ok = (rsi6.iloc[i] >= 50) and (rsi6.iloc[i] <= 99) and (rsi3.iloc[i] <= 100)
                
                gap_ratio = close.iloc[i] / ema5.iloc[i] if ema5.iloc[i] > 0 else 0
                price_ok = (gap_ratio > 1.0) and (gap_ratio < 1.13)

                is_selected = bool(breakout_ok and trend_ok and volume_ok and macd_ok and obv_ok and rsi_ok and price_ok)

                # --- 顯示結果到手機介面 ---
                st.subheader(f"📊 股票代號：{used_symbol} (結算日期: {last_date})")
                
                if is_selected:
                    st.success("🎉 【符合】此檔股票符合 V4 強勢多頭突破進場條件！")
                else:
                    st.warning("⚠️ 【不符合】目前未達到 V4 的全面突破標準。")

                # 展開各項實際計算數值供核對
                with st.expander("🔍 點此查看實際計算數值與對比"):
                    st.write(f"• **收盤價**: {round(close.iloc[i], 2)}  | 前20高: {round(prior_high, 2)} -> 突破: {'✅' if breakout_ok else '❌'}")
                    st.write(f"• **EMA5**: {round(ema5.iloc[i], 2)}  | EMA20: {round(ema20.iloc[i], 2)}  -> 多頭: {'✅' if trend_ok else '❌'}")
                    st.write(f"• **成交量**: {round(volume.iloc[i], 1)} 張 | 5日均量: {round(mavol5.iloc[i], 1)} 張 -> 量增: {'✅' if volume_ok else '❌'}")
                    st.write(f"• **MACD(DIF 6-12)**: DIF={round(dif.iloc[i], 2)}, MACD={round(macd.iloc[i], 2)}, OSC={round(osc.iloc[i], 2)} -> 動能: {'✅' if macd_ok else '❌'}")
                    st.write(f"• **OBV**: {round(obv.iloc[i], 0)} -> 向上: {'✅' if obv_ok else '❌'}")
                    st.write(f"• **RSI**: RSI3={round(rsi3.iloc[i], 2)}% , RSI6={round(rsi6.iloc[i], 2)}%  -> 區間: {'✅' if rsi_ok else '❌'}")
                    st.write(f"• **乖離率**: 收盤/EMA5 = {round(gap_ratio, 3)} (<1.13) -> 控制: {'✅' if price_ok else '❌'}")

        except Exception as e:
            st.error(f"發生錯誤，請確認股票代號是否正確或稍後再試。詳細錯誤: {e}")
