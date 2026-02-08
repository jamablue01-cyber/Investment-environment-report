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

# 2. プロンプト
PROMPT = f"""
前週（{monday_str}から{friday_str}）の米国株（TSLA, PLTR, SOFI, CELH）と市場概況を報告してください。
- 日本語で800文字程度
- 箇条書きを多用して簡潔に
"""

# 3. Grok API実行
def get_grok_report():
    print("AIレポートを作成中...")
    client = OpenAI(
        api_key=os.environ.get("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    
    # モデル名を「grok-beta」に。これで最新のGrok 4.x系が自動選択されます。
    response = client.chat.completions.create(
        model="grok-beta", 
        messages=[{"role": "user", "content": PROMPT}]
    )
    return response.choices[0].message.content

# 4. Discord送信
def send_discord(content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url:
        raise ValueError("DISCORD_WEB_HOOK が設定されていません")

    data = {"content": f"🚀 **週間米国株レポート (Grok最新版)**\n\n{content[:1900]}"}
    res = requests.post(webhook_url, json=data)
    print(f"Discordステータス: {res.status_code}")
    if res.status_code != 204:
        print(f"送信失敗の詳細: {res.text}")

if __name__ == "__main__":
    # あえて try-except を外しました。エラーがあればログに赤字で表示されます。
    report = get_grok_report()
    send_discord(report)
    print("すべて完了しました！")
