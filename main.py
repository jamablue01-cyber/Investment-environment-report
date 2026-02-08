import os
import datetime
import requests
from openai import OpenAI

# 1. 日付の自動計算
def get_date_range():
    today = datetime.datetime.now()
    # 前週の月曜日と金曜日を特定
    last_monday = today - datetime.timedelta(days=today.weekday() + 7)
    last_friday = last_monday + datetime.timedelta(days=4)
    return last_monday.strftime('%Y年%m月%d日'), last_friday.strftime('%m月%d日')

monday_str, friday_str = get_date_range()

# 2. プロンプトの組み立て
PROMPT = f"""
私は米国株投資家で、主要投資対象はTSLA、PLTR、SOFI、CELHです。前週（{monday_str}から{friday_str}）とその前々週のNYSEとNASDAQの相場状況、金融環境をチェックしてください。以下の項目について、前々週との比較を交え、データを簡潔にまとめ、簡単な見解を加えて報告してください。

市場全体のパフォーマンスとトレンド:主要指数の週次変化（S&P 500, DJIA, NASDAQ Composite, Russell 2000のリターン率と終値変動）。セクター別パフォーマンス。
テクニカル指標と市場の健康度:ヒンデンブルグオーメン、ディストリビューションデイ、VIXの変化。
金融政策とマクロ環境:FRB金融政策予想、10年物米国債利回り、米ドル指数DXYの変化。
主要投資対象銘柄（TSLA, PLTR, SOFI, CELH）の週次まとめ:各銘柄の株価変化、関連ニュース、前々週比の勢い変化。
全体の見解として、特にTSLA/PLTR/SOFI/CELHへの投資戦略への示唆を述べてください。
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
    # Secretsの名前に合わせて DISCORD_WEB_HOOK にしています
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    
    if len(content) > 1900:
        content = content[:1900] + "\n...(省略)"
    
    data = {"content": f"🚀 **週間米国株レポート ({monday_str}〜)**\n\n{content}"}
    requests.post(webhook_url, json=data)

if __name__ == "__main__":
    try:
        report = get_grok_report()
        send_discord(report)
        print("Done!")
    except Exception as e:
        print(f"Error: {e}")
