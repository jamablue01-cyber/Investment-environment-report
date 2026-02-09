import os
import datetime
import requests
import time
import yfinance as yf
from openai import OpenAI

def get_market_data():
    """ yfinanceから正確な数値を物理取得 """
    tickers = {
        "PLTR": "Palantir", "TSLA": "Tesla", "SOFI": "SoFi", "CELH": "Celsius",
        "^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "Dow Jones", "^RUT": "Russell 2000"
    }
    data_results = {}
    today = datetime.date.today()
    end_date = today - datetime.timedelta(days=(today.weekday() + 2) % 7 + 1)
    start_date = end_date - datetime.timedelta(days=4)
    
    for symbol, name in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date + datetime.timedelta(days=1))
            if not hist.empty:
                close_start = hist['Close'].iloc[0]
                close_end = hist['Close'].iloc[-1]
                change = ((close_end - close_start) / close_start) * 100
                data_results[symbol] = {
                    "name": name, "close": round(close_end, 2), "change": round(change, 2)
                }
        except: data_results[symbol] = "Error"
    return data_results, start_date, end_date

def get_grok_report(section_title, section_detail, date_info, market_data):
    client = OpenAI(api_key=os.environ.get("XAI_API_KEY"), base_url="https://api.x.ai/v1", timeout=150.0)
    
    market_summary = "【確定取引データ】\n"
    for k, v in market_data.items():
        if isinstance(v, dict):
            market_summary += f"- {v['name']} ({k}): ${v['close']} ({v['change']}%)\n"

    system_prompt = f"""
あなたはプロのシニアアナリストです。文字数制限を気にせず、提供された確定データに基づき、Live Searchを駆使して極めて詳細なレポートを執筆してください。
【鉄則】
1. 確定データ（株価・騰落率）は絶対に変更しない。
2. ニュース、地政学リスク、オプション活動、テクニカル指標を徹底的に調査し、専門的な洞察を加えてください。
3. 読みやすさのためにMarkdown（## や ###）を活用してください。
{market_summary}
"""
    user_prompt = f"対象期間: {date_info['current_range']}\nセクション: {section_title}\n依頼内容: {section_detail}"

    response = client.chat.completions.create(
        model="grok-3",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content

def send_discord_split(title, content):
    """
    内容が2000文字を超えていても、適切に分割してすべてDiscordに送信する。
    """
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url: return

    header = f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n## 📊 {title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    full_text = header + content
    
    # 1900文字ごとに分割
    limit = 1900
    if len(full_text) <= limit:
        requests.post(webhook_url, json={"content": full_text})
    else:
        # 文字数制限を回避するために、文末や改行を探して分割
        while full_text:
            if len(full_text) <= limit:
                requests.post(webhook_url, json={"content": full_text})
                break
            
            # 制限文字数内で最後の改行を探す
            split_at = full_text.rfind('\n', 0, limit)
            if split_at == -1: split_at = limit
            
            chunk = full_text[:split_at]
            requests.post(webhook_url, json={"content": chunk})
            
            full_text = "👉 (続き)\n" + full_text[split_at:].strip()
            time.sleep(1.5) # 連投エラー防止

if __name__ == "__main__":
    raw_data, s_dt, e_dt = get_market_data()
    date_info = {"today": datetime.date.today().strftime('%Y年%m月%d日'), "current_range": f"{s_dt.strftime('%m/%d')}〜{e_dt.strftime('%m/%d')}"}

    # 各セクションを詳細に。Grokに「長く書いていい」と思わせる構成
    tasks = [
        ("1. 市場概況と主要指数分析", "S&P500, NASDAQ, Dow, Russell 2000の騰落背景、セクター動向、出来高の変化を極めて詳細に。"),
        ("2. テクニカル・金融環境・センチメント", "VIX, 10年債利回り, DXY, 商品価格, Fear & Greed Index, ヒンデンブルグオーメン等の状況を網羅。"),
        ("3. 個別銘柄(TSLA, PLTR)深掘り", "TSLAとPLTRの確定値に基づき、ニュース、決算期待、オプション活動、投資家心理を詳細分析。"),
        ("4. 個別銘柄(SOFI, CELH) & 投資戦略総括", "SOFIとCELHの分析、および全体の投資戦略、主要銘柄への具体的な投資示唆を1段落以上で。")
    ]

    for title, detail in tasks:
        try:
            print(f"生成中: {title}")
            report = get_grok_report(title, detail, date_info, raw_data)
            send_discord_split(title, report) # ここで自動分割送信
        except Exception as e:
            print(f"Error: {e}")

    print("全データ送信完了")
