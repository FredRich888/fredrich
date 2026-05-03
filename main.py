import os  # 系統環境變數讀取
import requests  # 發送 Telegram 請求
import pandas as pd  # 資料分析與表格處理
import numpy as np  # 數學運算與邏輯判斷
from FinMind.data import DataLoader  # 抓取台股數據
from datetime import datetime, timedelta  # 時間處理

# --- 🛠️ 核心參數自定義區 (可隨時修改) ---
MIN_PRICE = 12       # 最低股價過濾
MAX_PRICE = 300      # 最高股價過濾
VOL_RATIO_MIN = 1.5  # 成交量必須是均量的幾倍以上
MIN_VOL_SHEETS = 500 # 當天成交量最少要幾張

def send_telegram(message):  # 定義傳送 Telegram 訊息函數
    token = os.getenv("TG_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")  # 讀取機器人 Token
    chat_id = os.getenv("TG_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")  # 讀取你的 Chat ID
    if not token or not chat_id: return  # 沒設定好就不跑
    url = f"https://api.telegram.org/bot{token}/sendMessage"  # API 網址
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}  # 設定格式為 Markdown
    requests.post(url, data=payload)  # 執行發送

def calculate_indicators(df):  # 定義技術指標計算函數
    df.columns = [str(c).lower() for c in df.columns]  # 統一欄位名稱為小寫
    # --- 均線類 ---
    df['ma5'] = df['close'].rolling(5).mean()  # 5日均線
    df['ma20'] = df['close'].rolling(20).mean()  # 20日均線
    df['ma60'] = df['close'].rolling(60).mean()  # 60日均線
    df['vol_ma5'] = df['trading_volume'].rolling(5).mean()  # 5日均量
    # --- MACD 類 ---
    ema12 = df['close'].ewm(span=12, adjust=False).mean()  # 快線 EMA
    ema26 = df['close'].ewm(span=26, adjust=False).mean()  # 慢線 EMA
    df['dif'] = ema12 - ema26  # DIF 線
    df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()  # MACD 信號線
    df['hist'] = df['dif'] - df['dea']  # MACD 柱狀體
    # --- K線型態類 ---
    df['range'] = df['high'] - df['low']  # 當日震幅
    df['body'] = (df['close'] - df['open']).abs()  # 實體紅線長度
    df['k_body_ratio'] = np.where(df['range'] > 0, df['body'] / df['range'], 0)  # 實體佔比
    return df

def analyze_stock(stock_id, dl):  # 定義核心分析邏輯
    try:
        sid = str(stock_id).split('.')[0].strip()  # 格式化股票代號
        df = dl.taiwan_stock_daily(stock_id=sid, start_date=(datetime.now() - timedelta(days=80)).strftime('%Y-%m-%d'))
        if len(df) < 40: return None  # 資料量不足則跳過
        
        curr = df.iloc[-1]  # 取得最新一筆資料
        prev = df.iloc[-2]  # 取得前一交易日資料
        
        # --- [第一關：硬指標過濾] ---
        if not (MIN_PRICE <= curr['close'] <= MAX_PRICE): return None  # 價格不在區間內就踢掉
        if (curr['trading_volume'] / 1000) < MIN_VOL_SHEETS: return None  # 張數太少就踢掉
        
        df = calculate_indicators(df)  # 計算技術指標
        t = df.iloc[-1]  # 取得最新計算後的結果
        t_1 = df.iloc[-2]  # 取得前一天的計算結果
        
        # --- [第二關：技術型態核心條件] ---
        cond_macd = (t['dif'] > 0) and (t['hist'] > t_1['hist'])  # MACD 多頭且紅柱增長
        cond_vol = t['trading_volume'] > (t['vol_ma5'] * VOL_RATIO_MIN)  # 爆量突破
        cond_price = (t['close'] > t['open']) and (t['close'] > t['ma5'])  # 價格收紅且站上 5 日線
        
        if not (cond_macd and cond_vol and cond_price): return None  # 基本條件不符就跳過
        
        # --- [第三關：AI 評分系統 (Scoring)] ---
        score = 100  # 初始基礎分
        # 1. 均線糾結加分 (如你圖中的糾結後突破)
        ma_list = [t['ma5'], t['ma20'], t['ma60']]
        tangle_pct = (max(ma_list) - min(ma_list)) / min(ma_list) * 100
        score += max(0, (10 - tangle_pct) * 20)  # 越糾結加分越高
        # 2. 量能放大加分
        vol_ratio = t['trading_volume'] / t['vol_ma5']
        score += min(vol_ratio * 30, 200)  # 量比越大加分越高
        # 3. 漲幅強度加分
        change_pct = ((t['close'] / t_1['close']) - 1) * 100
        score += min(change_pct * 25, 250)
        # 4. 均線多頭排列加分
        if t['ma5'] > t['ma20'] > t['ma60']: score += 100
        # 5. K棒實體比例加分 (代表買氣扎實)
        score += t['k_body_ratio'] * 50
        
        return {
            "id": sid, "price": t['close'], "change": round(change_pct, 2),
            "score": int(score), "vol_r": round(vol_ratio, 1), "tangle": round(tangle_pct, 1)
        }
    except: return None

def main():  # 主程式
    dl = DataLoader()  # 初始化
    fm_token = os.getenv("FINMIND_TOKEN")  # 抓取 Token
    if fm_token: dl.login_by_token(fm_token)  # 登入
    
    # --- 混合式掃描：先抓全市場 4 碼代號的股票 ---
    print("🔍 正在獲取市場清單並進行全自動 AI 掃描...")
    stock_info = dl.taiwan_stock_info()  # 獲取全台股基本資料
    all_stocks = stock_info[stock_info['stock_id'].str.len() == 4]['stock_id'].tolist()  # 只取 4 碼股票
    
    candidates = []  # 準備存放合格股票
    for sid in all_stocks:  # 循環全市場
        res = analyze_stock(sid, dl)  # 進行深度分析
        if res: candidates.append(res)  # 合格就放入清單
        
    # --- 排序與報告發送 ---
    top_stocks = sorted(candidates, key=lambda x: x['score'], reverse=True)[:8]  # 取前 8 強
    
    date_str = datetime.now().strftime('%Y-%m-%d')  # 取得日期
    header = f"🏆 *AI 多因子突破報表 ({date_str})*\n過濾條件: {MIN_PRICE}-{MAX_PRICE}元 | 量 > {MIN_VOL_SHEETS}張\n\n"
    
    if top_stocks:
        body = ""
        for i, s in enumerate(top_stocks, 1):  # 組合訊息內容
            body += f"{i}. `{s['id']}` 價:*{s['price']}* (漲{s['change']}%) \n"
            body += f" 評分:*{s['score']}* | 量比:{s['vol_r']} | 糾結:{s['tangle']}%\n\n"
        msg = header + body
    else:
        msg = header + "⚠️ 今日市場動能不足，無符合「爆量突破糾結」之標的。"
    
    print(msg)  # 終端機顯示
    send_telegram(msg)  # 傳送到手機

if __name__ == "__main__":
    main()  # 啟動！
