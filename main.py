import requests
import os
import concurrent.futures
from datetime import datetime
import time
from urllib.parse import urlparse, urlunparse

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
        return requests.get(CHECK_URL, timeout=TIMEOUT).json().get('origin')
    except Exception:
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


# --- 改良されたチェック周り ---

def _normalize_proxy_url(proxy_url: str) -> str:
    """
    proxy_url を受け取り、requests (PySocks経由) で確実に使える形式に整形する。
    - socks5 -> socks5h にして DNS をプロキシ側で解決する（ホスト名解決が必要な場合に安全）
    - 既に scheme を含む場合はそのまま使うが、socks5 を socks5h に変換する
    """
    if not proxy_url:
        return proxy_url
    parsed = urlparse(proxy_url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc or parsed.path  # 万一 scheme がなければ path に入っているかも
    # 正規化: socks5 -> socks5h
    if scheme.startswith("socks5"):
        scheme = "socks5h"
    elif scheme.startswith("socks4"):
        scheme = "socks4"
    elif scheme in ("http", "https"):
        scheme = scheme
    else:
        # 未指定スキームなら http とみなす
        if "://" not in proxy_url:
            return "http://" + proxy_url
    normalized = urlunparse((scheme, netloc, "", "", "", ""))
    return normalized


def _is_fast_enough(elapsed: float, timeout: int, max_allowed_ratio: float = 0.9) -> bool:
    """
    実用上「速い」とみなす閾値。timeout の大部分を超える遅さなら除外する。
    max_allowed_ratio は timeout に対する最大許容比率（デフォルト 90%）
    """
    return elapsed <= timeout * max_allowed_ratio


def check_proxy(proxy_url: str, my_ip: str) -> bool:
    """
    改良版プロキシチェック:
    1) proxy を正規化して requests に渡す
    2) CHECK_URL (httpbin.org/ip) に対して GET を行い、status==200, JSON で origin があり自分の IP を含まないことを確認
       — レスポンスタイムが timeout に近すぎる場合は除外（実用性確認）
    3) 実用チェックとして https://httpbin.org/get にアクセスして GET が成功するか確認（HTTPS経路やホスト名解決をチェック）
    失敗時は False。内部で例外は握りつぶして False を返す（ログは残す）。
    """
    try:
        proxy_norm = _normalize_proxy_url(proxy_url)
        proxies = {"http": proxy_norm, "https": proxy_norm}

        # --- 基本接続チェック ---
        start = time.time()
        resp = requests.get(CHECK_URL, proxies=proxies, timeout=TIMEOUT, allow_redirects=True)
        elapsed = time.time() - start

        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            log(f"❌ {proxy_url} : unexpected Content-Type: {content_type}")
            return False

        data = resp.json()
        origin = data.get("origin", "")
        if not origin:
            log(f"❌ {proxy_url} : no origin field")
            return False

        # 自分の IP が含まれている場合は直通（プロキシ経由になっていない）とみなす
        if my_ip and my_ip in origin:
            log(f"❌ {proxy_url} : origin contains my IP ({my_ip}) -> not anonymous / not via proxy")
            return False

        # 実用的に遅い場合は除外（timeout に近い応答は安定性に問題がある）
        if not _is_fast_enough(elapsed, TIMEOUT):
            log(f"❌ {proxy_url} : too slow in basic check ({elapsed:.2f}s)")
            return False

        # --- 実用リクエスト（HTTPS, ヘッダ等の確認）---
        # ここで HTTPS 経路やホスト名解決、ヘッダ返却などの確認を行う
        start2 = time.time()
        resp2 = requests.get("https://httpbin.org/get", proxies=proxies, timeout=TIMEOUT)
        elapsed2 = time.time() - start2
        resp2.raise_for_status()

        # 再度 JSON 構造を確認
        data2 = resp2.json()
        url_field = data2.get("url", "")
        if not url_field:
            log(f"❌ {proxy_url} : /get returned no url field")
            return False

        if not _is_fast_enough(elapsed2, TIMEOUT):
            log(f"❌ {proxy_url} : too slow in functional check ({elapsed2:.2f}s)")
            return False

        # ここまで OK なら実用的に利用可能と判断
        log(f"✅ {proxy_url} ok (basic {elapsed:.2f}s, functional {elapsed2:.2f}s)")
        return True

    except Exception as e:
        # 詳細なデバッグログを残して False を返す
        log(f"❌ {proxy_url} exception: {e}")
        return False


def check_list_parallel(proxy_list, my_ip):
    """
    並列チェックを堅牢化: future.result() の例外を捕まえ、個別のプロキシ評価に失敗しても全体が止まらないようにする。
    """
    if not proxy_list:
        return set()
    alive = set()
    total = len(proxy_list)
    completed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_proxy = {executor.submit(check_proxy, p, my_ip): p for p in proxy_list}
        for future in concurrent.futures.as_completed(future_to_proxy):
            completed += 1
            if completed % 500 == 0 or completed <= 5:
                print(f"   Progress: {completed}/{total} ...")
            proxy = future_to_proxy[future]
            try:
                result = future.result()
            except Exception as e:
                # 将来的な例外に備えて保険的に捕捉（通常 check_proxy は例外を握りつぶす）
                log(f"❌ {proxy} future exception: {e}")
                result = False
            if result:
                alive.add(proxy)
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