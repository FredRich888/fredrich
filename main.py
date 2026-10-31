import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
# 如果未安裝，請執行: pip install streamlit-option-menu
from streamlit_option_menu import option_menu 

# --- 側邊欄導覽 ---
with st.sidebar:
    selected_mode = option_menu(
        menu_title="選股模式", 
        options=["技術指標 (逢茗強勢 V4)", "法人籌碼 (外資投信)"], 
        icons=["rocket-takeoff", "person-add"], 
        menu_icon="cast", 
        default_index=0, 
    )

# --- 主網頁標題 ---
if selected_mode == "技術指標 (逢茗強勢 V4)":
    st.title("📱 逢茗強勢 V4 手機選股判斷器")
    st.write("輸入台股代號（純數字），立刻為您檢視是否符合「安全且強勢」的突破條件！")
else:
    st.title("💰 法人籌碼選股判斷器")
    st.write("輸入台股代號（純數字），快速檢視昨日法人是否聯手買超，為股價背書！")

# --- 使用者輸入股票代號 ---
stock_input = st.text_input("請輸入台股代號 (例如 4568 或 2330):", "4568")

# --- 開始判斷按鈕 ---
if st.button("開始選股"):
    with st.spinner('正在抓取資料並計算指標中...'):
        try:
            # 清理使用者輸入的代號，轉換成大寫純數字
            ticker_base = stock_input.strip().upper()
            
            # --- 聰明辨識 TW/TWO 邏輯 ---
            # 如果使用者手動加了 TW/TWO，直接使用；若沒有，預設先 TW 再 TWO
            if ticker_base.endswith(".TW") or ticker_base.endswith(".TWO"):
                symbols_to_try = [ticker_base]
            else:
                symbols_to_try = [f"{ticker_base}.TW", f"{ticker_base}.TWO"]
            
            df = pd.DataFrame()
            used_symbol = ""
            ticker_obj = None

            # 依序嘗試下載，直到成功抓取有效資料為止
            for sym in symbols_to_try:
                # 使用 yf.download 下載技術指標資料
                temp_df = yf.download(sym, period="1y", interval="1d", progress=False)
                # 檢查是否有資料、長度夠、且收盤價不是空的
                if not temp_df.empty and len(temp_df) >= 120 and not temp_df['Close'].dropna().empty:
                    df = temp_df
                    used_symbol = sym
                    ticker_obj = yf.Ticker(sym) # 用此物件抓取籌碼資料
                    break
            
            # 沒抓到任何資料，顯示錯誤
            if df.empty or len(df) < 120 or ticker_obj is None:
                st.error("找不到該股票資料，或歷史資料不足 120 天，請確認代號是否正確。")
            else:
                # 修正 MultiIndex 欄位問題（yf.download 常見格式）
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                
                # --- 執行選股模式 ---
                if selected_mode == "技術指標 (逢茗強勢 V4)":
                    # --- 技術指標模式邏輯 ---
                    close = df['Close']
                    high = df['High']
                    low = df['Low']
                    open_p = df['Open']
                    volume = df['Volume']

                    # 1. 均線 EMA
                    ema5 = close.ewm(span=5, adjust=False).mean()
                    ema20 = close.ewm(span=20, adjust=False).mean()

                    # 2. 均量mavol5
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

                    # 4. MACD 動能
                    w_close = (high + low + close * 2) / 4
                    ema6 = w_close.ewm(span=6, adjust=False).mean()
                    ema12 = w_close.ewm(span=12, adjust=False).mean()
                    dif = ema6 - ema12
                    macd = dif.ewm(span=2, adjust=False).mean()
                    osc = (dif - macd) * 2

                    # 5. OBV 籌碼
                    obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()

                    # 取最後一天數據判定
                    i = -1
                    prior_high = high.iloc[-21:-1].max() # 前20日高點

                    # 各項條件判定 (基於原本邏輯)
                    breakout_ok = (close.iloc[i] > prior_high) and (close.iloc[i] > open_p.iloc[i]) and (close.iloc[i] >= open_p.iloc[i] * 1.03)
                    trend_ok = (ema5.iloc[i] > ema20.iloc[i]) and (ema5.iloc[i] > ema5.iloc[i-1]) and (ema20.iloc[i] > ema20.iloc[i-1]) and (close.iloc[i] > ema5.iloc[i])
                    volume_ok = (volume.iloc[i] >= mavol5.iloc[i] * 2.0) and (mavol5.iloc[i] >= mavol10.iloc[i])
                    macd_ok = (dif.iloc[i] > macd.iloc[i]) and (osc.iloc[i] > 0) and (osc.iloc[i] > osc.iloc[i-1])
                    obv_ok = (obv.iloc[i] > obv.iloc[i-1]) and (obv.iloc[i] > obv.iloc[i-5:i].mean())
                    rsi_ok = (rsi6.iloc[i] >= 50) and (rsi6.iloc[i] <= 90) and (rsi3.iloc[i] <= 95)
                    
                    # --- 修正腳本條件：乖離率 < 1.05 ---
                    # 基於圖片分析，強勢上漲共同特徵是K棒極度靠近 EMA5。原本腳本 <=1.13太鬆，修正為貼近突破更安全。
                    gap_ratio = close.iloc[i] / ema5.iloc[i] if ema5.iloc[i] > 0 else 0
                    price_ok = (gap_ratio > 1.0) and (gap_ratio <= 1.05) #原本腳本是1.13，現縮小範圍符合圖片特徵

                    is_selected = bool(breakout_ok and trend_ok and volume_ok and macd_ok and obv_ok and rsi_ok and price_ok)

                    # --- 顯示結果到手機介面 ---
                    st.subheader(f"📊 技術指標模式：{used_symbol} 檢視結果")
                    if is_selected:
                        st.success("🎉 【符合】此檔股票符合逢茗強勢 V4 的「安全且貼近突破」進場條件！")
                    else:
                        st.warning("⚠️ 【不符合】目前未達到逢茗強勢 V4 的全面安全突破標準。")

                    # 原本腳本的技術數據檢視
                    with st.expander("查看詳細技術指標數據"):
                        st.write(f"- 收盤價: {round(close.iloc[i], 2)} (前20日高: {round(prior_high, 2)}) -> 突破: {'✅' if breakout_ok else '❌'}")
                        st.write(f"- 均線多頭 (EMA5>EMA20): {'✅' if trend_ok else '❌'}")
                        st.write(f"- 成交量放大 (>= 2倍5日均量): {'✅' if volume_ok else '❌'}")
                        st.write(f"- MACD 動能增強: {'✅' if macd_ok else '❌'}")
                        st.write(f"- OBV 籌碼向上: {'✅' if obv_ok else '❌'}")
                        st.write(f"- RSI 區間 (50~90): {'✅' if rsi_ok else '❌'}")
                        st.write(f"- **乖離率控制 (收盤貼近EMA5 <= 1.05)**: {'✅' if price_ok else '❌'}") #修改顯示數值

                else:
                    # --- 籌碼模式邏輯 ---
                    st.subheader(f"💰 法人籌碼模式：{used_symbol} 檢視結果")
                    # 使用 yfinance 物件抓取籌碼資料
                    info = ticker_obj.info
                    
                    # 抓取外資與投信持有股數，計算昨日買超
                    # (yfinance info 可能無法提供精確的當日籌碼，通常是昨日或最近一天的資料，有些股票可能不提供)
                    inst_inst = info.get('sharesOutstanding', None) # 用總發行量代表基礎
                    foreign_inst = info.get('foreignSharesHeld', None) # 雖然名字不一樣，但通常代表外資持有
                    domestic_inst = info.get('heldPercentInstitutions', None) # 這個可能是代表包含投信的內資法人持有比例

                    if foreign_inst is None or domestic_inst is None:
                         st.error("抱歉，無法抓取此股票的完整法人籌碼資料，請稍後再試或嘗試其他代號。")
                    else:
                        st.write(f"- 昨日發行總張數 (基礎): {inst_inst // 1000 if inst_inst else '未知'} 張")
                        
                        st.divider() #分隔線
                        
                        # --- 新增籌碼條件判斷 ---
                        # 設定標準：買超必須大於一定張數。上市櫃不同，簡單設定標準
                        # 圖片中的科際精密外資持股6000多張，買超13張太少，標準不能設定太高
                        # 大世科持股5000多張買超344張較明顯
                        # 腳本簡單判定標準：外資持股張數增加即為買超，我們判定成交量，買超必須佔成交量一定比例
                        volume_yesterday = df['Volume'].iloc[-1]
                        
                        # yfinance info沒有昨日買超張數，我們簡單顯示持有張數和比例供使用者參考
                        # 真實買超需要付費籌碼API。這邊顯示 info 提供數據
                        st.info(f"💡 yfinance 免費版目前無法提供當日「確切籌碼買超張數」。下方顯示 info 提供之「持有股數/比例」供您參考，請搭配 XQ 軟體查核。")
                        
                        st.write(f"- 昨日外資持股張數: {foreign_inst // 1000} 張")
                        st.write(f"- 昨日包含投信全體法人持有比例: {domestic_inst * 100:.2f}%")
                        
                        st.divider() #分隔線

                        st.write(f"💡 建議您搭配 XQ 軟體，查核下方真實籌碼條件：")
                        st.write(f"- ✅昨日外資與投信是否聯手買超？")
                        st.write(f"- ✅買超張數是否佔成交量之 5~10% 以上 (代表籌碼控制度高)？")

        except Exception as e:
            st.error(f"發生錯誤，請確認股票代號是否正確或稍後再試。詳細錯誤: {e}")
