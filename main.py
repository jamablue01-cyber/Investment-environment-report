import os
import datetime
import requests
from openai import OpenAI

# 1. 日付の自動計算（直近の月曜〜金曜を特定）
def get_date_range():
    today = datetime.date.today()
    # 今日が日曜(6)なら、6日前の月曜(0)を取得
    # これにより、日曜実行時に「その週の月曜〜金曜」を対象にします
    last_monday = today - datetime.timedelta(days=today.weekday())
    last_friday = last_monday + datetime.timedelta(days=4)
    return last_monday.strftime('%Y年%m月%d日'), last_friday.strftime('%m月%d日')

monday_str, friday_str = get_date_range()

# 2. プロンプト
PROMPT = f"""
{monday_str}から{friday_str}までの米国株相場（TSLA, PLTR, SOFI, CELH）と市場概況を報告してください。
【指示】
- 日本語で800文字程度
- 箇条書きを多用して簡潔に
- 主要指数の騰落、個別銘柄の重要ニュースを含めてください
"""

# 3. Grok API実行
def get_grok_report():
    client = OpenAI(
        api_key=os.environ.get("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    
    response = client.chat.completions.create(
        model="grok-3", 
        messages=[{"role": "user", "content": PROMPT}]
    )
    return response.choices[0].message.content

# 4. Discord送信
def send_discord(content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url: return

    data = {"content": f"🚀 **週間米国株レポート ({monday_str}〜{friday_str})**\n\n{content[:1900]}"}
    res = requests.post(webhook_url, json=data)
    print(f"Discord Status: {res.status_code}")

if __name__ == "__main__":
    report = get_grok_report()
    send_discord(report)
