import os
import datetime
import requests
import time
import yfinance as yf
from openai import OpenAI

def get_market_data():
    """ yfinanceから物理データを取得。利回りの計算ミスを徹底排除。 """
    tickers = {
        "PLTR": "Palantir", "TSLA": "Tesla", "SOFI": "SoFi", "CELH": "Celsius",
        "^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "Dow Jones", "^RUT": "Russell 2000",
        "^VIX": "VIX Index", 
        "^TNX": "US 10Y Treasury Yield", # 米国10年債利回り
        "DX-Y.NYB": "US Dollar Index", 
        "CL=F": "WTI Crude Oil Futures", # 原油先物
        "GC=F": "Gold Futures"           # 金先物
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
                close_end = hist['Close'].iloc[-1]
                close_start = hist['Close'].iloc[0]
                change = ((close_end - close_start) / close_start) * 100
                
                # 【重要】TNX(利回り)の計算。YahooFinanceでは10倍の値で届く(45.2 = 4.52%)
                if symbol == "^TNX":
                    actual_val = round(close_end / 10, 3) # 念のため小数点第3位まで
                else:
                    actual_val = round(close_end, 2)

                data_results[symbol] = {
                    "name": name, "val": actual_val, "change": round(change, 2)
                }
        except: data_results[symbol] = "Error"
    return data_results, start_date, end_date

def get_grok_report(section_title, section_detail, date_info, market_data, is_final=False):
    client = OpenAI(api_key=os.environ.get("XAI_API_KEY"), base_url="https://api.x.ai/v1", timeout=200.0)
    
    # AIへ渡す数値リストの構築（間違いを誘発しない形式）
    market_summary = "【2026年2月 第1週 確定取引データ】\n"
    for k, v in market_data.items():
        if isinstance(v, dict):
            # 利回りには % を、それ以外には適切な通貨記号をイメージさせる指示
            label = v['name']
            val = v['val']
            change = v['change']
            if k == "^TNX":
                market_summary += f"- {label} ({k}): {val}% (週間変化 {change}%)\n"
            else:
                market_summary += f"- {label} ({k}): {val} (週間騰落率 {change}%)\n"

    system_prompt = f"""
あなたはプロのシニアマーケットアナリストです。
【厳守：数値の正確性と事実主義】
1. **数値の捏造・再計算の禁止**: 提供された「確定取引データ」の数値をそのまま使用してください。特に米国10年債利回り(^TNX)を勝手に割ったり掛けたりしてはいけません。
2. **推論の排除**: 「〜と思われる」「可能性が高い」等の曖昧な表現を禁止し、断定的に事実を記述してください。
3. **一般論・定義の排除**: 指標の解説は不要です。即、本題の分析（なぜその数値になったか）に入ってください。
4. **結びの言葉**: {"最後に必ず『以上』と一行添えてください。" if is_final else "簡潔に締めてください。"}
5. **日付**: 現在は2026年2月です。

{market_summary}
"""
    user_prompt = f"分析期間: {date_info['current_range']}\nセクション: {section_title}\n詳細: {section_detail}"

    response = client.chat.completions.create(
        model="grok-3",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content

# send_discord_split は以前のコードと同じため維持

if __name__ == "__main__":
    raw_data, s_dt, e_dt = get_market_data()
    date_info = {"today": datetime.date.today().strftime('%Y年%m月%d日'), "current_range": f"{s_dt.strftime('%m/%d')}〜{e_dt.strftime('%m/%d')}"}

    tasks = [
        ("市場概況と指数分析", "S&P500, NASDAQ等の確定値に基づき変動要因を分析。前置き不要。"),
        ("金融環境とマクロ指標", "米国10年債利回り、VIX、DXY、金先物、原油先物の確定値に基づき背景を分析。推測厳禁。"),
        ("主要銘柄(TSLA, PLTR)詳細", "確定値に基づきニュースとオプション活動を分析。"),
        ("主要銘柄(SOFI, CELH) & 総括", "確定値に基づき分析と投資戦略。文末に必ず『以上』と記載。")
    ]

    for i, (title, detail) in enumerate(tasks):
        try:
            print(f"作成中: {title}")
            report = get_grok_report(title, detail, date_info, raw_data, is_final=(i == len(tasks)-1))
            # ここで send_discord_split を呼び出す
            # send_discord_split(title, report) 
        except Exception as e:
            print(f"Error: {e}")
