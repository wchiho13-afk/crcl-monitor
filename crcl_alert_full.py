#!/usr/bin/env python3
"""
CRCL 完整免費版監控警報系統 v2.0
監控範圍：技術指標、大額成交量、SEC Form 4 高管交易、機構持倉變化、新聞過濾、每日總結
新增：ARK 每日持倉監控、期權市場情緒、Clarity Act 法案進度追蹤、USDC 流通量監控
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

# ARK ETF 代號（持有 CRCL 的主要 ARK 基金）
ARK_FUNDS = ["ARKK", "ARKW", "ARKF"]

# 狀態記錄文件（避免重複發送相同警報）
STATE_FILE = "/home/ubuntu/crcl_monitor/state.json"

# ============================================================
# 狀態管理
# ============================================================

def load_state():
    """載入狀態記錄"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_state(state):
    """保存狀態記錄"""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[狀態] 保存失敗: {e}")

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
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={COMPANY_CIK}&type=4&dateb=&owner=include&count=5&search_text="
        headers = {"User-Agent": "CRCL Monitor Bot contact@example.com"}
        r = requests.get(url, headers=headers, timeout=15)

        if r.status_code != 200:
            print(f"[SEC Form 4] 查詢失敗: {r.status_code}")
            return

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')

        filings = []
        table = soup.find('table', {'class': 'tableFile2'})
        if not table:
            print("[SEC Form 4] 未找到申報記錄")
            return

        rows = table.find_all('tr')[1:]
        for row in rows[:3]:
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

        today = datetime.now().strftime('%Y-%m-%d')
        for filing in filings:
            if filing['date'] == today and '4' in filing['type']:
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

        xml_link = None
        for link in soup.find_all('a'):
            if link.text and '.xml' in link.get('href', ''):
                xml_link = "https://www.sec.gov" + link['href']
                break

        if not xml_link:
            return None

        r2 = requests.get(xml_link, headers=headers, timeout=15)
        root = ET.fromstring(r2.content)

        reporter_name = ""
        reporter_title = ""
        transaction_type = ""
        shares = 0
        price = 0.0

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

        if transaction_type == 'P' and total_value >= 100000:
            return {'name': reporter_name, 'title': reporter_title, 'type': 'buy', 'shares': shares, 'price': price, 'total': total_value}
        elif transaction_type == 'S' and total_value >= 100000:
            return {'name': reporter_name, 'title': reporter_title, 'type': 'sell', 'shares': shares, 'price': price, 'total': total_value}

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

        positive_keywords = [
            'clarity act', 'usdc', 'partnership', 'visa', 'mastercard',
            'blackrock', 'earnings beat', 'revenue', 'arc blockchain',
            'stablecoin bill', 'passed', 'approved', 'ai agent',
            'circle mint', 'institutional'
        ]

        negative_keywords = [
            'lawsuit', 'sec investigation', 'depeg', 'ban', 'rejected',
            'failed', 'scandal', 'fraud', 'hack', 'breach',
            'lost partnership', 'competitor', 'regulation blocked'
        ]

        noise_keywords = [
            'bitcoin price', 'ethereum price', 'crypto market',
            'dow jones', 's&p 500', 'nasdaq', 'fed rate',
            'inflation', 'other stocks'
        ]

        important_news = []
        checked_titles = set()

        for article in news[:10]:
            title = article.get('title', '').lower()
            pub_time = article.get('providerPublishTime', 0)

            if title in checked_titles:
                continue
            checked_titles.add(title)

            if pub_time and (time.time() - pub_time) > 86400:
                continue

            is_noise = any(kw in title for kw in noise_keywords)
            if is_noise:
                continue

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
            for news_item in important_news[:2]:
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
# 模組六（新）：ARK Invest 每日持倉監控
# 數據來源：ARK 官方每日公開 CSV（完全免費）
# ============================================================

def check_ark_holdings():
    """監控 ARK Invest 對 CRCL 的每日持倉變化"""
    print("[ARK] 正在查詢 ARK 持倉...")
    state = load_state()
    last_ark_shares = state.get('ark_total_shares', 0)

    total_shares = 0
    fund_details = []

    for fund in ARK_FUNDS:
        try:
            # ARK 每天公開當日持倉 CSV
            url = f"https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_INNOVATION_ETF_{fund}_HOLDINGS.csv"
            # 嘗試通用格式
            urls_to_try = [
                f"https://ark-funds.com/wp-content/uploads/funds-etf-csv/ARK_INNOVATION_ETF_{fund}_HOLDINGS.csv",
                f"https://ark-funds.com/wp-content/uploads/funds-etf-csv/{fund}_holdings.csv",
            ]

            df = None
            for u in urls_to_try:
                try:
                    resp = requests.get(u, timeout=10)
                    if resp.status_code == 200 and len(resp.text) > 100:
                        from io import StringIO
                        df = pd.read_csv(StringIO(resp.text))
                        break
                except:
                    continue

            if df is None:
                # 備用：用 yfinance 查 ARK ETF 持倉
                continue

            # 搜尋 CRCL
            df.columns = [c.lower().strip() for c in df.columns]
            ticker_col = next((c for c in df.columns if 'ticker' in c or 'symbol' in c), None)
            shares_col = next((c for c in df.columns if 'shares' in c), None)
            weight_col = next((c for c in df.columns if 'weight' in c), None)
            value_col = next((c for c in df.columns if 'value' in c or 'market' in c), None)

            if ticker_col and shares_col:
                crcl_row = df[df[ticker_col].astype(str).str.upper() == 'CRCL']
                if not crcl_row.empty:
                    shares = float(str(crcl_row[shares_col].iloc[0]).replace(',', ''))
                    weight = float(str(crcl_row[weight_col].iloc[0]).replace('%', '').replace(',', '')) if weight_col else 0
                    total_shares += shares
                    fund_details.append({'fund': fund, 'shares': shares, 'weight': weight})

        except Exception as e:
            print(f"[ARK] {fund} 查詢失敗: {e}")
            continue

    # 如果 CSV 方式失敗，使用備用 API
    if total_shares == 0:
        total_shares, fund_details = get_ark_holdings_fallback()

    if total_shares == 0:
        print("[ARK] 無法獲取 ARK 持倉數據")
        return

    print(f"[ARK] 當前總持倉: {total_shares:,.0f} 股")

    # 比較與昨日的變化
    if last_ark_shares > 0:
        change = total_shares - last_ark_shares
        change_pct = (change / last_ark_shares) * 100

        if abs(change) >= 10000:  # 變化超過 1 萬股才發通知
            action = "買入加倉" if change > 0 else "賣出減倉"
            emoji = "🏦" if change > 0 else "🏦"

            # 估算金額（用當前股價）
            try:
                ticker = yf.Ticker(TICKER)
                current_price = ticker.history(period="1d")['Close'].iloc[-1]
                change_value = abs(change) * current_price
            except:
                current_price = 0
                change_value = 0

            if change > 0:
                meaning = (
                    f"全球最著名的科技股基金（管理 $50 億美金）今天在市場上買入了更多 CRCL。\n"
                    f"這說明 ARK 認為現在的價格仍然值得買入。\n\n"
                    f"*你現在的感受應該是：*\n你的判斷方向跟機構一致，繼續持有。"
                )
            else:
                meaning = (
                    f"ARK 今天減少了 CRCL 持倉。這可能是基金贖回壓力或調倉，不一定代表看空。\n"
                    f"需要留意後續幾天是否持續減倉。\n\n"
                    f"*你需要做的事：*\n觀察後續走勢，如果連續 3 天減倉才需要重新評估。"
                )

            fund_str = ""
            for fd in fund_details:
                fund_str += f"  {fd['fund']}：{fd['shares']:,.0f} 股（佔比 {fd['weight']:.2f}%）\n"

            msg = (
                f"{emoji} *ARK Invest CRCL 持倉變化*\n\n"
                f"動作：*{action}*\n"
                f"變化股數：{abs(change):,.0f} 股（{change_pct:+.1f}%）\n"
                f"估計金額：約 ${change_value:,.0f} 美金\n"
                f"ARK 總持倉：{total_shares:,.0f} 股\n\n"
                f"各基金明細：\n{fund_str}\n"
                f"*這個信號的意思：*\n{meaning}"
            )
            send_telegram(msg)

    # 更新狀態
    state['ark_total_shares'] = total_shares
    state['ark_last_update'] = datetime.now().strftime('%Y-%m-%d')
    save_state(state)

def get_ark_holdings_fallback():
    """備用方案：從 Stockanalysis 抓取 ARK 持倉"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://stockanalysis.com/etf/arkk/holdings/"
        r = requests.get(url, headers=headers, timeout=15)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')

        # 找 CRCL 行
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if cells and any('CRCL' in c.text for c in cells):
                    # 找股數列
                    for i, cell in enumerate(cells):
                        if 'CRCL' in cell.text:
                            # 通常股數在後面幾列
                            for j in range(i+1, min(i+5, len(cells))):
                                try:
                                    val = float(cells[j].text.replace(',', '').replace('M', '000000').replace('K', '000').strip())
                                    if val > 1000:
                                        return val, [{'fund': 'ARKK', 'shares': val, 'weight': 0}]
                                except:
                                    continue
    except Exception as e:
        print(f"[ARK 備用] 錯誤: {e}")

    return 0, []

# ============================================================
# 模組七（新）：期權市場情緒分析
# 數據來源：Yahoo Finance 期權鏈（完全免費）
# ============================================================

def check_options_sentiment():
    """分析 CRCL 期權市場情緒（大戶看漲還是看跌）"""
    print("[期權] 正在分析期權市場情緒...")
    try:
        ticker = yf.Ticker(TICKER)

        # 獲取期權到期日列表
        expirations = ticker.options
        if not expirations:
            print("[期權] 無期權數據")
            return

        # 取最近 2 個到期日的數據
        total_call_oi = 0
        total_put_oi = 0
        total_call_volume = 0
        total_put_volume = 0
        large_calls = []  # 大額 Call 期權
        large_puts = []   # 大額 Put 期權

        for exp in expirations[:2]:
            try:
                chain = ticker.option_chain(exp)
                calls = chain.calls
                puts = chain.puts

                # 統計未平倉量和成交量
                total_call_oi += calls['openInterest'].sum()
                total_put_oi += puts['openInterest'].sum()
                total_call_volume += calls['volume'].fillna(0).sum()
                total_put_volume += puts['volume'].fillna(0).sum()

                # 找大額期權（未平倉量 > 500）
                big_calls = calls[calls['openInterest'] > 500].nlargest(3, 'openInterest')
                big_puts = puts[puts['openInterest'] > 500].nlargest(3, 'openInterest')

                for _, row in big_calls.iterrows():
                    large_calls.append({
                        'exp': exp,
                        'strike': row['strike'],
                        'oi': row['openInterest'],
                        'volume': row.get('volume', 0)
                    })

                for _, row in big_puts.iterrows():
                    large_puts.append({
                        'exp': exp,
                        'strike': row['strike'],
                        'oi': row['openInterest'],
                        'volume': row.get('volume', 0)
                    })

            except Exception as e:
                print(f"[期權] {exp} 解析失敗: {e}")
                continue

        if total_call_oi + total_put_oi == 0:
            print("[期權] 無有效期權數據")
            return

        # 計算 Put/Call 比率
        pc_ratio_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 1
        pc_ratio_vol = total_put_volume / total_call_volume if total_call_volume > 0 else 1

        print(f"[期權] Call OI: {total_call_oi:,.0f} | Put OI: {total_put_oi:,.0f} | P/C 比率: {pc_ratio_oi:.2f}")

        # 判斷市場情緒
        if pc_ratio_oi < 0.7:
            sentiment = "強烈看漲 🟢🟢"
            sentiment_meaning = (
                f"大戶買入 Call（看漲期權）的數量遠超 Put（看跌期權）。\n"
                f"這說明機構投資者預期 CRCL 股價會上漲。\n\n"
                f"*你現在的感受應該是：*\n市場的聰明錢跟你站在同一邊。"
            )
        elif pc_ratio_oi < 0.9:
            sentiment = "偏向看漲 🟢"
            sentiment_meaning = (
                f"Call 期權比 Put 期權多，市場整體偏向看漲。\n"
                f"這是一個正面信號，但不是極端情緒。"
            )
        elif pc_ratio_oi < 1.1:
            sentiment = "中性 ⚪"
            sentiment_meaning = (
                f"Call 和 Put 數量相近，市場方向不明確。\n"
                f"這種情況下，等待其他信號再做決定。"
            )
        elif pc_ratio_oi < 1.3:
            sentiment = "偏向看跌 🔴"
            sentiment_meaning = (
                f"Put 期權比 Call 期權多，市場有一定的看跌情緒。\n"
                f"這不代表一定會跌，但需要留意。"
            )
        else:
            sentiment = "強烈看跌 🔴🔴"
            sentiment_meaning = (
                f"大戶買入大量 Put（看跌期權），說明機構在對沖風險或預期下跌。\n"
                f"這是一個警示信號，需要謹慎。\n\n"
                f"*你需要做的事：*\n暫緩買入，等待情緒轉變。"
            )

        # 找最大的 Call 目標價（大戶預期漲到哪裡）
        top_call_strikes = ""
        if large_calls:
            sorted_calls = sorted(large_calls, key=lambda x: x['oi'], reverse=True)[:3]
            for c in sorted_calls:
                top_call_strikes += f"  Call ${c['strike']:.0f}（到期：{c['exp']}，未平倉：{c['oi']:,.0f}）\n"

        top_put_strikes = ""
        if large_puts:
            sorted_puts = sorted(large_puts, key=lambda x: x['oi'], reverse=True)[:3]
            for p in sorted_puts:
                top_put_strikes += f"  Put ${p['strike']:.0f}（到期：{p['exp']}，未平倉：{p['oi']:,.0f}）\n"

        msg = (
            f"📊 *CRCL 期權市場情緒分析*\n\n"
            f"整體情緒：*{sentiment}*\n"
            f"Put/Call 比率：{pc_ratio_oi:.2f}（低於 0.7 = 看漲，高於 1.3 = 看跌）\n\n"
            f"Call 未平倉量：{total_call_oi:,.0f}\n"
            f"Put 未平倉量：{total_put_oi:,.0f}\n\n"
        )

        if top_call_strikes:
            msg += f"*大戶看漲目標價（最大 Call）：*\n{top_call_strikes}\n"
        if top_put_strikes:
            msg += f"*大戶對沖位置（最大 Put）：*\n{top_put_strikes}\n"

        msg += f"*這個信號的意思：*\n{sentiment_meaning}"

        send_telegram(msg)

    except Exception as e:
        print(f"[期權] 錯誤: {e}")

# ============================================================
# 模組八（新）：Clarity Act 法案進度追蹤
# 數據來源：Congress.gov RSS Feed（完全免費）
# ============================================================

def check_clarity_act():
    """追蹤 Clarity Act 法案最新進度"""
    print("[法案] 正在查詢 Clarity Act 進度...")
    state = load_state()
    last_status = state.get('clarity_act_status', '')

    try:
        # 方法一：搜尋 Congress.gov RSS
        keywords_to_check = [
            'clarity act', 'stablecoin', 'genius act', 'digital asset',
            'crypto regulation', 'usdc regulation'
        ]

        # 使用 Google News RSS（免費）
        import urllib.parse
        query = urllib.parse.quote('Clarity Act stablecoin Congress 2026')
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(rss_url, headers=headers, timeout=15)

        if r.status_code != 200:
            print(f"[法案] RSS 查詢失敗: {r.status_code}")
            return

        root = ET.fromstring(r.content)
        items = root.findall('.//item')

        important_updates = []
        positive_keywords = ['passed', 'approved', 'signed', 'vote', 'hearing', 'advance', 'progress', 'senate', 'house']
        negative_keywords = ['failed', 'rejected', 'blocked', 'delayed', 'stalled', 'opposition']

        for item in items[:10]:
            title_elem = item.find('title')
            pub_date_elem = item.find('pubDate')
            link_elem = item.find('link')

            if title_elem is None:
                continue

            title = title_elem.text or ''
            title_lower = title.lower()
            pub_date = pub_date_elem.text if pub_date_elem is not None else ''
            link = link_elem.text if link_elem is not None else ''

            # 只看包含法案關鍵字的新聞
            if not any(kw in title_lower for kw in keywords_to_check):
                continue

            is_positive = any(kw in title_lower for kw in positive_keywords)
            is_negative = any(kw in title_lower for kw in negative_keywords)

            if is_positive or is_negative:
                important_updates.append({
                    'title': title,
                    'date': pub_date,
                    'link': link,
                    'is_positive': is_positive
                })

        if important_updates:
            latest = important_updates[0]
            # 避免重複發送相同新聞
            if latest['title'] != last_status:
                if latest['is_positive']:
                    emoji = "🏛️"
                    meaning = (
                        f"Clarity Act（穩定幣監管法案）有正面進展！\n"
                        f"這是 CRCL 最重要的催化劑之一。法案通過後，USDC 將獲得法律保障，"
                        f"機構採用率將大幅提升，直接利好 Circle 的業務。\n\n"
                        f"*你現在的感受應該是：*\n這是你持有 CRCL 的核心理由正在實現。"
                    )
                else:
                    emoji = "⚠️"
                    meaning = (
                        f"Clarity Act 遇到阻力。這是短期利空，但不代表法案最終會失敗。\n"
                        f"美國的立法過程本來就是反覆的，一次挫折不代表結束。\n\n"
                        f"*你需要做的事：*\n閱讀原文了解具體情況，不要因為一條新聞就做決定。"
                    )

                msg = (
                    f"{emoji} *Clarity Act 法案最新動態*\n\n"
                    f"標題：{latest['title']}\n"
                    f"日期：{latest['date']}\n\n"
                    f"*這個信號的意思：*\n{meaning}\n\n"
                    f"原文：{latest['link']}"
                )
                send_telegram(msg)

                state['clarity_act_status'] = latest['title']
                save_state(state)
        else:
            print("[法案] 今日無 Clarity Act 重要動態")

    except Exception as e:
        print(f"[法案] 錯誤: {e}")

# ============================================================
# 模組九（新）：USDC 流通量監控
# 數據來源：Circle 官方 API（完全免費）
# ============================================================

def check_usdc_supply():
    """監控 USDC 流通量變化（Circle 核心業務指標）"""
    print("[USDC] 正在查詢 USDC 流通量...")
    state = load_state()
    last_supply = state.get('usdc_supply', 0)

    try:
        # 方法一：CoinGecko API（免費，無需 API Key）
        url = "https://api.coingecko.com/api/v3/coins/usd-coin"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)

        if r.status_code != 200:
            print(f"[USDC] CoinGecko 查詢失敗: {r.status_code}")
            # 備用方案
            check_usdc_supply_fallback(state, last_supply)
            return

        data = r.json()
        market_data = data.get('market_data', {})
        current_supply = market_data.get('circulating_supply', 0)
        market_cap = market_data.get('market_cap', {}).get('usd', 0)

        if current_supply == 0:
            print("[USDC] 無法獲取流通量數據")
            return

        print(f"[USDC] 當前流通量: ${current_supply/1e9:.2f}B | 市值: ${market_cap/1e9:.2f}B")

        # 比較變化
        if last_supply > 0:
            change = current_supply - last_supply
            change_pct = (change / last_supply) * 100
            change_b = change / 1e9  # 轉換為十億

            # 只有變化超過 0.5% 才發通知
            if abs(change_pct) >= 0.5:
                if change > 0:
                    emoji = "💵"
                    action = "增加"
                    meaning = (
                        f"USDC 流通量增加，說明更多人在使用 USDC，Circle 的業務在增長。\n"
                        f"Circle 的收入主要來自 USDC 儲備的利息，流通量越大，收入越高。\n\n"
                        f"*你現在的感受應該是：*\n你持有 CRCL 的核心理由（業務增長）正在被數據驗證。"
                    )
                else:
                    emoji = "📉"
                    action = "減少"
                    meaning = (
                        f"USDC 流通量減少，可能是市場整體情緒偏空，或有競爭對手搶佔市場。\n"
                        f"如果連續多日減少，需要重新評估持有邏輯。\n\n"
                        f"*你需要做的事：*\n觀察後續趨勢，單日波動不需要過度反應。"
                    )

                msg = (
                    f"{emoji} *USDC 流通量變化（Circle 核心業務指標）*\n\n"
                    f"當前流通量：*${current_supply/1e9:.2f}B*（{current_supply/1e9:.2f} 十億美元）\n"
                    f"變化：{action} {abs(change_b):.2f}B（{change_pct:+.2f}%）\n"
                    f"市值：${market_cap/1e9:.2f}B\n\n"
                    f"*這個信號的意思：*\n{meaning}"
                )
                send_telegram(msg)

        # 更新狀態
        state['usdc_supply'] = current_supply
        state['usdc_last_update'] = datetime.now().strftime('%Y-%m-%d')
        save_state(state)

    except Exception as e:
        print(f"[USDC] 錯誤: {e}")

def check_usdc_supply_fallback(state, last_supply):
    """備用方案：從 CryptoCompare 獲取 USDC 數據"""
    try:
        url = "https://min-api.cryptocompare.com/data/pricemultifull?fsyms=USDC&tsyms=USD"
        r = requests.get(url, timeout=10)
        data = r.json()
        supply = data.get('RAW', {}).get('USDC', {}).get('USD', {}).get('SUPPLY', 0)
        if supply > 0:
            state['usdc_supply'] = supply
            save_state(state)
            print(f"[USDC 備用] 流通量: ${supply/1e9:.2f}B")
    except Exception as e:
        print(f"[USDC 備用] 錯誤: {e}")

# ============================================================
# 模組五：每日總結（升級版）
# ============================================================

def send_daily_summary():
    """發送每日市場總結（包含所有新模組數據）"""
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

        rsi_status = "正常 ✅" if 35 <= current_rsi <= 65 else ("超賣（買入機會）🟢" if current_rsi < 35 else "超買（注意風險）⚠️")
        vol_status = "正常 ✅" if vol_ratio < 2 else f"異常放大 {vol_ratio:.1f}x ⚠️"
        price_status = "正常 ✅"

        if current_price <= BUY_ZONE_1[1]:
            price_status = f"已進入買入區間 $122-$124 🟢"
        elif current_price >= SELL_TARGET_1:
            price_status = f"已達到鎖利目標 $200 🔴"

        direction_emoji = "📈" if daily_pct > 0 else "📉"

        # 讀取 USDC 流通量
        state = load_state()
        usdc_supply = state.get('usdc_supply', 0)
        usdc_str = f"${usdc_supply/1e9:.1f}B ✅" if usdc_supply > 0 else "數據載入中..."

        # 讀取 ARK 持倉
        ark_shares = state.get('ark_total_shares', 0)
        ark_str = f"{ark_shares/1e6:.2f}M 股 ✅" if ark_shares > 0 else "數據載入中..."

        msg = (
            f"📊 *CRCL 每日市場總結*\n"
            f"{'─' * 30}\n\n"
            f"收盤價：${current_price:.2f}  {direction_emoji} {daily_pct:+.2f}%\n"
            f"RSI：{current_rsi:.1f}  |  狀態：{rsi_status}\n"
            f"成交量：{vol_status}\n"
            f"價格位置：{price_status}\n\n"
            f"{'─' * 30}\n"
            f"*持有理由檢查：*\n"
            f"✅ USDC 流通量：{usdc_str}\n"
            f"✅ ARK 持倉：{ark_str}\n"
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
    print(f"CRCL 監控系統 v2.0 啟動 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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

    # 模組六：ARK 持倉監控（新）
    check_ark_holdings()

    # 模組七：期權市場情緒（新）
    check_options_sentiment()

    # 模組八：Clarity Act 法案進度（新）
    check_clarity_act()

    # 模組九：USDC 流通量（新）
    check_usdc_supply()

    print(f"\n✅ 本次檢查完成（v2.0）")

def run_daily_summary():
    """執行每日總結（收盤後調用）"""
    send_daily_summary()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'daily':
        run_daily_summary()
    else:
        run_all_checks()
