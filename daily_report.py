#!/usr/bin/env python3
"""
每日市場日報系統 v1.0
每天自動發送 CRCL + BTC 完整分析到 Telegram
包含：最重要新聞、今日要留意的事、買入位置建議
"""

import os
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import feedparser

# ============================================================
# 設定
# ============================================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8712513930:AAF_n3MYED5mMXLEMoEbyU3tGZrzmDvzNTY')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '8366663316')

# 你的持倉
CRCL_COST = 121.43
CRCL_INVESTED = 30000
BTC_COST = 79000
BTC_INVESTED = 30000

# ============================================================
# Telegram 發送
# ============================================================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }, timeout=15)
        if r.status_code == 200:
            print("✅ 發送成功")
        else:
            print(f"❌ 發送失敗: {r.text}")
    except Exception as e:
        print(f"❌ 錯誤: {e}")

# ============================================================
# 技術指標計算
# ============================================================
def get_indicators(ticker_symbol, period='90d'):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period=period)
        if hist.empty or len(hist) < 20:
            return None

        price = hist['Close'].iloc[-1]
        prev = hist['Close'].iloc[-2]
        chg_pct = (price - prev) / prev * 100

        # RSI
        delta = hist['Close'].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rsi = float((100 - 100 / (1 + gain / loss)).iloc[-1])

        # MA
        ma20 = float(hist['Close'].rolling(20).mean().iloc[-1])
        ma50 = float(hist['Close'].rolling(50).mean().iloc[-1])

        # 布林帶
        std = float(hist['Close'].rolling(20).std().iloc[-1])
        bb_upper = ma20 + 2 * std
        bb_lower = ma20 - 2 * std

        # 成交量
        vol_today = float(hist['Volume'].iloc[-1])
        vol_avg = float(hist['Volume'].rolling(20).mean().iloc[-1])
        vol_ratio = vol_today / vol_avg if vol_avg > 0 else 1.0

        # 52週高低
        high_52w = float(hist['High'].tail(252).max())
        low_52w = float(hist['Low'].tail(252).min())

        return {
            'price': price,
            'chg_pct': chg_pct,
            'rsi': rsi,
            'ma20': ma20,
            'ma50': ma50,
            'bb_upper': bb_upper,
            'bb_lower': bb_lower,
            'vol_ratio': vol_ratio,
            'high_52w': high_52w,
            'low_52w': low_52w,
        }
    except Exception as e:
        print(f"[指標] {ticker_symbol} 錯誤: {e}")
        return None

# ============================================================
# 新聞抓取
# ============================================================
def get_top_news(query, max_items=5):
    feeds = [
        f'https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en',
    ]
    items = []
    seen = set()
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items]:
                title = entry.get('title', '').strip()
                if title and title not in seen:
                    seen.add(title)
                    # 清理標題（去掉來源）
                    if ' - ' in title:
                        clean = title.rsplit(' - ', 1)[0]
                    else:
                        clean = title
                    items.append(clean[:80])
        except Exception as e:
            print(f"[新聞] 錯誤: {e}")
    return items[:max_items]

# ============================================================
# 判斷市場狀態
# ============================================================
def get_market_status(ind):
    price = ind['price']
    rsi = ind['rsi']
    ma20 = ind['ma20']
    ma50 = ind['ma50']
    bb_upper = ind['bb_upper']
    bb_lower = ind['bb_lower']
    vol_ratio = ind['vol_ratio']

    signals = []
    warnings = []
    score = 0

    # RSI 判斷
    if rsi < 35:
        signals.append("RSI 超賣（買入機會）")
        score += 2
    elif rsi < 50:
        signals.append("RSI 偏低（中性偏好）")
        score += 1
    elif rsi > 70:
        warnings.append("RSI 超買（謹慎追高）")
        score -= 1
    else:
        signals.append("RSI 中性")

    # 均線判斷
    if price > ma20:
        signals.append(f"站上 MA20（短期趨勢向上）")
        score += 1
    else:
        warnings.append(f"跌破 MA20（短期偏弱）")
        score -= 1

    if price > ma50:
        signals.append(f"站上 MA50（中期趨勢向上）")
        score += 1
    else:
        warnings.append(f"低於 MA50（中期偏弱）")

    # 布林帶
    bb_pos = (price - bb_lower) / (bb_upper - bb_lower) * 100
    if bb_pos < 20:
        signals.append("接近布林下軌（超賣區）")
        score += 2
    elif bb_pos > 80:
        warnings.append("接近布林上軌（超買區）")
        score -= 1

    # 成交量
    if vol_ratio > 2.0:
        signals.append(f"成交量放大 {vol_ratio:.1f}x（大資金活躍）")
        score += 1

    # 總體判斷
    if score >= 3:
        status = "🟢 強力買入機會"
    elif score >= 1:
        status = "🟡 中性偏好，可小注"
    elif score == 0:
        status = "⚪ 中性觀望"
    else:
        status = "🔴 謹慎，等待回調"

    return status, signals, warnings

# ============================================================
# CRCL 買入區間計算
# ============================================================
def get_crcl_buy_zones(ind):
    ma20 = ind['ma20']
    bb_lower = ind['bb_lower']
    ma50 = ind['ma50']

    # 進取模式（當前支撐附近）
    aggressive_z1 = (round(ma20 * 0.97, 2), round(ma20 * 0.99, 2))
    aggressive_z2 = (round(ma20 * 0.94, 2), round(ma20 * 0.96, 2))

    # 保守模式（MA20 以下）
    conservative_z1 = (round(bb_lower * 1.01, 2), round(ma20 * 0.98, 2))
    conservative_z2 = (round(ma50 * 0.98, 2), round(ma50 * 1.00, 2))

    return aggressive_z1, aggressive_z2, conservative_z1, conservative_z2

# ============================================================
# BTC 買入區間計算
# ============================================================
def get_btc_buy_zones(ind):
    price = ind['price']
    ma20 = ind['ma20']
    ma50 = ind['ma50']
    bb_lower = ind['bb_lower']

    z1 = (round(ma20 * 0.97, 0), round(ma20 * 1.00, 0))
    z2 = (round(ma50 * 0.98, 0), round(ma50 * 1.02, 0))
    z3 = (round(bb_lower * 0.97, 0), round(bb_lower * 1.00, 0))

    return z1, z2, z3

# ============================================================
# 主報告生成
# ============================================================
def generate_daily_report():
    now = datetime.now()
    date_str = now.strftime("%m月%d日 %H:%M")
    weekday = ["週一","週二","週三","週四","週五","週六","週日"][now.weekday()]

    print("正在生成每日日報...")

    # 獲取數據
    crcl_ind = get_indicators('CRCL')
    btc_ind = get_indicators('BTC-USD')

    # 獲取新聞
    print("正在抓取新聞...")
    crcl_news = get_top_news('Circle+Internet+CRCL+stablecoin')
    btc_news = get_top_news('Bitcoin+BTC+price+crypto')

    # ============================================================
    # 組合報告
    # ============================================================
    msg = f"📋 *每日市場日報 · {date_str} ({weekday})*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    # ===== CRCL 部分 =====
    msg += "🔵 *CRCL（Circle Internet Group）*\n"

    if crcl_ind:
        price = crcl_ind['price']
        chg = crcl_ind['chg_pct']
        rsi = crcl_ind['rsi']
        ma20 = crcl_ind['ma20']

        # 持倉浮盈
        shares = CRCL_INVESTED / CRCL_COST
        pnl = (price - CRCL_COST) * shares
        pnl_pct = (price - CRCL_COST) / CRCL_COST * 100

        chg_emoji = "📈" if chg > 0 else "📉"
        msg += f"現價：*${price:.2f}* {chg_emoji} {chg:+.2f}%\n"
        msg += f"你的持倉：成本 ${CRCL_COST} | 浮盈 *${pnl:+,.0f}* ({pnl_pct:+.1f}%)\n\n"

        # 市場狀態
        status, signals, warnings = get_market_status(crcl_ind)
        msg += f"*市場狀態：{status}*\n"

        # 關鍵指標
        msg += f"RSI：{rsi:.0f}  |  MA20：${ma20:.2f}\n"
        vol_emoji = "🔥" if crcl_ind['vol_ratio'] > 2 else "📊"
        msg += f"{vol_emoji} 成交量：{crcl_ind['vol_ratio']:.1f}x 均量\n\n"

        # 買入位置
        az1, az2, cz1, cz2 = get_crcl_buy_zones(crcl_ind)
        msg += f"*🎯 今日買入位置：*\n"
        msg += f"🟠 進取：第一批 ${az1[0]}-${az1[1]} | 第二批 ${az2[0]}-${az2[1]}\n"
        msg += f"🔵 保守：第一批 ${cz1[0]}-${cz1[1]} | 第二批 ${cz2[0]}-${cz2[1]}\n\n"

        # 今日要留意
        msg += f"*⚠️ 今日要留意：*\n"
        for w in warnings[:2]:
            msg += f"• {w}\n"
        for s in signals[:2]:
            msg += f"• {s}\n"
        msg += "\n"

    else:
        msg += "⚠️ 無法獲取 CRCL 數據（美股可能未開市）\n\n"

    msg += "─────────────────────\n\n"

    # ===== BTC 部分 =====
    msg += "🟠 *BTC（比特幣）*\n"

    if btc_ind:
        price = btc_ind['price']
        chg = btc_ind['chg_pct']
        rsi = btc_ind['rsi']
        ma20 = btc_ind['ma20']
        ma50 = btc_ind['ma50']

        # 持倉浮盈
        btc_held = BTC_INVESTED / BTC_COST
        pnl = (price - BTC_COST) * btc_held
        pnl_pct = (price - BTC_COST) / BTC_COST * 100

        chg_emoji = "📈" if chg > 0 else "📉"
        msg += f"現價：*${price:,.0f}* {chg_emoji} {chg:+.2f}%\n"
        msg += f"你的持倉：成本 ${BTC_COST:,} | 浮盈 *${pnl:+,.0f}* ({pnl_pct:+.1f}%)\n\n"

        # 市場狀態
        status, signals, warnings = get_market_status(btc_ind)
        msg += f"*市場狀態：{status}*\n"

        # 關鍵指標
        msg += f"RSI：{rsi:.0f}  |  MA20：${ma20:,.0f}  |  MA50：${ma50:,.0f}\n"
        vol_emoji = "🔥" if btc_ind['vol_ratio'] > 2 else "📊"
        msg += f"{vol_emoji} 成交量：{btc_ind['vol_ratio']:.1f}x 均量\n\n"

        # 買入位置
        bz1, bz2, bz3 = get_btc_buy_zones(btc_ind)
        msg += f"*🎯 加倉位置建議：*\n"
        msg += f"第二批（${bz1[0]:,.0f}-${bz1[1]:,.0f}）— MA20 支撐\n"
        msg += f"第三批（${bz2[0]:,.0f}-${bz2[1]:,.0f}）— MA50 支撐\n"
        msg += f"超跌機會（${bz3[0]:,.0f}-${bz3[1]:,.0f}）— 布林下軌\n\n"

        # 今日要留意
        msg += f"*⚠️ 今日要留意：*\n"
        for w in warnings[:2]:
            msg += f"• {w}\n"
        for s in signals[:2]:
            msg += f"• {s}\n"
        msg += "\n"

    else:
        msg += "⚠️ 無法獲取 BTC 數據\n\n"

    msg += "─────────────────────\n\n"

    # ===== 今日最重要新聞 =====
    msg += "📰 *今日最重要新聞*\n\n"

    msg += "🔵 *CRCL 相關：*\n"
    if crcl_news:
        for i, news in enumerate(crcl_news[:3], 1):
            msg += f"{i}. {news}\n"
    else:
        msg += "暫無最新消息\n"
    msg += "\n"

    msg += "🟠 *BTC / 加密市場：*\n"
    if btc_news:
        for i, news in enumerate(btc_news[:3], 1):
            msg += f"{i}. {news}\n"
    else:
        msg += "暫無最新消息\n"
    msg += "\n"

    # ===== 總結 =====
    msg += "─────────────────────\n"
    msg += "💡 *今日策略提示：*\n"

    tips = []
    if crcl_ind and crcl_ind['rsi'] > 65:
        tips.append("CRCL RSI 偏高，不追高，等回調再加倉")
    elif crcl_ind and crcl_ind['rsi'] < 40:
        tips.append("CRCL RSI 偏低，是加倉好機會")
    else:
        tips.append("CRCL 繼續持有，等穩定幣法案催化劑")

    if btc_ind and btc_ind['price'] < btc_ind['ma20'] * 0.97:
        tips.append("BTC 跌破 MA20，考慮第二批加倉")
    elif btc_ind and btc_ind['rsi'] > 70:
        tips.append("BTC RSI 超買，不追高，等回調")
    else:
        tips.append("BTC 繼續持有，等 Trump-Xi 峰會消息")

    for tip in tips:
        msg += f"• {tip}\n"

    msg += "\n_沒有信號 = 不需要行動 = 安心去生活_ 😊"

    return msg

# ============================================================
# 執行
# ============================================================
if __name__ == "__main__":
    report = generate_daily_report()
    print("\n" + "="*50)
    print("報告預覽：")
    print("="*50)
    print(report[:500] + "...")
    print("="*50)
    send_telegram(report)
