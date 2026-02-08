import os
import datetime
import requests
from openai import OpenAI

def get_date_range():
    today = datetime.date.today()
    # 直近の月曜日を特定
    last_monday = today - datetime.timedelta(days=today.weekday())
    last_friday = last_monday + datetime.timedelta(days=4)
    return last_monday.strftime('%Y年%m月%d日'), last_friday.strftime('%m月%d日')

monday_str, friday_str = get_date_range()

# プロンプトを「検索強制モード」に大幅強化
PROMPT = f"""
あなたはプロの証券アナリストです。
【重要任務】
必ず最新のウェブ検索を行い、{monday_str}から{friday_str}までの実在する正確な市場データに基づき報告してください。

【報告内容】
1. 指数: S&P500, NASDAQ, SOX指数の週次騰落率（正確な％）。
2. 個別株: TSLA, PLTR, SOFI, CELH の直近の株価と、この1週間に起きた具体的なニュースや材料。
3. 展望: 来週の注目イベント。

【禁止事項】
- 架空の数値やニュースを絶対に創作しないでください。
- 検索結果が見つからない場合は「不明」と書いてください。
- 日本語で800文字程度で。
"""

def get_grok_report():
    client = OpenAI(
        api_key=os.environ.get("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    
    response = client.chat.completions.create(
        model="grok-3", # 最新の推論モデルを指定
        messages=[{"role": "user", "content": PROMPT}]
        # Grok-3は標準で検索能力が高いですが、プロンプトでさらに念押ししています
    )
    return response.choices[0].message.content

def send_discord(content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url: return

    data = {"content": f"📊 **【実データ確認版】週間米国株レポート**\n\n{content[:1900]}"}
    requests.post(webhook_url, json=data)

if __name__ == "__main__":
    report = get_grok_report()
    send_discord(report)
