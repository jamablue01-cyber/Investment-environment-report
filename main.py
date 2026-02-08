import os
import datetime
import requests
from openai import OpenAI

# 1. 日付の自動計算
def get_date_range():
    today = datetime.datetime.now()
    last_monday = today - datetime.timedelta(days=today.weekday() + 7)
    last_friday = last_monday + datetime.timedelta(days=4)
    return last_monday.strftime('%Y年%m月%d日'), last_friday.strftime('%m月%d日')

monday_str, friday_str = get_date_range()

# 2. プロンプト（短くまとめるように指示を追加）
PROMPT = f"""
前週（{monday_str}から{friday_str}）の米国株（TSLA, PLTR, SOFI, CELH）と市場概況を報告してください。
【重要ルール】
- 各項目を非常に簡潔にまとめてください。
- 全体の文字数は必ず「日本語で800文字以内」に収めてください。
- 箇条書きを多用してください。
"""

# 3. Grok API実行
def get_grok_report():
    client = OpenAI(
        api_key=os.environ.get("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    
    response = client.chat.completions.create(
        model="grok-2-1212", 
        messages=[{"role": "user", "content": PROMPT}]
    )
    return response.choices[0].message.content

# 4. Discord送信
def send_discord(content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    
    # 万が一文字数が多い場合は、Discordが拒否しないように強制カット
    if len(content) > 1900:
        content = content[:1900] + "\n...(制限のため省略)"
    
    data = {"content": f"🚀 **週間米国株レポート**\n\n{content}"}
    
    # 送信結果をログに出力するように変更
    res = requests.post(webhook_url, json=data)
    print(f"Discord Status Code: {res.status_code}")
    if res.status_code != 204:
        print(f"Error Response: {res.text}")

if __name__ == "__main__":
    report = get_grok_report()
    send_discord(report)
