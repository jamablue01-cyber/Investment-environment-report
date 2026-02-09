import os
import datetime
import requests
import time
from openai import OpenAI

def get_date_info():
    today = datetime.date.today()
    # 直近の月曜〜金曜（2/2〜2/6など）
    last_monday = today - datetime.timedelta(days=today.weekday())
    last_friday = last_monday + datetime.timedelta(days=4)
    # 前々週の月曜〜金曜
    prev_monday = last_monday - datetime.timedelta(days=7)
    prev_friday = prev_monday + datetime.timedelta(days=4)
    
    return {
        "today": today.strftime('%Y年%m月%d日'),
        "current_range": f"{last_monday.strftime('%m/%d')}〜{last_friday.strftime('%m/%d')}",
        "prev_range": f"{prev_monday.strftime('%m/%d')}〜{prev_friday.strftime('%m/%d')}"
    }

def get_grok_report(section_title, section_detail, date_info):
    client = OpenAI(
        api_key=os.environ.get("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    
    system_prompt = f"""
あなたはプロの米国株アナリストです。本日（{date_info['today']}）を基準に、必ずLive Searchツールを使用して最新情報を取得してください。
「未来だから知識がない」という回答は禁止です。
前週（{date_info['current_range']}）と前々週（{date_info['prev_range']}）を比較し、具体的数値（%や終値）を交えて分析してください。
各見解は1-2文で簡潔かつ鋭く述べてください。
"""

    user_prompt = f"""
【調査項目: {section_title}】
以下の詳細について調査し、報告してください：
{section_detail}

※信頼できるソース（Yahoo Finance, Bloomberg等）を使用し、事実に基づいたデータを提示してください。
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content

def send_discord(title, content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url: return

    # Discordの文字数制限対策（念のため）
    if len(content) > 1950:
        content = content[:1900] + "\n...(以下略)"

    data = {"content": f"### 📌 {title}\n{content}"}
    res = requests.post(webhook_url, json=data)
    print(f"Sent {title}: Status {res.status_code}")
    # 連投によるエラー（レート制限）を防ぐため少し待機
    time.sleep(1)

if __name__ == "__main__":
    dates = get_date_info()
    
    # 6つのセクションに分割
    sections = [
        ("1. 市場全体のパフォーマンスとトレンド", "主要指数(S&P500, DJIA, NASDAQ, Russell 2000)の週次変化と終値。主要セクターの騰落。市場ボリュームの変化。"),
        ("2. テクニカル指標と市場の健康度", "ヒンデンブルグオーメン、ディストリビューションデイ、フォロースルーデイの発生状況。新高値/安値数、VIXの変化。"),
        ("3. 金融政策とマクロ環境", "FRB政策予想（利下げ確率等）、10年債利回り、ドル指数(DXY)、商品価格(原油, 金, 銅)の変動。"),
        ("4. 経済指標とイベント", "重要指標(NFP, CPI, PPI等)の予想vs実績。主要企業の決算とガイダンス。地政学的リスク。"),
        ("5. センチメントと心理指標", "AAII、Fear & Greed Index、プット/コール比率、主要株のショートインタレスト。"),
        ("6. 主要投資対象（TSLA, PLTR, SOFI, CELH）と総括", "各銘柄の株価変化、関連ニュース、オプション活動、前々週比の勢い変化。最後に投資戦略への示唆を1段落で。")
    ]

    print(f"レポート作成開始: {dates['current_range']}")
    
    for title, detail in sections:
        try:
            report = get_grok_report(title, detail, dates)
            send_discord(title, report)
        except Exception as e:
            print(f"エラー発生 ({title}): {e}")

    print("全セクションの送信が完了しました。")
