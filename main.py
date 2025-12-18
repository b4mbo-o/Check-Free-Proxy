import requests
import os
import concurrent.futures
from datetime import datetime

# --- 設定 ---
SOURCES = {
    "http": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "socks4": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"
}

# 保存ファイル名の定義
FILES = {
    "http": "alive_http.txt",
    "socks4": "alive_socks4.txt",
    "socks5": "alive_socks5.txt"
}

FILE_CACHE = "list_cache.txt" # 全体キャッシュ
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

def download_all_lists():
    """全リスト取得し、プレフィックス(socks5://など)を付けて統合セットにする"""
    combined = set() # setを使うことで自動的に重複が消えます
    for proto, url in SOURCES.items():
        log(f"📥 {proto.upper()} リストを取得中...")
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            for line in resp.text.splitlines():
                p = line.strip()
                if p:
                    # 統一フォーマット: protocol://ip:port
                    if "://" not in p:
                        p = f"{proto}://{p}"
                    combined.add(p) # ここで重複は弾かれます
        except Exception as e:
            log(f"❌ {proto.upper()} 取得失敗: {e}")
    return combined

def load_prev_alive():
    combined = set()
    for proto, filename in FILES.items():
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                for line in f:
                    p = line.strip()
                    if p:
                        combined.add(f"{proto}://{p}")
    return combined

def save_alive_split(alive_set):
    """
    生存リストをプロトコルごとに分けて保存する
    """
    data = {k: [] for k in FILES.keys()}

    for proxy in alive_set:
        if proxy.startswith("socks5://"):
            data["socks5"].append(proxy.replace("socks5://", ""))
        elif proxy.startswith("socks4://"):
            data["socks4"].append(proxy.replace("socks4://", ""))
        else:
            clean_ip = proxy.replace("http://", "")
            data["http"].append(clean_ip)

    # ファイル書き込み
    for proto, filename in FILES.items():
        # ★ここが重要: set() で重複を消し、sorted() で綺麗に並べる
        unique_lines = sorted(list(set(data[proto])))
        
        with open(filename, "w", encoding="utf-8") as f:
            for line in unique_lines:
                f.write(line + "\n")
        log(f"💾 {filename}: {len(unique_lines)} 件 保存")

def load_file_as_set(filename):
    if not os.path.exists(filename):
        return set()
    with open(filename, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_set_to_file(filename, data_set):
    with open(filename, "w", encoding="utf-8") as f:
        for item in sorted(list(data_set)):
            f.write(item + "\n")

def check_proxy(proxy_url, my_ip):
    proxies = {"http": proxy_url, "https": proxy_url}
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
    total = len(proxy_list)
    completed = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_proxy = {executor.submit(check_proxy, p, my_ip): p for p in proxy_list}
        for future in concurrent.futures.as_completed(future_to_proxy):
            completed += 1
            if completed % 500 == 0:
                print(f"   Progress: {completed}/{total} ...")
            if future.result():
                alive.add(future_to_proxy[future])
    return alive

def main():
    log("🚀 Proxy Checker (No Duplicates Mode)")
    my_ip = get_my_ip()
    if not my_ip: return

    prev_alive = load_prev_alive()
    prev_cache = load_file_as_set(FILE_CACHE)
    current_source = download_all_lists()
    
    if not current_source: current_source = prev_cache

    new_arrivals = current_source - prev_cache
    targets_new = new_arrivals - prev_alive
    
    log(f"📋 再チェック: {len(prev_alive)}件")
    log(f"📋 新規チェック: {len(targets_new)}件")

    alive_recheck = check_list_parallel(prev_alive, my_ip)
    alive_new = check_list_parallel(targets_new, my_ip)
    
    final_alive = alive_recheck | alive_new
    
    save_alive_split(final_alive)
    save_set_to_file(FILE_CACHE, current_source)
    
    log(f"✅ 完了。全 {len(final_alive)} 件")

if __name__ == "__main__":
    main()
