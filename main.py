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

def get_master_data(date_info):
    """
    全セクションで共通して使用する確定数値を最初に取得する。
    """
    client = OpenAI(api_key=os.environ.get("XAI_API_KEY"), base_url="https://api.x.ai/v1")
    
    prompt = f"""
    対象期間（{date_info['current_start']} 〜 {date_info['current_end']}）の米国市場の確定数値を調査し、以下のJSON形式で返してください。
    
    調査対象：
    1. 主要指数（S&P500, NASDAQ, Dow, Russell 2000）の始値・終値・騰落率
    2. 主要銘柄（TSLA, PLTR, SOFI, CELH）の始値・終値・騰落率
    3. 主要指標（VIX, 10年債利回り, DXY, 原油, 金）の終値
    
    出力形式：
    {{
      "indices": {{"SP500": {{"start": 0, "end": 0, "change": "0%"}}, ...}},
      "stocks": {{"TSLA": {{"start": 0, "end": 0, "change": "0%"}}, ...}},
      "macro": {{"VIX": 0, "US10Y": "0%", "DXY": 0, "WTI": 0, "GOLD": 0}}
    }}
    必ず実在する確定データを使用してください。
    """
    
    response = client.chat.completions.create(
        model="grok-3",
        messages=[{"role": "system", "content": "あなたは正確なデータ抽出を行うアシスタントです。"},
                  {"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message.content

def get_grok_report(section_title, section_detail, date_info, master_data_text):
    client = OpenAI(
        api_key=os.environ.get("XAI_API_KEY"),
        base_url="https://api.x.ai/v1",
    )
    
    system_prompt = f"""
あなたはプロの米国株シニアアナリストです。
現在の日付は {date_info['today']} です。

【鉄則：整合性の保持】
以下の「確定マスターデータ」にある数値を絶対的な基準として使用してください。
各セクション間で数値が矛盾することは許されません。

【確定マスターデータ】
{master_data_text}

【執筆ルール】
1. 数値は上記データから引用し、勝手に書き換えない。
2. ニュースは実在する企業の事実のみを記載。
3. 2026年の実勢価格（S&P500 7000前後等）に基づき、現実的なオプション価格を提示。
4. Markdownを使い、プロフェッショナルな日本語で出力。
"""

    user_prompt = f"""
【分析対象期間】
・直近週：{date_info['current_range']}（{date_info['current_start']} ～ {date_info['current_end']}）
・前週：{date_info['prev_range']}

【今回のセクション：{section_title}】
{section_detail}

冒頭に「データ取得日時: {date_info['today']}」を記載し、マスターデータと整合した正確なレポートを作成してください。
"""

    response = client.chat.completions.create(
        model="grok-3",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3, # 整合性重視のためさらに低く
        max_tokens=4000
    )
    return response.choices[0].message.content

# --- send_discord 関数は変更なし ---
def send_discord(title, content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url:
        print("Discord Webhook URLが設定されていません")
        return
    
    header = f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n## 📈 {title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    full_content = header + content
    
    chunks = []
    while len(full_content) > 1800:
        split_point = full_content.rfind('\n', 0, 1800)
        if split_point == -1:
            split_point = 1800
        chunks.append(full_content[:split_point])
        full_content = "👉 (続き)\n" + full_content[split_point:]
    chunks.append(full_content)
    
    for i, chunk in enumerate(chunks):
        payload = {"content": chunk}
        try:
            r = requests.post(webhook_url, json=payload)
            if r.status_code != 204:
                print(f"Discord送信失敗 ({title} part {i+1}): {r.status_code}")
            time.sleep(2.0)
        except Exception as e:
            print(f"送信エラー: {e}")
    
    print(f"Sent: {title}")

if __name__ == "__main__":
    dates = get_date_info()
    print(f"レポート生成開始: {dates['today']}（対象週: {dates['current_range']}）")

    # 1. 最初にマスターデータを確定させる
    print("共通マスターデータを取得中...")
    master_data_text = get_master_data(dates)
    print("マスターデータ取得完了。各セクションの生成を開始します。")

    sections = [
        ("1. 市場全体のパフォーマンスとトレンド", 
         "S&P500, Dow Jones, NASDAQ, Russell 2000の週間騰落率と終値。主要セクターの比較。"),
        
        ("2. テクニカル指標と市場の健康度", 
         "VIX、新高値/新安値比率、A/Dライン、Fear & Greed Indexの分析。"),
        
        ("3. 金融政策とマクロ環境", 
         "金利、ドル指数、原油、金、銅の動向とFedWatchの確率。"),
        
        ("4. 経済指標とイベント", 
         "雇用統計、CPI等の実績と予想の比較。主要企業の決算結果。"),
        
        ("5. センチメントと心理指標", 
         "AAII調査、プット/コール比率、ショートインタレスト動向。"),
        
        ("6. 主要銘柄（TSLA, PLTR, SOFI, CELH）詳細分析 & 週の総括", 
         "TSLA, PLTR, SOFI, CELHの個別分析と、市場全体の総括、具体的な投資戦略。")
    ]

    for title, detail in sections:
        try:
            print(f"生成中: {title}")
            # マスターデータを注入して生成
            report = get_grok_report(title, detail, dates, master_data_text)
            send_discord(title, report)
        except Exception as e:
            error_msg = f"エラー発生: {title}\n```python\n{e}\n```"
            send_discord("⚠️ レポート生成エラー", error_msg)
            print(f"Error in {title}: {e}")
    
    send_discord("✅ 週次市場レポート", "すべてのセクションの送信が完了しました！")
    print("全レポート送信完了！")
