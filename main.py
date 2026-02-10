import os
import datetime
import requests
import time
import sys

# ライブラリ未インストールによるエラーを避けるためのチェック
try:
    import yfinance as yf
    from openai import OpenAI
except ImportError as e:
    print(f"Error: Missing libraries. {e}")
    sys.exit(1)

def get_market_data():
    """ yfinanceから物理データを取得。TNXの計算処理は行わず、そのまま使用。 """
    tickers = {
        "PLTR": "Palantir", "TSLA": "Tesla", "SOFI": "SoFi", "CELH": "Celsius",
        "^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "Dow Jones", "^RUT": "Russell 2000",
        "^VIX": "VIX Index", 
        "^TNX": "US 10Y Treasury Yield", 
        "DX-Y.NYB": "US Dollar Index", 
        "CL=F": "WTI Crude Oil Futures", 
        "GC=F": "Gold Futures"
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
                actual_val = round(close_end, 2)
                data_results[symbol] = {
                    "name": name, "val": actual_val, "change": round(change, 2)
                }
        except Exception as e:
            print(f"Warning: Could not get data for {symbol}: {e}")
            data_results[symbol] = "Error"
    return data_results, start_date, end_date

def get_grok_report(section_title, section_detail, date_info, market_data, is_final=False):
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise ValueError("XAI_API_KEY is not set in environment variables.")
        
    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1", timeout=300.0)
    
    market_summary = "【確定取引データ（2026年2月）】\n"
    for k, v in market_data.items():
        if isinstance(v, dict):
            label = v['name']
            val = v['val']
            change = v['change']
            if k == "^TNX":
                market_summary += f"- {label} ({k}): {val}% (週間騰落率 {change}%)\n"
            else:
                market_summary += f"- {label} ({k}): {val} (週間騰落率 {change}%)\n"

    system_prompt = f"""
あなたはプロのシニアマーケットアナリストです。
【厳守事項】
1. **推論の完全排除**: 「〜と思われる」「可能性がある」等の表現を禁止。確定データを「事実」として断定的に記述せよ。
2. **前置き・定義の禁止**: 指標の解説は不要。## 見出しから即、分析を開始せよ。
3. **数値捏造の禁止**: 提示された確定データのみを使用せよ。
4. **結びの言葉**: {"最後に必ず『以上』と一行添えてください。" if is_final else "セクションの最後は簡潔に締めてください。"}
5. **日付**: 現在は2026年2月です。

{market_summary}
"""
    user_prompt = f"分析期間: {date_info['current_range']}\nセクション: {section_title}\n指示: {section_detail}"

    response = client.chat.completions.create(
        model="grok-3",
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=0.1
    )
    return response.choices[0].message.content

def send_discord_split(title, content):
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url:
        print("Error: DISCORD_WEB_HOOK is not set.")
        return

    header = f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n## 📊 {title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    limit = 1850
    chunks = []
    text_to_process = content
    
    while text_to_process:
        if len(text_to_process) <= limit:
            chunks.append(text_to_process)
            break
        split_at = text_to_process.rfind('\n', 0, limit)
        if split_at == -1: split_at = limit
        chunks.append(text_to_process[:split_at])
        text_to_process = text_to_process[split_at:].strip()

    for i, chunk in enumerate(chunks):
        msg_header = header if i == 0 else f"**{title} ({i+1}/{len(chunks)}) 続き**\n"
        try:
            requests.post(webhook_url, json={"content": msg_header + chunk})
        except Exception as e:
            print(f"Failed to send to Discord: {e}")
        time.sleep(2.0)

if __name__ == "__main__":
    try:
        raw_data, s_dt, e_dt = get_market_data()
        date_info = {
            "today": datetime.date.today().strftime('%Y年%m月%d日'), 
            "current_range": f"{s_dt.strftime('%m/%d')}〜{e_dt.strftime('%m/%d')}"
        }

        tasks = [
            ("市場概況と指数分析", "主要指数の確定値に基づき分析。前置き不要。"),
            ("金融環境とマクロ指標分析", "米国10年債利回り、VIX、DXY、金先物、原油先物の確定値に基づき背景を分析。推測厳禁。"),
            ("個別株(TSLA, PLTR)詳細分析", "確定値に基づきニュースとオプション活動を分析。"),
            ("個別株(SOFI, CELH) & 総括", "確定値に基づく個別分析と投資戦略。文末に必ず『以上』と記載。")
        ]

        for i, (title, detail) in enumerate(tasks):
            is_final = (i == len(tasks) - 1)
            report_content = get_grok_report(title, detail, date_info, raw_data, is_final=is_final)
            send_discord_split(title, report_content)
            time.sleep(1)

        print("Success: All reports sent.")
    except Exception as e:
        print(f"Execution Error: {e}")
        sys.exit(1)
