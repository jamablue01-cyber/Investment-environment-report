import os
import datetime
import requests
import time
from openai import OpenAI

def get_date_info():
    today = datetime.date.today()
    # 直近完了した週（月〜金）を基準にする
    # 今日が月曜なら先週、火〜日なら先週の週を対象
    days_since_monday = today.weekday()
    last_monday = today - datetime.timedelta(days=days_since_monday)
    last_friday = last_monday + datetime.timedelta(days=4)
    
    # 前週
    prev_monday = last_monday - datetime.timedelta(days=7)
    prev_friday = prev_monday + datetime.timedelta(days=4)
    
    return {
        "today": today.strftime('%Y年%m月%d日'),
        "current_range": f"{last_monday.strftime('%m/%d')}〜{last_friday.strftime('%m/%d')}",
        "prev_range": f"{prev_monday.strftime('%m/%d')}〜{prev_friday.strftime('%m/%d')}",
        "current_start": last_monday.strftime('%Y-%m-%d'),
        "current_end": last_friday.strftime('%Y-%m-%d'),
    }

def get_grok_report(section_title, section_detail, date_info):
    client = OpenAI(
        api_key=os.environ.get("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    
    # 強化されたシステムプロンプト（リアリティ重視）
    system_prompt = f"""
あなたはプロの米国株シニアアナリストで、週次市場レポートを執筆しています。
現在の日付は {date_info['today']} です。

【厳守ルール】
1. 必ずLive Searchツールを使用して、以下のサイトから最新の正確なデータを取得してください：
   - Yahoo Finance (finance.yahoo.com)
   - Investing.com
   - Bloomberg.com または CNBC.com（ニュース用）
   - MarketWatch.com
   株価は終値ベースで、週間始値・終値・騰落率を正確に記載。

2. 未来のことはわからないという表現は絶対に禁止。{date_info['current_range']} の週を「直近完了した週」として、事実ベースで分析。

3. 株価・オプションのストライク価格は必ず現在の実勢価格に近い現実的な値を使用（例: 現在の株価が$400なら$420コールなど）。

4. ニュースは具体的に：日付、数字、企業発表内容、影響を明記。曖昧な表現（「懸念が浮上」など）は避け、根拠を示す。

5. オプション活動のコール/プット比は市場センチメントを反映しつつ、現実的な数値（例: 1.4:1など）で記載。

6. Markdownで見やすく整理。太字、数値強調、箇条書きを積極活用。

7. 日本語で自然かつプロフェッショナルな文体。
"""

    user_prompt = f"""
【分析対象期間】
・直近週：{date_info['current_range']}（{date_info['current_start']} ～ {date_info['current_end']}）
・前週：{date_info['prev_range']}

【今回のセクション：{section_title}】
{section_detail}

特に以下の点を必ず含めてください：
- 数値データ（株価は小数点2桁まで、騰落率は%で小数点2桁）
- 具体的なニュース（日付・内容・影響）
- 現実的なオプションストライク価格（現在の株価 ±10〜20%程度）
- 前週との明確な比較
- 総括セクションではS&P500、Nasdaq、Dowの週間パフォーマンスを必ず1行で記載

出力は読みやすく、適切な改行とMarkdownを使用してください。
"""

    response = client.chat.completions.create(
        model="grok-3",  # または "grok-4" が利用可能ならそちらを推奨
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=4000
    )
    return response.choices[0].message.content

def send_discord(title, content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url:
        print("Discord Webhook URLが設定されていません")
        return
    
    header = f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n## 📈 {title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    full_content = header + content
    
    # Discord 2000文字制限対策（安全マージン付き分割）
    chunks = []
    while len(full_content) > 1950:
        split_point = full_content.rfind('\n', 0, 1950)
        if split_point == -1:
            split_point = 1950
        chunks.append(full_content[:split_point])
        full_content = "👉 (続き)\n" + full_content[split_point:]
    chunks.append(full_content)
    
    for i, chunk in enumerate(chunks):
        payload = {"content": chunk}
        try:
            r = requests.post(webhook_url, json=payload)
            if r.status_code != 204:
                print(f"Discord送信失敗 ({title} part {i+1}): {r.status_code}")
            time.sleep(1.8)  # レート制限回避
        except Exception as e:
            print(f"送信エラー: {e}")
    
    print(f"Sent: {title}")

if __name__ == "__main__":
    dates = get_date_info()
    print(f"レポート生成開始: {dates['today']}（対象週: {dates['current_range']}）")

    sections = [
        ("1. 市場全体のパフォーマンスとトレンド", 
         "S&P500, Dow Jones, NASDAQ, Russell 2000の週間騰落率と終値。主要セクター（テクノロジー、金融、消費財、エネルギーなど）のパフォーマンス比較。取引量の増減傾向も記載。"),
        
        ("2. テクニカル指標と市場の健康度", 
         "VIX指数の推移、ヒンデンブルグ・オーメン、新高値/新安値比率、Advance-Decline Line、Fear & Greed Indexの最新値と前週比較。"),
        
        ("3. 金融政策とマクロ環境", 
         "10年物国債利回り、DXYドル指数、WTI原油、金、銅の週間動向。CME FedWatch Toolに基づく次回FOMCの利下げ/据え置き確率。"),
        
        ("4. 経済指標とイベント", 
         "直近週に発表された主要経済指標（雇用統計、CPI、PPI、小売売上など）の実績と市場予想との比較。主要企業の決算ハイライトと株価反応。地政学リスクの影響。"),
        
        ("5. センチメントと心理指標", 
         "AAII調査（強気/弱気比率）、CNN Fear & Greed Index、全体のプット/コール比率、ショートインタレストの高い銘柄動向。"),
        
        ("6. 主要銘柄（TSLA, PLTR, SOFI, CELH）詳細分析 & 週の総括", 
         "TSLA, PLTR, SOFI, CELHの4銘柄について、それぞれ以下のフォーマットで分析：\n"
         "- 株価動向（週間始値→終値、騰落率）\n"
         "- ニュースハイライト（具体的な出来事、日付、数字）\n"
         "- オプション活動（コール:プット比、注目ストライクとその理由）\n"
         "- 前週との比較\n"
         "最後に週の総括（市場全体 + 銘柄別ランキング）と、投資戦略の示唆（強気/中立/弱気 + 具体的なオプション提案）を記載。")
    ]

    for title, detail in sections:
        try:
            print(f"生成中: {title}")
            report = get_grok_report(title, detail, dates)
            send_discord(title, report)
        except Exception as e:
            error_msg = f"エラー発生: {title}\n```python\n{e}\n```"
            send_discord("⚠️ レポート生成エラー", error_msg)
            print(f"Error in {title}: {e}")
    
    send_discord("✅ 週次市場レポート", "すべてのセクションの送信が完了しました！")
    print("全レポート送信完了！")
