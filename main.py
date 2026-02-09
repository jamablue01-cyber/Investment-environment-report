import os
import datetime
import requests
import time
import yfinance as yf
from openai import OpenAI

def get_market_data():
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
    client = OpenAI(api_key=os.environ.get("XAI_API_KEY"), base_url="https://api.x.ai/v1", timeout=120.0)
    
    # AIに渡す確定データ（そのセクションに関係するものだけを絞り込む）
    market_summary = "【確定データ】\n"
    for k, v in market_data.items():
        if isinstance(v, dict):
            market_summary += f"- {v['name']} ({k}): ${v['close']} ({v['change']}%)\n"

    system_prompt = f"""
あなたはプロの証券アナリストです。
提示された「確定データ」の数値を絶対に変更せず、Live Searchでその背景（ニュース・要因）を詳しく解説してください。
1通の文字数は日本語で800文字程度にまとめ、重要なポイントを強調してください。
{market_summary}
"""
    user_prompt = f"対象期間: {date_info['current_range']}\nセクション: {section_title}\n依頼内容: {section_detail}"

    response = client.chat.completions.create(
        model="grok-3",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content

def send_discord(title, content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url: return
    # 2000文字ギリギリだと失敗するため、余裕を持って分割送信
    header = f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n## 📝 {title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    full_text = header + content
    
    if len(full_text) > 1900:
        parts = [full_text[i:i+1900] for i in range(0, len(full_text), 1900)]
        for part in parts:
            requests.post(webhook_url, json={"content": part})
            time.sleep(1)
    else:
        requests.post(webhook_url, json={"content": full_text})
    time.sleep(2)

if __name__ == "__main__":
    raw_data, s_dt, e_dt = get_market_data()
    date_info = {"today": datetime.date.today().strftime('%Y年%m月%d日'), "current_range": f"{s_dt.strftime('%m/%d')}〜{e_dt.strftime('%m/%d')}"}

    # 1通が長くならないよう、細かくリスト化
    tasks = [
        ("指数動向: S&P500 & NASDAQ", "S&P500とNASDAQの確定値に基づき、下落の主因となった経済指標やテック関連ニュースを分析。"),
        ("指数動向: Dow & Russell", "Dow JonesとRussell 2000の騰落要因と、市場の資金移動（ローテーション）を分析。"),
        ("個別株分析: TSLA (Tesla)", "TSLAの確定値に基づき、中国市場や生産動向などの具体的ニュースを調査。"),
        ("個別株分析: PLTR (Palantir)", "PLTRの大幅下落（-8.03%）の具体的要因（契約遅延や決算期待等）を特定。"),
        ("個別株分析: SOFI & CELH", "SOFIとCELHの動き、および投資戦略の総括を簡潔に。")
    ]

    for title, detail in tasks:
        try:
            print(f"作成中: {title}")
            report = get_grok_report(title, detail, date_info, raw_data)
            send_discord(title, report)
        except Exception as e: print(f"Error: {e}")

    print("全レポート送信完了")
