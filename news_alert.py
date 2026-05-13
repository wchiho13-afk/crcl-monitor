#!/usr/bin/env python3
"""
重大新聞即時警報系統 v1.0
每 30 分鐘掃描一次，有重大新聞才發送 Telegram 通知
涵蓋：CRCL、BTC、Trump、宏觀政策
"""

import os
import json
import hashlib
import requests
import feedparser
from datetime import datetime, timedelta

# ============================================================
# 設定
# ============================================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8712513930:AAF_n3MYED5mMXLEMoEbyU3tGZrzmDvzNTY')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '8366663316')

# 已發送過的新聞記錄（避免重複）
SENT_NEWS_FILE = '/tmp/sent_news.json'

# ============================================================
# 重大新聞關鍵字分類
# ============================================================
NEWS_CATEGORIES = {

    '🔵 CRCL 重大消息': {
        'queries': ['Circle Internet CRCL stablecoin'],
        'keywords': [
            # 法案相關（最重要）
            'genius act', 'clarity act', 'stablecoin bill', 'stablecoin act',
            'senate vote', 'house vote', 'congress', 'signed into law',
            # 分析師評級
            'upgrade', 'downgrade', 'price target', 'buy rating', 'outperform',
            'overweight', 'strong buy', 'analyst',
            # 監管
            'sec', 'cftc', 'regulation', 'regulatory', 'compliance',
            # 業務
            'partnership', 'integration', 'earnings', 'revenue', 'q1', 'q2', 'q3', 'q4',
            'usdc', 'blackrock', 'coinbase', 'meta',
            # 重大事件
            'ipo', 'acquisition', 'merger', 'lawsuit', 'investigation',
        ],
        'emoji': '🔵',
        'importance': 'high'
    },

    '🟠 BTC 重大消息': {
        'queries': ['Bitcoin BTC price crypto market'],
        'keywords': [
            # 聯儲局（最重要）
            'federal reserve', 'fed rate', 'interest rate', 'powell', 'fomc',
            'rate hike', 'rate cut', 'inflation', 'cpi', 'ppi',
            # ETF 機構
            'etf', 'blackrock', 'fidelity', 'microstrategy', 'institutional',
            'spot bitcoin', 'etf inflow', 'etf outflow',
            # 監管
            'sec bitcoin', 'bitcoin ban', 'crypto regulation', 'legal tender',
            'government bitcoin', 'national reserve',
            # 技術面大事
            'halving', 'all-time high', 'ath', '$100,000', '$150,000',
            'whale', 'exchange outflow',
            # 宏觀
            'recession', 'gdp', 'unemployment', 'dollar index',
        ],
        'emoji': '🟠',
        'importance': 'high'
    },

    '🇺🇸 Trump / 貿易 / 宏觀': {
        'queries': ['Trump China trade tariff crypto Bitcoin'],
        'keywords': [
            # Trump 直接相關
            'trump bitcoin', 'trump crypto', 'trump tariff', 'trump china',
            'trump xi', 'trump fed', 'trump powell', 'executive order',
            # 貿易戰
            'tariff', 'trade war', 'trade deal', 'china us', 'us china',
            'beijing summit', 'trade truce',
            # 加密政策
            'crypto policy', 'digital asset', 'crypto reserve',
            'strategic bitcoin reserve', 'white house crypto',
            # 伊朗 / 地緣政治
            'iran', 'oil price', 'geopolitical', 'war',
        ],
        'emoji': '🇺🇸',
        'importance': 'medium'
    },

    '⚡ 穩定幣 / 加密監管': {
        'queries': ['stablecoin regulation crypto law 2026'],
        'keywords': [
            'stablecoin regulation', 'usdc regulation', 'tether',
            'crypto law', 'digital dollar', 'cbdc',
            'genius act', 'clarity act', 'fit21',
            'crypto tax', 'defi regulation',
        ],
        'emoji': '⚡',
        'importance': 'high'
    },
}

# ============================================================
# 工具函數
# ============================================================
def load_sent_news():
    """載入已發送的新聞記錄"""
    try:
        if os.path.exists(SENT_NEWS_FILE):
            with open(SENT_NEWS_FILE, 'r') as f:
                data = json.load(f)
                # 只保留 24 小時內的記錄
                cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
                return {k: v for k, v in data.items() if v > cutoff}
    except:
        pass
    return {}

def save_sent_news(sent):
    """保存已發送的新聞記錄"""
    try:
        with open(SENT_NEWS_FILE, 'w') as f:
            json.dump(sent, f)
    except:
        pass

def news_hash(title):
    """生成新聞標題的唯一 hash"""
    return hashlib.md5(title.lower().encode()).hexdigest()[:12]

def send_telegram(msg):
    """發送 Telegram 消息"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"❌ 發送失敗: {e}")
        return False

def fetch_news(query, max_items=10):
    """從 Google News RSS 抓取新聞"""
    url = f'https://news.google.com/rss/search?q={query.replace(" ", "+")}&hl=en-US&gl=US&ceid=US:en'
    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:max_items]:
            title = entry.get('title', '').strip()
            link = entry.get('link', '')
            published = entry.get('published', '')

            # 清理標題（去掉來源）
            if ' - ' in title:
                clean_title = title.rsplit(' - ', 1)[0]
                source = title.rsplit(' - ', 1)[1]
            else:
                clean_title = title
                source = 'Unknown'

            items.append({
                'title': clean_title,
                'source': source,
                'link': link,
                'published': published,
                'hash': news_hash(clean_title)
            })
    except Exception as e:
        print(f"[新聞] 抓取失敗: {e}")
    return items

def is_important(title, keywords):
    """判斷新聞是否包含重要關鍵字"""
    title_lower = title.lower()
    matched = [kw for kw in keywords if kw.lower() in title_lower]
    return len(matched) > 0, matched

# ============================================================
# 主程式
# ============================================================
def scan_breaking_news():
    sent_news = load_sent_news()
    alerts_sent = 0
    now_str = datetime.now().strftime("%m月%d日 %H:%M")

    print(f"[{now_str}] 開始掃描重大新聞...")

    for category_name, config in NEWS_CATEGORIES.items():
        emoji = config['emoji']
        keywords = config['keywords']

        for query in config['queries']:
            news_items = fetch_news(query, max_items=8)

            for item in news_items:
                title = item['title']
                h = item['hash']

                # 跳過已發送的
                if h in sent_news:
                    continue

                # 檢查是否包含重要關鍵字
                important, matched_kws = is_important(title, keywords)

                if important:
                    # 構建警報消息
                    msg = f"🚨 *重大消息警報* 🚨\n"
                    msg += f"━━━━━━━━━━━━━━━━━━\n"
                    msg += f"{category_name}\n\n"
                    msg += f"📌 *{title}*\n\n"
                    msg += f"🔑 觸發關鍵字：`{', '.join(matched_kws[:3])}`\n"
                    msg += f"🕐 時間：{now_str}\n\n"

                    # 根據類別加入操作建議
                    if 'CRCL' in category_name:
                        if any(kw in title.lower() for kw in ['genius act', 'clarity act', 'senate vote', 'signed']):
                            msg += "💡 *操作提示：穩定幣法案消息！CRCL 可能大幅波動，密切關注。*"
                        elif any(kw in title.lower() for kw in ['upgrade', 'buy', 'outperform', 'target']):
                            msg += "💡 *操作提示：分析師正面評級，CRCL 短期看漲。*"
                        elif any(kw in title.lower() for kw in ['downgrade', 'sell', 'underperform']):
                            msg += "💡 *操作提示：分析師負面評級，注意風險。*"
                        else:
                            msg += "💡 *操作提示：留意對 CRCL 的影響。*"

                    elif 'BTC' in category_name:
                        if any(kw in title.lower() for kw in ['rate hike', 'rate cut', 'fomc', 'fed']):
                            msg += "💡 *操作提示：聯儲局消息！對 BTC 影響重大，加息偏空，減息偏多。*"
                        elif any(kw in title.lower() for kw in ['etf', 'institutional', 'blackrock']):
                            msg += "💡 *操作提示：機構動向消息，ETF 流入偏多，流出偏空。*"
                        elif any(kw in title.lower() for kw in ['ban', 'regulation', 'sec']):
                            msg += "💡 *操作提示：監管消息，注意短期波動，長線不影響。*"
                        else:
                            msg += "💡 *操作提示：留意對 BTC 的影響。*"

                    elif 'Trump' in category_name:
                        if any(kw in title.lower() for kw in ['tariff', 'trade war', 'china']):
                            msg += "💡 *操作提示：貿易消息！貿易戰升級偏空，停火偏多。*"
                        elif any(kw in title.lower() for kw in ['bitcoin reserve', 'crypto policy']):
                            msg += "💡 *操作提示：Trump 加密政策消息，可能對 BTC 和 CRCL 有直接影響！*"
                        else:
                            msg += "💡 *操作提示：宏觀消息，留意市場反應。*"

                    elif '穩定幣' in category_name:
                        msg += "💡 *操作提示：穩定幣監管消息，直接影響 CRCL！*"

                    # 發送
                    print(f"  🚨 發送警報: {title[:50]}...")
                    if send_telegram(msg):
                        sent_news[h] = datetime.now().isoformat()
                        alerts_sent += 1
                    break  # 每個 query 只發一條最重要的

    save_sent_news(sent_news)

    if alerts_sent == 0:
        print(f"  ✅ 無重大新聞（正常）")
    else:
        print(f"  ✅ 共發送 {alerts_sent} 條重大新聞警報")

    return alerts_sent

# ============================================================
# 執行
# ============================================================
if __name__ == "__main__":
    scan_breaking_news()
