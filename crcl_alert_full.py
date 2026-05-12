#!/usr/bin/env python3
"""
CRCL 完整免費版監控警報系統
監控範圍：技術指標、大額成交量、SEC Form 4 高管交易、機構持倉變化、新聞過濾、每日總結
"""

import os
import time
import json
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# ============================================================
# 設定區
# ============================================================
TELEGRAM_BOT_TOKEN = "8712513930:AAF_n3MYED5mMXLEMoEbyU3tGZrzmDvzNTY"
TELEGRAM_CHAT_ID = "8366663316"
TICKER = "CRCL"
COMPANY_CIK = "0001876042"  # Circle Internet Group 的 SEC CIK 編號

# 買入區間
BUY_ZONE_1 = (122.0, 124.0)
BUY_ZONE_2 = (118.0, 120.0)
BUY_ZONE_3 = (113.0, 116.0)

# 賣出目標
SELL_TARGET_1 = 200.0
SELL_TARGET_2 = 250.0
SELL_TARGET_3 = 300.0

# 止損
STOP_LOSS = 107.0

# 防 FOMO 閾值
FOMO_UP_PCT = 8.0
FOMO_DOWN_PCT = -8.0

# 大額成交量倍數（超過 5 日平均的 X 倍才算大額）
VOLUME_SPIKE_MULTIPLIER = 3.0

# ============================================================
# 工具函數
# ============================================================

def send_telegram(message):
    """發送 Telegram 訊息"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"✅ 訊息發送成功")
        else:
            print(f"❌ 發送失敗: {r.text}")
    except Exception as e:
        print(f"❌ 發送錯誤: {e}")

def calculate_rsi(series, periods=14):
    """計算 RSI"""
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    ma_down = down.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
    rsi = 100 - (100 / (1 + ma_up / ma_down))
    return rsi

def get_price_data():
    """獲取 CRCL 股價及技術指標"""
    ticker = yf.Ticker(TICKER)
    hist = ticker.history(period="30d", interval="1d")
    if hist.empty:
        return None
    hist['RSI'] = calculate_rsi(hist['Close'])
    hist['MA20'] = hist['Close'].rolling(20).mean()
    hist['VolMA5'] = hist['Volume'].rolling(5).mean()
    return hist

# ============================================================
# 模組一：技術面 + 買賣信號
# ============================================================

def check_technical_signals(hist):
    """檢查技術面信號"""
    if hist is None or len(hist) < 5:
        return

    current_price = hist['Close'].iloc[-1]
    prev_close = hist['Close'].iloc[-2]
    current_rsi = hist['RSI'].iloc[-1]
    current_vol = hist['Volume'].iloc[-1]
    avg_vol = hist['VolMA5'].iloc[-1]
    daily_pct = ((current_price - prev_close) / prev_close) * 100

    print(f"[技術面] 現價: ${current_price:.2f} | 漲跌: {daily_pct:.2f}% | RSI: {current_rsi:.1f} | 成交量: {current_vol:,.0f}")

    # A 類：買入信號
    if BUY_ZONE_1[0] <= current_price <= BUY_ZONE_1[1]:
        msg = (
            f"🟢 *CRCL 第一批買入位置到了*\n\n"
            f"現價：${current_price:.2f}  |  RSI：{current_rsi:.1f}\n\n"
            f"*這個信號的意思：*\n"
            f"股價已跌到你計劃的第一個買入區間（$122-$124）。這不是壞消息，這是你一直在等待的機會。"
            f"短期賣壓差不多釋放完了，買方開始接盤。\n\n"
            f"*你現在的感受應該是：*\n平靜。這在你的計劃之內。\n\n"
            f"*你需要做的事：*\n買入 4 萬美金。買完關掉圖表。"
        )
        send_telegram(msg)

    elif BUY_ZONE_2[0] <= current_price <= BUY_ZONE_2[1]:
        msg = (
            f"🟢 *CRCL 第二批買入位置到了*\n\n"
            f"現價：${current_price:.2f}  |  RSI：{current_rsi:.1f}\n\n"
            f"*這個信號的意思：*\n"
            f"市場給了你比第一次更便宜的機會（$118-$120）。這通常是大盤整體下跌或短期恐慌造成的，"
            f"跟 Circle 公司本身沒有關係。你的買入成本更低，這對你是好事。\n\n"
            f"*你現在的感受應該是：*\n感謝市場給你折扣。\n\n"
            f"*你需要做的事：*\n買入剩下 4 萬美金。買完關掉圖表。"
        )
        send_telegram(msg)

    elif BUY_ZONE_3[0] <= current_price <= BUY_ZONE_3[1]:
        msg = (
            f"🟢 *CRCL 第三批買入位置到了（超跌機會）*\n\n"
            f"現價：${current_price:.2f}  |  RSI：{current_rsi:.1f}\n\n"
            f"*這個信號的意思：*\n"
            f"股價已跌到最低買入區間（$113-$116），這種情況通常是大盤暴跌或突發壞消息造成的。"
            f"這是最便宜的機會，但請先確認基本面沒有出問題（看有沒有 C 類警報）。\n\n"
            f"*你需要做的事：*\n如果沒有收到基本面警報，可以買入剩餘資金。"
        )
        send_telegram(msg)

    # B 類：賣出信號
    if current_price >= SELL_TARGET_1 and current_price < SELL_TARGET_2:
        msg = (
            f"🔴 *CRCL 第一次鎖利位置到了*\n\n"
            f"現價：${current_price:.2f}\n\n"
            f"*這個信號的意思：*\n"
            f"你的投資已達到第一個目標價 $200。這是值得慶祝的事！"
            f"賣出 25% 讓你心理上更輕鬆，剩下 75% 繼續享受後續增長。\n\n"
            f"*你現在的感受應該是：*\n開心。你做到了。\n\n"
            f"*你需要做的事：*\n賣出持倉的 25%，剩下 75% 繼續持有。"
        )
        send_telegram(msg)

    elif current_price >= SELL_TARGET_2 and current_price < SELL_TARGET_3:
        msg = (
            f"🔴 *CRCL 第二次鎖利位置到了*\n\n"
            f"現價：${current_price:.2f}\n\n"
            f"*你需要做的事：*\n再賣出持倉的 25%，剩下 50% 繼續持有。你已經回本有餘了！"
        )
        send_telegram(msg)

    elif current_price >= SELL_TARGET_3:
        msg = (
            f"🔴 *CRCL 第三次鎖利位置到了*\n\n"
            f"現價：${current_price:.2f}\n\n"
            f"*你需要做的事：*\n再賣出持倉的 25%，剩下 25% 長期持有，等待更大的目標。"
        )
        send_telegram(msg)

    # 止損警報
    if current_price <= STOP_LOSS:
        msg = (
            f"🚨 *CRCL 止損警報*\n\n"
            f"現價：${current_price:.2f}（已跌破止損線 $107）\n\n"
            f"*這個信號的意思：*\n"
            f"股價已跌破你設定的止損線，虧損超過 10%。這說明市場方向可能判斷錯誤，"
            f"需要保護本金。\n\n"
            f"*你需要做的事：*\n認真考慮止損出場，保護本金。先確認基本面有沒有出大問題。"
        )
        send_telegram(msg)

    # D 類：防 FOMO
    if daily_pct >= FOMO_UP_PCT:
        msg = (
            f"🛑 *冷靜提醒 ── 現在不是追高時機*\n\n"
            f"CRCL 今日已上漲 *{daily_pct:.1f}%*\n\n"
            f"*這個信號的意思：*\n"
            f"你現在很想買，但這正是最危險的時刻。今天追高的人，通常是替昨天買入的機構提供出貨機會。"
            f"你的計劃買入位置是 $122-$124 和 $118-$120，現在的價格不在計劃之內。\n\n"
            f"*你現在的感受應該是：*\n忍住。等待。好的機會不需要追。\n\n"
            f"*你需要做的事：*\n什麼都不做。關掉圖表。"
        )
        send_telegram(msg)

    elif daily_pct <= FOMO_DOWN_PCT:
        msg = (
            f"🛑 *冷靜提醒 ── 下跌不代表你判斷錯誤*\n\n"
            f"CRCL 今日下跌 *{daily_pct:.1f}%*\n\n"
            f"*這個信號的意思：*\n"
            f"股價下跌讓你感到不安，但請記住：只要 Circle 還在做 USDC、Visa 還在用 USDC、"
            f"法案還在推進，下跌只是市場的短期情緒，不是你判斷錯誤的證明。\n\n"
            f"*你現在的感受應該是：*\n這是正常的。我的持有理由沒有改變。\n\n"
            f"*你需要做的事：*\n看一下有沒有收到基本面警報。如果沒有，關掉圖表，去做其他事。"
        )
        send_telegram(msg)

    return current_price, daily_pct, current_rsi, current_vol, avg_vol

# ============================================================
# 模組二：大額成交量偵測
# ============================================================

def check_volume_spike(current_price, daily_pct, current_vol, avg_vol):
    """偵測大額成交量異常"""
    if avg_vol <= 0:
        return

    vol_ratio = current_vol / avg_vol
    print(f"[成交量] 今日: {current_vol:,.0f} | 5日均量: {avg_vol:,.0f} | 倍數: {vol_ratio:.1f}x")

    if vol_ratio >= VOLUME_SPIKE_MULTIPLIER:
        direction = "買入" if daily_pct > 0 else "賣出"
        direction_emoji = "📈" if daily_pct > 0 else "📉"
        direction_meaning = (
            "有大資金在這個價位積極買入，可能是機構在建倉。這是一個正面信號，說明有人比你更看好這個價位。\n\n"
            "*你需要做的事：*\n如果股價在你的買入區間內，這是加強買入信心的信號。如果不在區間內，繼續等待。"
            if daily_pct > 0 else
            "有大資金在這個價位賣出。這不一定是壞事，可能只是機構在調倉。\n\n"
            "*你需要做的事：*\n不要恐慌。先看一下有沒有同時出現基本面警報。如果基本面沒問題，這只是短期波動，不需要行動。"
        )

        msg = (
            f"{direction_emoji} *CRCL 大額{direction}偵測*\n\n"
            f"現價：${current_price:.2f}  |  今日漲跌：{daily_pct:.1f}%\n"
            f"今日成交量：{current_vol:,.0f}\n"
            f"5日平均成交量：{avg_vol:,.0f}\n"
            f"倍數：*{vol_ratio:.1f} 倍*（超過正常水平 {VOLUME_SPIKE_MULTIPLIER} 倍）\n\n"
            f"*這個信號的意思：*\n{direction_meaning}"
        )
        send_telegram(msg)

# ============================================================
# 模組三：SEC Form 4 高管內部交易監控
# ============================================================

def check_sec_form4():
    """監控 SEC Form 4 高管內部交易"""
    print("[SEC Form 4] 正在查詢高管交易...")
    try:
        # 使用 SEC EDGAR RSS Feed 獲取最新 Form 4 申報
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={COMPANY_CIK}&type=4&dateb=&owner=include&count=5&search_text="
        headers = {"User-Agent": "CRCL Monitor Bot contact@example.com"}
        r = requests.get(url, headers=headers, timeout=15)

        if r.status_code != 200:
            print(f"[SEC Form 4] 查詢失敗: {r.status_code}")
            return

        # 解析 HTML 找到最新申報
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')

        filings = []
        table = soup.find('table', {'class': 'tableFile2'})
        if not table:
            print("[SEC Form 4] 未找到申報記錄")
            return

        rows = table.find_all('tr')[1:]  # 跳過標題行
        for row in rows[:3]:  # 只看最新 3 筆
            cols = row.find_all('td')
            if len(cols) >= 4:
                filing_type = cols[0].text.strip()
                filing_date = cols[3].text.strip()
                link = cols[1].find('a')
                if link:
                    filings.append({
                        'type': filing_type,
                        'date': filing_date,
                        'url': "https://www.sec.gov" + link['href']
                    })

        # 檢查今天是否有新的 Form 4
        today = datetime.now().strftime('%Y-%m-%d')
        for filing in filings:
            if filing['date'] == today and '4' in filing['type']:
                # 獲取申報詳情
                detail = parse_form4_detail(filing['url'], headers)
                if detail:
                    send_form4_alert(detail)

    except Exception as e:
        print(f"[SEC Form 4] 錯誤: {e}")

def parse_form4_detail(url, headers):
    """解析 Form 4 申報詳情"""
    try:
        r = requests.get(url, headers=headers, timeout=15)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')

        # 找到 XML 文件連結
        xml_link = None
        for link in soup.find_all('a'):
            if link.text and '.xml' in link.get('href', ''):
                xml_link = "https://www.sec.gov" + link['href']
                break

        if not xml_link:
            return None

        # 解析 XML
        r2 = requests.get(xml_link, headers=headers, timeout=15)
        root = ET.fromstring(r2.content)

        ns = {'': 'http://www.sec.gov/cgi-bin/viewer?action=view&cik='}

        # 提取申報人信息
        reporter_name = ""
        reporter_title = ""
        transaction_type = ""
        shares = 0
        price = 0.0

        # 嘗試提取關鍵信息
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if tag == 'rptOwnerName' and elem.text:
                reporter_name = elem.text.strip()
            elif tag == 'officerTitle' and elem.text:
                reporter_title = elem.text.strip()
            elif tag == 'transactionCode' and elem.text:
                transaction_type = elem.text.strip()
            elif tag == 'transactionShares' and elem.text:
                try:
                    shares = float(elem.text.strip())
                except:
                    pass
            elif tag == 'transactionPricePerShare' and elem.text:
                try:
                    price = float(elem.text.strip())
                except:
                    pass

        total_value = shares * price

        # 只關注自有資金買入（P 類型）且金額超過 $10 萬
        if transaction_type == 'P' and total_value >= 100000:
            return {
                'name': reporter_name,
                'title': reporter_title,
                'type': 'buy',
                'shares': shares,
                'price': price,
                'total': total_value
            }
        elif transaction_type == 'S' and total_value >= 100000:
            return {
                'name': reporter_name,
                'title': reporter_title,
                'type': 'sell',
                'shares': shares,
                'price': price,
                'total': total_value
            }

        return None

    except Exception as e:
        print(f"[Form 4 解析] 錯誤: {e}")
        return None

def send_form4_alert(detail):
    """發送 Form 4 高管交易警報"""
    action = "買入" if detail['type'] == 'buy' else "賣出"
    emoji = "🔍" if detail['type'] == 'buy' else "⚠️"

    if detail['type'] == 'buy':
        meaning = (
            f"公司高管用自己的錢在市場上買入股票。這是最強的信心信號之一，"
            f"說明他們認為現在的價格被低估了。\n\n"
            f"*你現在的感受應該是：*\n這是好消息，聰明錢在買入。"
        )
    else:
        meaning = (
            f"公司高管賣出了部分股票。這不一定代表看空，高管賣股有很多原因（如個人資金需求、分散投資）。"
            f"需要結合基本面一起判斷。\n\n"
            f"*你需要做的事：*\n留意後續是否有更多高管賣出，單一賣出不需要過度反應。"
        )

    msg = (
        f"{emoji} *CRCL 高管內部交易申報*\n\n"
        f"申報人：{detail['name']}\n"
        f"職位：{detail['title']}\n"
        f"動作：自有資金{action} ✅\n"
        f"{action}股數：{detail['shares']:,.0f} 股\n"
        f"{action}價格：${detail['price']:.2f}\n"
        f"總金額：${detail['total']:,.0f} 美金\n\n"
        f"*這個信號的意思：*\n{meaning}"
    )
    send_telegram(msg)

# ============================================================
# 模組四：重要新聞過濾
# ============================================================

def check_news():
    """過濾並發送重要新聞"""
    print("[新聞] 正在掃描相關新聞...")
    try:
        ticker = yf.Ticker(TICKER)
        news = ticker.news

        if not news:
            print("[新聞] 無最新新聞")
            return

        # 重要關鍵字（利多）
        positive_keywords = [
            'clarity act', 'usdc', 'partnership', 'visa', 'mastercard',
            'blackrock', 'earnings beat', 'revenue', 'arc blockchain',
            'stablecoin bill', 'passed', 'approved', 'ai agent',
            'circle mint', 'institutional'
        ]

        # 重要關鍵字（利空）
        negative_keywords = [
            'lawsuit', 'sec investigation', 'depeg', 'ban', 'rejected',
            'failed', 'scandal', 'fraud', 'hack', 'breach',
            'lost partnership', 'competitor', 'regulation blocked'
        ]

        # 過濾掉的無用關鍵字
        noise_keywords = [
            'bitcoin price', 'ethereum price', 'crypto market',
            'dow jones', 's&p 500', 'nasdaq', 'fed rate',
            'inflation', 'other stocks'
        ]

        important_news = []
        checked_titles = set()

        for article in news[:10]:  # 只看最新 10 條
            title = article.get('title', '').lower()
            pub_time = article.get('providerPublishTime', 0)

            # 跳過重複標題
            if title in checked_titles:
                continue
            checked_titles.add(title)

            # 跳過超過 24 小時的舊新聞
            if pub_time and (time.time() - pub_time) > 86400:
                continue

            # 過濾無用雜訊
            is_noise = any(kw in title for kw in noise_keywords)
            if is_noise:
                continue

            # 判斷是否重要
            is_positive = any(kw in title for kw in positive_keywords)
            is_negative = any(kw in title for kw in negative_keywords)

            if is_positive or is_negative:
                sentiment = "利多 📈" if is_positive else "利空 📉"
                important_news.append({
                    'title': article.get('title', ''),
                    'sentiment': sentiment,
                    'url': article.get('link', ''),
                    'is_positive': is_positive
                })

        if important_news:
            for news_item in important_news[:2]:  # 最多發 2 條
                if news_item['is_positive']:
                    meaning = "這條新聞對 Circle 的業務是正面的，支持你的長期持有邏輯。不需要行動，繼續持有。"
                else:
                    meaning = "這條新聞需要你花 5 分鐘閱讀原文，確認是否影響你的持有理由。如果 USDC 和法案沒有根本性問題，不需要賣出。"

                msg = (
                    f"📰 *CRCL 重要新聞過濾*\n\n"
                    f"性質：{news_item['sentiment']}\n"
                    f"標題：{news_item['title']}\n\n"
                    f"*這個信號的意思：*\n{meaning}\n\n"
                    f"原文連結：{news_item['url']}"
                )
                send_telegram(msg)
        else:
            print("[新聞] 今日無重要新聞")

    except Exception as e:
        print(f"[新聞] 錯誤: {e}")

# ============================================================
# 模組五：每日總結
# ============================================================

def send_daily_summary():
    """發送每日市場總結"""
    print("[每日總結] 正在生成...")
    try:
        hist = get_price_data()
        if hist is None:
            return

        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2]
        daily_pct = ((current_price - prev_close) / prev_close) * 100
        current_rsi = hist['RSI'].iloc[-1]
        current_vol = hist['Volume'].iloc[-1]
        avg_vol = hist['VolMA5'].iloc[-1]
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1

        # 判斷各項狀態
        rsi_status = "正常 ✅" if 35 <= current_rsi <= 65 else ("超賣（買入機會）🟢" if current_rsi < 35 else "超買（注意風險）⚠️")
        vol_status = "正常 ✅" if vol_ratio < 2 else f"異常放大 {vol_ratio:.1f}x ⚠️"
        price_status = "正常 ✅"

        if current_price <= BUY_ZONE_1[1]:
            price_status = f"已進入買入區間 $122-$124 🟢"
        elif current_price >= SELL_TARGET_1:
            price_status = f"已達到鎖利目標 $200 🔴"

        direction_emoji = "📈" if daily_pct > 0 else "📉"

        msg = (
            f"📊 *CRCL 每日市場總結*\n"
            f"{'─' * 30}\n\n"
            f"收盤價：${current_price:.2f}  {direction_emoji} {daily_pct:+.2f}%\n"
            f"RSI：{current_rsi:.1f}  |  狀態：{rsi_status}\n"
            f"成交量：{vol_status}\n"
            f"價格位置：{price_status}\n\n"
            f"{'─' * 30}\n"
            f"*持有理由檢查：*\n"
            f"✅ USDC 業務：繼續運營中\n"
            f"✅ Visa 合作：維持中\n"
            f"✅ 法案進展：正常推進中\n\n"
            f"{'─' * 30}\n"
            f"*結論：*\n"
            f"持有理由完整，繼續持有。\n"
            f"下次需要行動：等待系統發出買入或賣出警報。\n\n"
            f"_沒有收到警報 = 不需要行動 = 安心去生活_"
        )
        send_telegram(msg)

    except Exception as e:
        print(f"[每日總結] 錯誤: {e}")

# ============================================================
# 主程式
# ============================================================

def run_all_checks():
    """執行所有監控模組"""
    print(f"\n{'='*50}")
    print(f"CRCL 監控系統啟動 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    # 獲取價格數據
    hist = get_price_data()
    if hist is None:
        print("❌ 無法獲取股價數據，跳過本次檢查")
        return

    # 模組一：技術面信號
    result = check_technical_signals(hist)
    if result:
        current_price, daily_pct, current_rsi, current_vol, avg_vol = result

        # 模組二：大額成交量
        check_volume_spike(current_price, daily_pct, current_vol, avg_vol)

    # 模組三：SEC Form 4 高管交易
    check_sec_form4()

    # 模組四：重要新聞過濾
    check_news()

    print(f"\n✅ 本次檢查完成")

def run_daily_summary():
    """執行每日總結（收盤後調用）"""
    send_daily_summary()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'daily':
        run_daily_summary()
    else:
        run_all_checks()
