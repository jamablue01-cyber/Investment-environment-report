import yfinance as yf
import os
import datetime
import requests
import time
from openai import OpenAI

def get_date_info():
    today = datetime.date.today()
    days_since_monday = today.weekday()
    
    # 今日が月曜(0)〜火曜(1)の場合、先週を対象にオフセット
    offset = 7 if days_since_monday <= 1 else 0
    last_monday = today - datetime.timedelta(days=days_since_monday + offset)
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
        timeout=120.0, # 検索に時間がかかるためタイムアウトを延長
    )
    
    # 【最重要修正】2026年の実勢価格帯をAIに強制認識させるプロンプト
    system_prompt = f"""
あなたはプロの米国株シニアアナリストです。
現在の日付は {date_info['today']} です。

【価格バリデーション・ルール（2026年実勢）】
Live Searchで見つかったデータが以下の範囲外である場合、それは「古いデータ」または「誤報」です。必ず再検索して最新の2026年終値を採用してください：
- PLTR: 終値は $400 〜 $700 の範囲内（$100以下は2024年以前の古いデータです）
- TSLA: 終値は $900 〜 $1,300 の範囲内
- 主要指数（S&P500 6,500超、NASDAQ 22,000超、Dow 48,000超）

【厳守ルール】
1. 対象週は必ず完了した過去の週（金曜終値まで確定したもの）を扱う。
2. Yahoo Finance (Historical Data) を最優先し、2026年現在の実勢レベルを厳密に反映すること。
3. ニュースは架空のものを排除し、実在企業・実際の数字を明記。
4. 数値の桁間違い（100Bと10B、株価の小数点の位置など）を徹底的にチェックしてください。
"""

    user_prompt = f"""
【分析対象期間】
・直近週：{date_info['current_range']}（{date_info['current_start']} ～ {date_info['current_end']}）
・前々週：{date_info['prev_range']}

【今回のセクション：{section_title}】
{section_detail}

특히 PLTRについては、現在S&P500の主力銘柄として株価が数百ドル台で推移しています。
過去の「$20〜$40台」のデータは一切無視し、最新の終値を正確に報告してください。

出力形式：
- 各銘柄の終値を正確に記載（例: PLTR: $xxx.xx）
- 前週との騰落率を小数点2桁まで
- 適切な改行とMarkdown（太字等）を使用
- レポート冒頭に「データ取得日時: {date_info['today']}」を追加
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,  # 事実精度をさらに高めるため低めに設定
        max_tokens=4000
    )
    return response.choices[0].message.content

def send_discord(title, content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url: return
    
    header = f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n## 📈 {title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    full_content = header + content
    
    # 2000文字制限対策
    chunks = []
    while len(full_content) > 1800:
        split_point = full_content.rfind('\n', 0, 1800)
        if split_point == -1: split_point = 1800
        chunks.append(full_content[:split_point])
        full_content = "👉 (続き)\n" + full_content[split_point:]
    chunks.append(full_content)
    
    for chunk in chunks:
        requests.post(webhook_url, json={"content": chunk})
        time.sleep(1.5)
    
    print(f"Sent: {title}")

if __name__ == "__main__":
    dates = get_date_info()
    print(f"レポート生成開始: {dates['today']}（対象週: {dates['current_range']}）")

    sections = [
        ("1. 市場全体のパフォーマンスとトレンド", "S&P500, Dow Jones, NASDAQ, Russell 2000の週間騰落率と終値。主要セクター比較。"),
        ("2. テクニカル指標と市場の健康度", "VIX、ヒンデンブルグ・オーメン、新高値/新安値比率、Fear & Greed Indexの最新値。"),
        ("3. 金融政策とマクロ環境", "10年債利回り、DXY、WTI原油、金、銅の週間動向。CME FedWatchの利下げ確率。"),
        ("4. 経済指標とイベント", "直近週に発表された主要経済指標実績と予想比。主要企業の決算ハイライト。"),
        ("5. センチメントと心理指標", "AAII調査、CNN Fear & Greed Index、プット/コール比率。"),
        ("6. 主要銘柄（TSLA, PLTR, SOFI, CELH）詳細分析 & 週の総括", 
         "各銘柄の終値（特にPLTRの数百ドル台を厳守）、騰落率、ニュース、オプション活動。最後に投資戦略への示唆。")
    ]

    for title, detail in sections:
        try:
            print(f"生成中: {title}")
            report = get_grok_report(title, detail, dates)
            send_discord(title, report)
        except Exception as e:
            print(f"Error in {title}: {e}")
    
    send_discord("✅ レポート完了", f"{dates['today']} 分の全セクション送信が完了しました。")
