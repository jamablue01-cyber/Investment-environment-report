name: Weekly Market Report

on:
  workflow_dispatch: # 手動実行用
  push:
    branches:
      - main
  schedule:
    - cron: '0 9 * * 6' # 毎週土曜 18:00 (JST)

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run script
        env:
          XAI_API_KEY: ${{ secrets.XAI_API_KEY }}
          DISCORD_WEB_HOOK: ${{ secrets.DISCORD_WEB_HOOK }}
        run: python main.py