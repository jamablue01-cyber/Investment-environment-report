import os
import datetime
import requests
import time
from openai import OpenAI

def get_date_info():
    today = datetime.date.today()
    # 直近の月曜〜金曜
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
あなたはプロの米国株シニアアナリストです。
現在の日付は {date_info['today']} です。
【報告の鉄則】
1. 必ずLive Searchツールを使用して、最新の市場データ・株価・ニュースを取得してください。
2. 「未来だからわからない」という回答は厳禁。{date_info['current_range']} の出来事を「現在進行系」または「直近の過去」として分析してください。
3. 文体は「プロの市場リポート」として、Markdown（太字、箇条書き、引用ブロック）を多用して美しく整理してください。
4. 数値データ（％や価格）を必ず含めてください。
"""

    user_prompt = f"""
【今回の調査範囲: {section_title}】
以下の項目について、前週（{date_info['current_range']}）と前々週（{date_info['prev_range']}）を徹底比較してください：
{section_detail}

※出力は適切な改行を入れ、読みやすくしてください。
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

    # ヘッダーを装飾して視認性を向上
    header = f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n## 📂 {title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    full_content = header + content

    # Discordの2000文字制限対策（念のため分割して送る処理を追加）
    if len(full_content) > 2000:
        # 1900文字で切って、残りは別メッセージにする（安全策）
        msg1 = full_content[:1950] + "\n...(続く)"
        requests.post(webhook_url, json={"content": msg1})
        time.sleep(1)
        msg2 = "👉 (続き)\n" + full_content[1950:]
        requests.post(webhook_url, json={"content": msg2})
    else:
        requests.post(webhook_url, json={"content": full_content})
    
    print(f"Sent: {title}")
    time.sleep(1.5) # レート制限回避のため少し長めに待機

if __name__ == "__main__":
    dates = get_date_info()
    
    sections = [
        ("1. 市場全体のパフォーマンスとトレンド", "S&P500, DJIA, NASDAQ, Russell 2000の週次騰落。セクター別パフォーマンス、取引量の変化。"),
        ("2. テクニカル指標と市場の健康度", "ヒンデンブルグオーメン、ディストリビューションデイ、フォロースルーデイ、新高値/安値、VIX指数。"),
        ("3. 金融政策とマクロ環境", "FRB政策予想（FedWatch）、10年債利回り、DXY(ドル指数)、原油・金・銅の動向。"),
        ("4. 経済指標とイベント", "雇用統計、CPI、PPI等の実績。主要企業の決算ハイライト。地政学的リスク。"),
        ("5. センチメントと心理指標", "AAII、Fear & Greed Index、プットコール比率、ショートインタレスト。"),
        ("6. 主要銘柄（TSLA, PLTR, SOFI, CELH）分析 ＆ 総括", "4銘柄の株価・ニュース・オプション活動。最後に週のまとめと投資戦略の示唆。")
    ]

    for title, detail in sections:
        try:
            report = get_grok_report(title, detail, dates)
            send_discord(title, report)
        except Exception as e:
            print(f"Error in {title}: {e}")

    print("完了！")
