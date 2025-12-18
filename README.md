# 🚀 Auto Proxy Checker & List

[![Daily Proxy Check](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/actions/workflows/daily_check.yml/badge.svg)](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME/actions/workflows/daily_check.yml)

GitHub Actionsを利用して、毎日自動で**有効かつ無料のプロキシ**を収集・検証し、リストを更新するリポジトリです。
[TheSpeedX/PROXY-List](https://github.com/TheSpeedX/PROXY-List) の膨大なリストから、実際に接続可能でIP漏洩のないものだけを厳選しています。

This repository automatically collects, validates, and updates a list of **working and anonymous proxies** daily using GitHub Actions.

## 📂 Live Proxy Lists (Auto Updated)
毎日 JST 04:00 (UTC 19:00) に自動更新されます。  
Rawリンクをクリックして、ツールやスクリプトで直接利用できます。

| Protocol | Status | Raw File (Text) |
| :--- | :---: | :--- |
| **HTTP / HTTPS** | 🟢 Active | [**alive_http.txt**](./alive_http.txt) |
| **SOCKS4** | 🟢 Active | [**alive_socks4.txt**](./alive_socks4.txt) |
| **SOCKS5** | 🟢 Active | [**alive_socks5.txt**](./alive_socks5.txt) |

> **Format:** `IP:Port` 

## ⚙️ How it Works (仕組み)

効率的に検証を行うため、スマートな差分チェックシステムを採用しています。

1.  **Fetch**: [TheSpeedX](https://github.com/TheSpeedX/PROXY-List) から最新のプロキシリストを取得。
2.  **Diff**: 前回チェックしたリストと比較し、**「新規追加されたプロキシ」**のみを抽出。
3.  **Re-check**: 前回のスキャンで**「生存していたプロキシ」**を再検証。
4.  **Update**: 生き残ったプロキシだけをリストに保存し、Commit & Push。

これにより、サーバー負荷を抑えつつ、常に新鮮なリストを提供します。

## 🛠 Usage (Local Run)

自分のPCで手動実行したい場合の手順です。

### Requirements
- Python 3.9+
- `requests[socks]`

### Installation

```bash
# Clone this repository
git clone [https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git)
cd YOUR_REPO_NAME

# Install dependencies
pip install "requests[socks]"
```

### Run

```bash
python main.py
```

実行すると `alive_http.txt`, `alive_socks4.txt`, `alive_socks5.txt` が生成されます。

## 🤖 Automation

GitHub Actionsの `cron` スケジュール機能により完全自動化されています。
設定ファイル: `.github/workflows/daily_check.yml`

- **Schedule**: Daily at 19:00 UTC (04:00 JST)
- **Timeout**: 10 seconds per proxy
- **Concurrency**: 100 threads

## 📝 License

This project is open source. Feel free to use the proxy lists for your projects.
