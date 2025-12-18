import requests
import os
import concurrent.futures
from datetime import datetime

# --- 設定 ---
# プロトコルごとのリストURL
SOURCES = {
    "http": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "socks4": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
    "socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"
}

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

def download_all_lists():
    """全種類のリストをダウンロードし、プロトコルを付与して統合する"""
    combined_proxies = set()
    
    for protocol, url in SOURCES.items():
        log(f"📥 {protocol.upper()} リストを取得中...")
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            
            count = 0
            for line in resp.text.splitlines():
                p = line.strip()
                if p:
                    # IP:Port の形式ならプロトコルを頭につける
                    # (例: socks5://1.1.1.1:1080)
                    if "://" not in p:
                        p = f"{protocol}://{p}"
                    combined_proxies.add(p)
                    count += 1
            log(f"   -> {count} 件取得")
            
        except Exception as e:
            log(f"❌ {protocol.upper()} 取得失敗: {e}")
    
    return combined_proxies

def load_file_as_set(filename):
    if not os.path.exists(filename):
        return set()
    with open(filename, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_set_to_file(filename, data_set):
    with open(filename, "w", encoding="utf-8") as f:
        # プロトコルごとにソートして保存すると見やすい
        for item in sorted(list(data_set)):
            f.write(item + "\n")

def check_proxy(proxy_url, my_ip):
    """
    proxy_url は 'socks5://1.1.1.1:80' のような形式で渡ってくる
    requests[socks] が入っていればそのまま使える
    """
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
    
    # 完了数表示用
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
    log("🚀 GitHub Actions Proxy Checker (HTTP/SOCKS4/SOCKS5)")
    my_ip = get_my_ip()
    if not my_ip: return

    prev_alive = load_file_as_set(FILE_ALIVE)
    prev_cache = load_file_as_set(FILE_CACHE)
    
    # 全ソースを取得して統合
    current_source = download_all_lists()
    
    if not current_source: 
        log("⚠️ リストが一つも取得できませんでした。既存キャッシュを使用します。")
        current_source = prev_cache

    # 差分計算
    new_arrivals = current_source - prev_cache
    targets_new = new_arrivals - prev_alive
    
    log(f"📋 再チェック: {len(prev_alive)}件")
    log(f"📋 新規チェック: {len(targets_new)}件 (前回との差分)")

    # チェック実行
    alive_recheck = check_list_parallel(prev_alive, my_ip)
    alive_new = check_list_parallel(targets_new, my_ip)
    
    final_alive = alive_recheck | alive_new
    
    save_set_to_file(FILE_ALIVE, final_alive)
    save_set_to_file(FILE_CACHE, current_source)
    
    log(f"✅ 完了: {len(final_alive)} 件が生存。")

if __name__ == "__main__":
    main()
