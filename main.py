import os
import datetime
import requests
from openai import OpenAI

def get_date_range():
    today = datetime.datetime.now()
    last_monday = today - datetime.timedelta(days=today.weekday() + 7)
    last_friday = last_monday + datetime.timedelta(days=4)
    return last_monday.strftime('%Y年%m月%d日'), last_friday.strftime('%m月%d日')

monday_str, friday_str = get_date_range()

PROMPT = f"""
前週（{monday_str}から{friday_str}）の米国株（TSLA, PLTR, SOFI, CELH）と市場概況を報告してください。
- 日本語で800文字程度
- 箇条書きを多用して簡潔に
"""

def get_grok_report():
    client = OpenAI(
        api_key=os.environ.get("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    
    # ログの指示通り、grok-3 を指定します
    response = client.chat.completions.create(
        model="grok-3", 
        messages=[{"role": "user", "content": PROMPT}]
    )
    return response.choices[0].message.content

def send_discord(content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url: return

    data = {"content": f"🚀 **週間米国株レポート**\n\n{content[:1900]}"}
    res = requests.post(webhook_url, json=data)
    print(f"Discord Status: {res.status_code}")

if __name__ == "__main__":
    report = get_grok_report()
    send_discord(report)
