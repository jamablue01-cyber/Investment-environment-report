import os
import datetime
import requests
import time
import sys

# yfinance等は、環境によって入っていない場合があるため安全に読み込む
try:
    import yfinance as yf
    from openai import OpenAI
except ImportError:
    print("Required libraries not found. Please check requirements.txt")

def get_market_data():
    """ yfinanceからデータを取得。1つのエラーで全体を止めない設計 """
    tickers = {
        "PLTR": "Palantir", "TSLA": "Tesla", "SOFI": "SoFi", "CELH": "Celsius",
        "^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "Dow Jones", "^RUT": "Russell 2000",
        "^VIX": "VIX Index", "^TNX": "US 10Y Treasury Yield", 
        "DX-Y.NYB": "US Dollar Index", "CL=F": "WTI Crude Oil Futures", "GC=F": "Gold Futures"
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
                val = round(hist['Close'].iloc[-1], 2)
                chg = round(((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100, 2)
                data_results[symbol] = {"name": name, "val": val, "change": chg}
        except:
            continue # 1つ失敗しても次へ行く
    return data_results, start_date, end_date

def get_grok_report(section_title, section_detail, date_info, market_data, is_final=False):
    api_key = os.environ.get("XAI_API_KEY")
    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1", timeout=300.0)
    
    summary = "【確定取引データ】\n"
    for k, v in market_data.items():
        unit = "%" if k == "^TNX" else ""
        summary += f"- {v['name']}: {v['val']}{unit} ({v['change']}%)\n"

    system_msg = f"""アナリストとして事実のみを記述せよ。推測、前置き、定義の解説は厳禁。
最後に必ず「以上」と一言添えて完結させよ。現在は2026年2月です。
{summary}"""

    res = client.chat.completions.create(
        model="grok-3",
        messages=[{"role": "system", "content": system_msg}, 
                  {"role": "user", "content": f"{section_title}\n{section_detail}"}],
        temperature=0.1
    )
    return res.choices[0].message.content

def send_discord(title, content):
    url = os.environ.get("DISCORD_WEB_HOOK")
    if not url: return
    
    # 2000文字制限対策
    full_msg = f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n## 📊 {title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n{content}"
    for i in range(0, len(full_msg), 1900):
        requests.post(url, json={"content": full_msg[i:i+1900]})
        time.sleep(1)

if __name__ == "__main__":
    data, s_dt, e_dt = get_market_data()
    d_info = {"current_range": f"{s_dt.strftime('%m/%d')}〜{e_dt.strftime('%m/%d')}"}

    # セクションを絞ってエラーを回避
    tasks = [
        ("1. 市場・マクロ指標分析", "主要指数、VIX、金利、ドル、原油、金の動向背景。"),
        ("2. 個別銘柄・戦略総括", "TSLA, PLTR, SOFI, CELHの分析と投資戦略。")
    ]

    for title, detail in tasks:
        try:
            report = get_grok_report(title, detail, d_info, data)
            send_discord(title, report)
        except Exception as e:
            print(f"Error: {e}")