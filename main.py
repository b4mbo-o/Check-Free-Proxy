import requests
import os
import concurrent.futures
from datetime import datetime

# --- 設定 ---
SOURCE_URL = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
FILE_ALIVE = "alive.txt"
FILE_CACHE = "list_cache.txt"
CHECK_URL = "http://httpbin.org/ip"
TIMEOUT = 10
MAX_WORKERS = 100 

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_my_ip():
    try:
        return requests.get(CHECK_URL, timeout=TIMEOUT).json()['origin']
    except:
        log("❌ インターネット接続エラー")
        return None

def download_list():
    log("📥 最新リストを取得中...")
    try:
        resp = requests.get(SOURCE_URL, timeout=20)
        resp.raise_for_status()
        proxies = set(line.strip() for line in resp.text.splitlines() if line.strip())
        return proxies
    except Exception as e:
        log(f"❌ ダウンロード失敗: {e}")
        return set()

def load_file_as_set(filename):
    if not os.path.exists(filename):
        return set()
    with open(filename, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_set_to_file(filename, data_set):
    with open(filename, "w", encoding="utf-8") as f:
        for item in data_set:
            f.write(item + "\n")

def check_proxy(proxy, my_ip):
    formatted_proxy = proxy if proxy.startswith("http") else f"http://{proxy}"
    proxies = {"http": formatted_proxy, "https": formatted_proxy}
    try:
        resp = requests.get(CHECK_URL, proxies=proxies, timeout=TIMEOUT)
        resp.raise_for_status()
        if my_ip in resp.json()['origin']: return False
        return True
    except:
        return False

def check_list_parallel(proxy_list, my_ip):
    if not proxy_list: return set()
    alive = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_proxy = {executor.submit(check_proxy, p, my_ip): p for p in proxy_list}
        for future in concurrent.futures.as_completed(future_to_proxy):
            if future.result():
                alive.add(future_to_proxy[future])
    return alive

def main():
    log("🚀 GitHub Actions Proxy Checker Started")
    my_ip = get_my_ip()
    if not my_ip: return

    prev_alive = load_file_as_set(FILE_ALIVE)
    prev_cache = load_file_as_set(FILE_CACHE)
    current_source = download_list()
    
    if not current_source: current_source = prev_cache

    # 新規分 = 今回取得分 - 前回取得分 - 既に生存リストにある分
    new_arrivals = current_source - prev_cache
    targets_new = new_arrivals - prev_alive
    
    log(f"📋 再チェック: {len(prev_alive)}件 / 新規チェック: {len(targets_new)}件")

    alive_recheck = check_list_parallel(prev_alive, my_ip)
    alive_new = check_list_parallel(targets_new, my_ip)
    
    final_alive = alive_recheck | alive_new
    
    save_set_to_file(FILE_ALIVE, final_alive)
    save_set_to_file(FILE_CACHE, current_source)
    
    log(f"✅ 完了: {len(final_alive)} 件が生存。ファイルを更新しました。")

if __name__ == "__main__":
    main()
