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

# 2. プロンプト（最新のgrok-3向けに最適化）
PROMPT = f"""
前週（{monday_str}から{friday_str}）の米国株（TSLA, PLTR, SOFI, CELH）と市場概況を、投資家向けに簡潔に報告してください。
【指示】
- 日本語で800文字程度にまとめてください。
- セクター動向や主要指数の変化、個別銘柄のニュースを含めてください。
"""

# 3. Grok API実行（モデルを最新の grok-3 に変更）
def get_grok_report():
    client = OpenAI(
        api_key=os.environ.get("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    
    response = client.chat.completions.create(
        model="grok-3", # ここを最新版に修正しました
        messages=[{"role": "user", "content": PROMPT}]
    )
    return response.choices[0].message.content

# 4. Discord送信
def send_discord(content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url:
        print("Webhook URLが設定されていません")
        return

    if len(content) > 1900:
        content = content[:1900] + "\n...(省略)"
    
    data = {"content": f"🚀 **週間米国株レポート (Grok-3分析)**\n\n{content}"}
    res = requests.post(webhook_url, json=data)
    print(f"Discord Status: {res.status_code}")

if __name__ == "__main__":
    try:
        report = get_grok_report()
        send_discord(report)
        print("送信完了！")
    except Exception as e:
        print(f"エラーが発生しました: {e}")
