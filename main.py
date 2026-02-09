import os
import datetime
import requests
import time
import yfinance as yf
from openai import OpenAI

def get_market_data():
    """ yfinanceから主要指数・個別銘柄・コモディティ・マクロ指標を物理取得 """
    tickers = {
        "PLTR": "Palantir", "TSLA": "Tesla", "SOFI": "SoFi", "CELH": "Celsius",
        "^GSPC": "S&P 500", "^IXIC": "NASDAQ", "^DJI": "Dow Jones", "^RUT": "Russell 2000",
        "^VIX": "VIX Index", "^TNX": "10Y Treasury Yield",
        "DX-Y.NYB": "US Dollar Index", "CL=F": "WTI Crude Oil", "GC=F": "Gold"
    }
    data_results = {}
    today = datetime.date.today()
    # 直近の完了した週（金曜終値）を計算
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
                
                actual_val = round(close_end, 2)
                if symbol == "^TNX":
                    actual_val = round(close_end / 10, 2) # 利回り(%)表示

                data_results[symbol] = {
                    "name": name, "val": actual_val, "change": round(change, 2)
                }
        except: data_results[symbol] = "Error"
    return data_results, start_date, end_date

def get_grok_report(section_title, section_detail, date_info, market_data, is_final=False):
    client = OpenAI(api_key=os.environ.get("XAI_API_KEY"), base_url="https://api.x.ai/v1", timeout=200.0)
    
    market_summary = "【確定取引データ（2026年）】\n"
    for k, v in market_data.items():
        if isinstance(v, dict):
            unit = "%" if k == "^TNX" else ""
            market_summary += f"- {v['name']} ({k}): {v['val']}{unit} (週間騰落率 {v['change']}%)\n"

    system_prompt = f"""
あなたはプロのシニアマーケットアナリストです。
【厳守事項：客観的事実のみの記述】
1. **推論の排除**: 「〜の可能性がある」「〜と推測される」といった曖昧な表現を禁止します。確定データを「事実」として断定的に記述してください。
2. **解説の排除**: 指標の定義や一般論（例：VIXとは、ヒンデンブルグオーメンとは、等）は一切不要です。即、本題の分析に入ってください。
3. **データ欠如時の対応**: 確定データにない数値を捏造しないでください。不明な指標は項目ごと削除してください。
4. **結びの言葉**: {"レポートの最後には必ず『以上』と記述し、分析を完結させてください。" if is_final else "セクションの最後は簡潔に締めてください。"}
5. **前置きの禁止**: 「このレポートでは」等の導入文は一切書かないでください。

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
    """ 内容を適切に分割し、インデックスを付けて連投する """
    webhook_url = os.environ.get("DISCORD_WEB_HOOK")
    if not webhook_url: return

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
        requests.post(webhook_url, json={"content": msg_header + chunk})
        time.sleep(2.0)

if __name__ == "__main__":
    raw_data, s_dt, e_dt = get_market_data()
    date_info = {"today": datetime.date.today().strftime('%Y年%m月%d日'), "current_range": f"{s_dt.strftime('%m/%d')}〜{e_dt.strftime('%m/%d')}"}

    tasks = [
        ("市場概況と指数分析", "主要指数の確定値に基づき、その週の変動要因となったニュースを分析。前置き不要。"),
        ("金融環境と主要指標", "VIX, TNX, DXY, 商品(原油・金)の確定値に基づき背景を分析。推測や一般論は厳禁。"),
        ("主要銘柄(TSLA, PLTR)詳細分析", "確定値に基づき重要ニュースとオプション活動を記述。"),
        ("主要銘柄(SOFI, CELH) & 総括", "確定値に基づき個別分析と、全体の投資戦略。文末に必ず『以上』を記載すること。")
    ]

    for i, (title, detail) in enumerate(tasks):
        try:
            print(f"生成中: {title}")
            # 最後のタスクの場合のみ is_final=True にする
            is_final = (i == len(tasks) - 1)
            report = get_grok_report(title, detail, date_info, raw_data, is_final=is_final)
            send_discord_split(title, report)
        except Exception as e:
            print(f"Error in {title}: {e}")

    print("全ての処理が正常に完了しました。")
