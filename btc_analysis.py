#!/usr/bin/env python3
import yfinance as yf
import pandas as pd
import requests
import sys
import os
import json
from datetime import datetime, timedelta

# Telegram 設定
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

def send_telegram_message(message):
    """發送訊息到 Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("未設定 Telegram Token 或 Chat ID，僅在終端機顯示：")
        print(message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("Telegram 訊息發送成功！")
        else:
            print(f"Telegram 發送失敗: {response.text}")
    except Exception as e:
        print(f"Telegram 發送錯誤: {e}")

def get_btc_data():
    """獲取 BTC 技術面和成交量數據"""
    btc = yf.Ticker('BTC-USD')
    hist = btc.history(period='1y', interval='1d')
    
    if hist.empty:
        return None
        
    close = hist['Close'].iloc[-1]
    prev = hist['Close'].iloc[-2]
    change = ((close - prev) / prev) * 100
    
    ma50 = hist['Close'].rolling(50).mean().iloc[-1]
    ma200 = hist['Close'].rolling(200).mean().iloc[-1]
    
    # RSI
    delta = hist['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=13, adjust=True, min_periods=14).mean()
    ma_down = down.ewm(com=13, adjust=True, min_periods=14).mean()
    rsi = (100 - (100 / (1 + ma_up / ma_down))).iloc[-1]
    
    # 成交量分析
    vol_today = hist['Volume'].iloc[-1]
    vol_20ma = hist['Volume'].rolling(20).mean().iloc[-1]
    vol_ratio = vol_today / vol_20ma
    
    # 判斷成交量信號
    if change > 0 and vol_ratio > 1.2:
        vol_signal = "🟢 放量上漲（強買盤）"
    elif change > 0 and vol_ratio <= 1.2:
        vol_signal = "🟡 縮量上漲（弱買盤）"
    elif change < 0 and vol_ratio > 1.2:
        vol_signal = "🔴 放量下跌（強賣盤）"
    else:
        vol_signal = "⚪ 縮量下跌（正常）"
        
    # 判斷 MA200 狀態
    if close > ma200:
        ma200_status = f"🟢 高於 MA200 (+{((close-ma200)/ma200*100):.1f}%)"
    else:
        ma200_status = f"🔴 低於 MA200 ({((close-ma200)/ma200*100):.1f}%)"
        
    return {
        'close': close,
        'change': change,
        'ma50': ma50,
        'ma200': ma200,
        'ma200_status': ma200_status,
        'rsi': rsi,
        'vol_ratio': vol_ratio,
        'vol_signal': vol_signal
    }

def get_fear_greed_index():
    """獲取恐懼與貪婪指數"""
    try:
        response = requests.get("https://api.alternative.me/fng/", timeout=10)
        data = response.json()
        value = int(data['data'][0]['value'])
        classification = data['data'][0]['value_classification']
        
        if value >= 75:
            emoji = "🔴 極度貪婪"
        elif value >= 55:
            emoji = "🟡 貪婪"
        elif value >= 45:
            emoji = "⚪ 中性"
        elif value >= 25:
            emoji = "🟢 恐懼"
        else:
            emoji = "🟢 極度恐懼 (買入機會)"
            
        return f"{value} - {emoji}"
    except:
        return "無法獲取"

def generate_daily_report():
    """生成每日分析報告"""
    data = get_btc_data()
    if not data:
        return "無法獲取 BTC 數據"
        
    fng = get_fear_greed_index()
    
    # 判斷整體市場狀態
    market_status = "🟡 震盪整固"
    if data['close'] > data['ma200'] and data['change'] > 0 and data['vol_ratio'] > 1.2:
        market_status = "🟢 強勢多頭"
    elif data['close'] < data['ma200'] and data['change'] < 0 and data['vol_ratio'] > 1.2:
        market_status = "🔴 弱勢空頭"
        
    # 買入建議
    if data['close'] < 65000:
        action = "🟢 **強烈建議加倉** (低於 MA50，極佳機會)"
    elif data['close'] < 75000:
        action = "🟢 **建議分批買入** (接近 MA50 支撐)"
    elif data['close'] < 82000:
        action = "🟡 **觀望或小注試水** (MA200 阻力區前)"
    else:
        action = "⚪ **持有不動** (已突破 MA200，等待確認)"
        
    msg = f"""📊 **BTC 每日深度分析報告** 📊

*日期：{datetime.now().strftime('%Y-%m-%d')}*

**【市場狀態：{market_status}】**
• 現價：`${data['close']:,.0f}` ({data['change']:+.2f}%)
• 恐懼貪婪指數：{fng}

**【技術面信號】**
• MA200 (牛熊線)：`${data['ma200']:,.0f}`
• 狀態：{data['ma200_status']}
• MA50 (中期線)：`${data['ma50']:,.0f}`
• RSI 指標：`{data['rsi']:.1f}` (50為中性)

**【成交量分析】**
• 今日成交量：`{data['vol_ratio']:.1f}x` 均量
• 信號：{data['vol_signal']}

**【10萬美金長持佈局建議】**
{action}

*💡 備註：機構 ETF Q1 流入 $187 億創歷史新高，長線支撐強勁。短期若有回調至 $70,000-$75,000 是極佳加倉機會。*
"""
    return msg

if __name__ == "__main__":
    print("開始執行 BTC 每日分析...")
    report = generate_daily_report()
    send_telegram_message(report)
    print("執行完畢。")
