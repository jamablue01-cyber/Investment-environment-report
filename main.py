import os
import datetime
import requests
import time
import yfinance as yf
from openai import OpenAI

def get_market_data():
    """
    yfinanceを使用して、実際の株価と騰落率を物理的に取得する。
    AIの嘘（ハルシネーション）を排除するための「真実のソース」。
    """
    # 調査対象の銘柄と指数
    tickers = {
        "PLTR": "Palantir",
        "TSLA": "Tesla",
        "SOFI": "SoFi",
        "CELH": "Celsius",
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ",
        "^DJI": "Dow Jones",
        "^RUT": "Russell 2000"
    }
    
    data_results = {}
    today = datetime.date.today()
    # 直近の完了した週（金曜終値）を計算
    end_date = today - datetime.timedelta(days=(today.weekday() + 2) % 7 + 1)
    start_date = end_date - datetime.timedelta(days=4)
    
    print(f"データ取得期間: {start_date} ～ {end_date}")

    for symbol, name in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            # 期間中のヒストリカルデータを取得
            hist = ticker.history(start=start_date, end=end_date + datetime.timedelta(days=1))
            if not hist.empty:
                close_start = hist['Close'].iloc[0]
                close_end = hist['Close'].iloc[-1]
                change = ((close_end - close_start) / close_start) * 100
                data_results[symbol] = {
                    "name": name,
                    "close": round(close_end, 2),
                    "change": round(change, 2),
                    "start": round(close_start, 2)
                }
            else:
                data_results[symbol] = "データなし"
        except Exception as e:
            data_results[symbol] = f"エラー: {e}"
    
    return data_results, start_date, end_date

def get_grok_report(section_title, section_detail, date_info, market_data):
    client = OpenAI(
        api_key=os.environ.get("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
        timeout=120.0,
    )
    
    # 物理的に取得した数値を文字列にする
    market_summary = "【確定市場データ】\n"
    for k, v in market_data.items():
        if isinstance(v, dict):
            market_summary += f"- {v['name']} ({k}): 終値 ${v['close']} (騰落率 {v['change']}%)\n"

    system_prompt = f"""
あなたはプロの米国株シニアアナリストです。本日（{date_info['today']}）を基準に執筆してください。
【鉄則】
1. 以下の「確定市場データ」は物理的な取引所データです。数値は1ミリも変えないでください。
2. あなたの仕事は、この「確定した数値（下落・上昇）」が、なぜ起きたのかをLive Searchで調査し、解説することです。
3. 数値がマイナスなのに「好調だった」などと書くことは、虚偽報告として厳禁します。
4. プロンプトにない「嘘の数字」は一切出さないでください。

{market_summary}
"""

    user_prompt = f"""
【分析対象期間: {date_info['current_range']}】
セクション: {section_title}
詳細要件: {section_detail}

※レポートはMarkdownで美しく装飾し、確定データを正確に反映した上で、具体的なニュース（日付・ソース）を添えてください。
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2 # 創作を防ぎ、事実に基づかせる
    )
    return response.choices[0].message.content

def send_discord(title, content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url: return
    header = f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n## 📝 {title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    # Discordの2000文字制限対策
    if len(header + content) > 2000:
        msg = (header + content)[:1990] + "..."
    else:
        msg = header + content
    requests.post(webhook_url, json={"content": msg})
    time.sleep(2)

if __name__ == "__main__":
    # 1. 物理データの取得
    raw_data, s_dt, e_dt = get_market_data()
    
    date_info = {
        "today": datetime.date.today().strftime('%Y年%m月%d日'),
        "current_range": f"{s_dt.strftime('%m/%d')}〜{e_dt.strftime('%m/%d')}"
    }

    # 2. レポートセクションの構築
    sections = [
        ("市場全体と指数の動向", "S&P500, NASDAQ, Dow, Russell 2000の確定値に基づき、なぜこの騰落になったのか背景を分析。"),
        ("主要銘柄(TSLA, PLTR, SOFI, CELH)の深掘り", "確定した4銘柄の株価に基づき、その週の重要ニュース、決算、材料、オプション活動をLive Searchで特定。")
    ]

    for title, detail in sections:
        try:
            print(f"生成中: {title}")
            report = get_grok_report(title, detail, date_info, raw_data)
            send_discord(title, report)
        except Exception as e:
            print(f"Error: {e}")

    print("完了しました。")
