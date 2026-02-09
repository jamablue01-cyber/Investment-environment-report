import os
import datetime
import requests
import time
from typing import Dict, List
from openai import OpenAI

# =========================
# 設定値（GitHub管理しやすく）
# =========================
MODEL_NAME = "grok-3"
MAX_TOKENS = 4000
TEMPERATURE = 0.5
DISCORD_CHUNK_SIZE = 1800
DISCORD_POST_INTERVAL = 2.0

XAI_API_KEY = os.environ.get("XAI_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEB_HOOK")

if not XAI_API_KEY:
    raise EnvironmentError("XAI_API_KEY が設定されていません")
if not DISCORD_WEBHOOK_URL:
    raise EnvironmentError("DISCORD_WEB_HOOK が設定されていません")

# =========================
# 日付計算（確定週のみ）
# =========================
def get_date_info() -> Dict[str, str]:
    today = datetime.date.today()
    weekday = today.weekday()  # Mon=0

    # 月・火は必ず前週を「直近完了週」とする
    offset = 7 if weekday <= 1 else 0

    last_monday = today - datetime.timedelta(days=weekday + offset)
    last_friday = last_monday + datetime.timedelta(days=4)

    prev_monday = last_monday - datetime.timedelta(days=7)
    prev_friday = prev_monday + datetime.timedelta(days=4)

    return {
        "today": today.strftime("%Y年%m月%d日"),
        "current_range": f"{last_monday:%m/%d}〜{last_friday:%m/%d}",
        "prev_range": f"{prev_monday:%m/%d}〜{prev_friday:%m/%d}",
        "current_start": last_monday.isoformat(),
        "current_end": last_friday.isoformat(),
    }

# =========================
# OpenAI Client（使い回し）
# =========================
client = OpenAI(
    api_key=XAI_API_KEY,
    base_url="https://api.x.ai/v1",
)

# =========================
# レポート生成
# =========================
def get_grok_report(
    section_title: str,
    section_detail: str,
    date_info: Dict[str, str],
) -> str:
    system_prompt = f"""
あなたはプロの米国株シニアアナリストです。
現在の日付は {date_info['today']} です。

【厳守ルール】
- 対象週は「{date_info['current_start']}〜{date_info['current_end']}」の完了週のみ
- 未来・進行中データは禁止
- 架空データ・推測は禁止
- 数値は必ず実在する現実的レンジ
- 曖昧表現禁止、根拠明示
- 日本語・Markdownで簡潔かつプロ仕様
"""

    user_prompt = f"""
【分析対象期間】
直近週：{date_info['current_range']}（確定）
前週：{date_info['prev_range']}

【セクション】
{section_title}

【分析指示】
{section_detail}

【必須要件】
- 株価は終値ベース（小数点2桁）
- 騰落率は % 表記（小数点2桁）
- 実在ニュース（企業名・日付・数値）
- オプションは株価±10〜20%の現実的ストライク
- 前週比較を明示
- 冒頭に「データ取得日時: {date_info['today']}」
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    return response.choices[0].message.content.strip()

# =========================
# Discord送信
# =========================
def send_discord(title: str, content: str) -> None:
    header = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"## 📈 {title}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    text = header + content
    chunks: List[str] = []

    while len(text) > DISCORD_CHUNK_SIZE:
        split_at = text.rfind("\n", 0, DISCORD_CHUNK_SIZE)
        if split_at == -1:
            split_at = DISCORD_CHUNK_SIZE
        chunks.append(text[:split_at])
        text = "👉 (続き)\n" + text[split_at:]

    chunks.append(text)

    for i, chunk in enumerate(chunks, 1):
        r = requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": chunk},
            timeout=10,
        )
        if r.status_code != 204:
            print(f"[WARN] Discord送信失敗 {title} part {i}: {r.status_code}")
        time.sleep(DISCORD_POST_INTERVAL)

    print(f"[OK] Sent: {title}")

# =========================
# メイン処理
# =========================
if __name__ == "__main__":
    dates = get_date_info()
    print(f"レポート生成開始: {dates['today']}（対象週: {dates['current_range']}）")

    sections = [
        (
            "1. 市場全体のパフォーマンスとトレンド",
            "S&P500、Dow、NASDAQ、Russell2000の終値・週間騰落率。"
            "主要セクター別パフォーマンスと出来高傾向。"
        ),
        (
            "2. テクニカル指標と市場の健康度",
            "VIX、新高値/新安値、Advance-Decline、Fear & Greed Index。"
        ),
        (
            "3. 金融政策とマクロ環境",
            "10年国債利回り、DXY、WTI原油、金、FedWatch。"
        ),
        (
            "4. 経済指標とイベント",
            "CPI、雇用統計、小売売上、主要企業決算と株価反応。"
        ),
        (
            "5. センチメントと心理指標",
            "AAII、Put/Call比、ショート比率の高い銘柄。"
        ),
        (
            "6. 主要銘柄分析 & 週の総括",
            "TSLA、PLTR、SOFI、CELHの株価・ニュース・オプション動向。"
            "最後に指数まとめと投資戦略示唆。"
        ),
    ]

    for title, detail in sections:
        try:
            print(f"生成中: {title}")
            report = get_grok_report(title, detail, dates)
            send_discord(title, report)
        except Exception as e:
            send_discord(
                "⚠️ レポート生成エラー",
                f"```text\n{title}\n{e}\n```",
            )
            print(f"[ERROR] {title}: {e}")

    send_discord("✅ 週次市場レポート", "すべてのセクションの送信が完了しました！")
    print("全レポート送信完了！")
