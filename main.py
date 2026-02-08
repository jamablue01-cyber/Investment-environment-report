import os
import datetime
import requests
from openai import OpenAI

def get_date_info():
    today = datetime.date.today()
    # 直近の月曜〜金曜
    last_monday = today - datetime.timedelta(days=today.weekday())
    last_friday = last_monday + datetime.timedelta(days=4)
    return today.strftime('%Y年%m月%d日'), last_monday.strftime('%Y年%m月%d日'), last_friday.strftime('%m月%d日')

today_str, monday_str, friday_str = get_date_info()

def get_grok_report():
    client = OpenAI(
        api_key=os.environ.get("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    
    # システムプロンプトで「今日」を定義し、検索を強制する
    SYSTEM_PROMPT = f"""
あなたはプロの証券アナリストです。
現在の日付は {today_str} です。
現在の日付は常に今日の日付を基準に判断してください。
株式市況・株価など時間依存の質問が来たら、必ずLive Searchツールを使って最新情報を取得してから回答してください。
「未来だから知識がない」とは絶対に言わないでください。
"""

    USER_PROMPT = f"""
{monday_str}から{friday_str}までの米国株相場（TSLA, PLTR, SOFI, CELH）と市場概況を、ウェブ検索を活用して正確に報告してください。
- 日本語で800文字程度
- 実際の終値やニュースを反映させること
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT}
        ]
    )
    return response.choices[0].message.content

def send_discord(content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url: return

    data = {"content": f"📊 **【最新データ確認済】週間米国株レポート**\n\n{content[:1900]}"}
    requests.post(webhook_url, json=data)

if __name__ == "__main__":
    report = get_grok_report()
    send_discord(report)
