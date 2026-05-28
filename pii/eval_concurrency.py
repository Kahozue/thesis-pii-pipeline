#!/usr/bin/env python3
"""
PII Pipeline API 並發效能基準測試 (Concurrency Benchmark)
==========================================================
本腳本啟動 PII API 伺服器 (uvicorn 子行程，port 8505) 後，
以 ThreadPoolExecutor 模擬多用戶並發請求，量測
/api/v1/redact (單文本) 與 /api/v1/redact/batch (批次) 端點
在不同並發數、請求量、文本長度下的效能指標。

啟動方式:
    python eval_concurrency.py

必要套件: fastapi, uvicorn, requests, pipeline (本地模組)

輸出檔案:
    eval_charts/concurrency_raw.json     — 所有測試的原始延遲、QPS、成功率等數據
    eval_charts/concurrency_summary.json — 重點指標彙整表，方便製圖與論文引用
"""
from __future__ import annotations

import json
import math
import os
import signal
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests

# ==============================================================================
# 測試文本定義
# ==============================================================================

# 短文本-中文 (~50 字元): 包含中文姓名、手機號碼、email
SHORT_CN = (
    "你好，我叫王小明，我的電話是0912-345-678，"
    "email 是 wang.xm@example.com，麻煩幫我查一下訂單"
)

# 短文本-英文 (~70 字元): 包含英文姓名、email、電話
SHORT_EN = (
    "Hi, my name is John Smith, you can reach me at john.smith@test.com "
    "or call +44-7911-123456. Thanks!"
)

# 中文本 (Teams 對話, ~350 字元): 來源為 app.py TEMPLATES 之「工程師 Teams 群聊（部署事故）」
MEDIUM_TEAMS = (
    "Kevin 陳彥廷 10:47\n"
    "幹 prod 掛了，剛才 deploy 完直接 500\n\n"
    "Priya Nair 10:48\n"
    "what?? 我還在 review Ryan 的 PR 欸\n\n"
    "Kevin 陳彥廷 10:49\n"
    "先上去看 log，DB password 要換，舊的是 db_pass=Tg7!kQw2#mZ9\n"
    "新的我等等 DM 你\n\n"
    "Priya Nair 10:50\n"
    "你直接貼這邊？？ Kevin...\n\n"
    "Kevin 陳彥廷 10:51\n"
    "shit 對 抱歉\n"
    "另外 AWS key 也順便 rotate 一下：AKIAY3KLM9XPQR72WSVT\n"
    "secret: v8Jn+2oWqTfLmKdR5cXzHbPeNgYsAuI1\n\n"
    "Ryan Wu 10:52\n"
    "哥你快去 revoke 那個 key，我先 rollback"
)


def _make_long_text() -> str:
    """重複 Teams 對話結構 4 次，每次替換不同人名/密碼/金鑰/個資，形成 ~2000 字元長文本"""
    scenes = [
        # 場景 1: Kevin / Priya / Ryan (原始 Teams 對話)
        MEDIUM_TEAMS,
        # 場景 2: Daniel / Nadia — Stripe 金鑰洩漏
        (
            "Daniel 吳承翰 10:53\n"
            "rollback 完成了，但 staging 的 secret 好像也 leak 了\n\n"
            "Nadia Kovač 10:54\n"
            "wait 哪個 secret？我剛 push 了 staging.env 上去...\n\n"
            "Daniel 吳承翰 10:55\n"
            "就是有 DB_URL 那個，裡面有 postgresql://admin:StgP@ss2026!@staging.db.internal/prod\n\n"
            "Nadia Kovač 10:56\n"
            "omg 那個 repo 是 public 的嗎？\n\n"
            "Daniel 吳承翰 10:57\n"
            "對... 而且還有 Stripe 測試 key: sk_test_51JkLmNqXwRtYvZuPcBaTf\n"
            "已經 force push 蓋掉了，但還是要 revoke\n\n"
            "Nadia Kovač 10:58\n"
            "ok 我馬上去 dashboard revoke，email 是 nadia.kovac@startup.io\n\n"
            "Daniel 吳承翰 10:59\n"
            "對，順便 cc 給 security@startup.io，手機 +886-933-112-233"
        ),
        # 場景 3: Ryan / Amy — 客戶個資 CSV 外洩
        (
            "Ryan Wu 11:00\n"
            "我這邊也發現一個問題，customer data CSV 裡面有 real names 跟電話\n\n"
            "客服 Amy 11:01\n"
            "哪個客戶？我剛處理完一筆理賠，保單 LF-2024-887432\n\n"
            "Ryan Wu 11:02\n"
            "客戶黃美華 (huang.mh@gmail.com)，電話 0922-334-445\n"
            "身分證 L123456789，這些在 CSV 裡面完全沒遮\n\n"
            "客服 Amy 11:03\n"
            "這也是個資法問題... 保單號碼 LF-2025-991234 也在同一個 CSV 嗎？\n\n"
            "Ryan Wu 11:04\n"
            "對，還有銀行帳號 700-0123456-789012，持卡人 陳大為\n"
            "我先 pull 下來然後加密，你幫我 notify 法務\n\n"
            "客服 Amy 11:05\n"
            "好，法務 email legal@corp-ins.com，我 cc 你 ryan.wu@corp.com"
        ),
        # 場景 4: 資安團隊 — 憑證外洩通報
        (
            "From: it-security@corp.com\n"
            "To: ciso@corp.com, legal@corp.com\n"
            "Subject: [URGENT] Credential exposure — 初步調查\n\n"
            "CISO 及法務，\n\n"
            "本日 09:14 偵測到 GitHub public repo 中存在明文憑證：\n\n"
            "受影響帳號：陳柏宇 (po-yu.chen@corp.com)\n"
            "洩漏內容：\n"
            "  - AWS_ACCESS_KEY_ID = AKIAWXYZ1234ABCDEFGH\n"
            "  - AWS_SECRET_ACCESS_KEY = wJalrXUtnFEMI/K7MDENG/bPxRfiCYz3+Qk\n"
            "  - DB_URL = postgresql://poyuchen:Chen@1234!@rds.corp.internal/prod\n\n"
            "陳柏宇本人於 09:31 回報已 revoke，但 key 存在時間約 6 小時。\n"
            "目前 IP 38.242.101.77 有異常 API call，已 block。\n"
            "需要法務評估是否觸發個資法通報義務。\n\n"
            "IT Security Team"
        ),
    ]
    return "\n\n".join(scenes)


LONG_TEXT = _make_long_text()

# 短文本池 (用於批次測試): 12 筆不同短文本，避免 API 端快取影響量測
BATCH_TEXT_POOL = [
    SHORT_CN,
    SHORT_EN,
    "請回電給李大明，手機 0912-888-777，email: david.li@company.tw",
    "信用卡號 4532-7890-1234-5678，持卡人 張美玲，到期日 12/28，安全碼 567",
    "護照號碼 B12345678，姓名: 林志偉，出生日期: 1990-05-15，國籍台灣",
    "請聯絡 sara.jones@firm.co.uk，電話 +44-20-7946-0958，帳號 SARAJ01",
    "身分證 F234567890，姓名 吳雅婷，住址 台中市西屯區台灣大道三段 200 號",
    "員工編號 EMP-9999，user: 黃建宏，email: jianhong@startup.tw",
    "API key: sk-proj-abc123def456ghi789jkl，team: devops@org.com",
    "訂單 #ORD-8876，客戶 陳思妤，tel: 0928-111-222，addr: 高雄市前鎮區一心一路",
    "你好我是許文傑，身分證字號 M167890123，聯絡電話 0976-543-210",
    "Hi this is Rachel Green, rachel.g@friends.com, SSN 123-45-6789",
]

# 文本輪替清單 (用於單文本測試，涵蓋不同長度)
TEXT_POOL = [SHORT_CN, SHORT_EN, MEDIUM_TEAMS, LONG_TEXT]

# ==============================================================================
# 設定
# ==============================================================================

# API 伺服器位址
BASE_URL = "http://localhost:8505"
HEALTH_URL = f"{BASE_URL}/api/v1/health"
REDACT_URL = f"{BASE_URL}/api/v1/redact"
BATCH_URL = f"{BASE_URL}/api/v1/redact/batch"
API_PORT = 8505

# 單個 HTTP 請求的逾時時間 (秒)，模型推論可能耗時，保留充足緩衝
REQUEST_TIMEOUT = 120

# 伺服器模型載入等待上限 (秒)
MODEL_LOAD_TIMEOUT = 600

# 健康檢查輪詢間隔 (秒)
HEALTH_POLL_INTERVAL = 3

# ── 單文本測試配置: (並發 workers, 請求數 num_requests) 組合 ──
# 每種組合會將 TEXT_POOL 文本輪替分配給各請求
SINGLE_CONFIGS = [
    {"workers": w, "num_requests": r}
    for w in [1, 2, 4, 8]    # 模擬同時在線用戶數
    for r in [10, 20, 50]    # 總請求量
]

# ── 批次測試配置: (並發 workers, 每 worker 批次請求數, 每批次文本數) ──
BATCH_CONFIGS = [
    {"workers": w, "num_requests": 10, "batch_size": s}
    for w in [1, 2, 4, 8]    # 模擬同時在線用戶數
    for s in [1, 5, 10]      # 每批次含 1/5/10 筆文本
]

# 腳本所在目錄 (api_server.py, pipeline.py 位於同一層)
SCRIPT_DIR = Path(__file__).resolve().parent
CHARTS_DIR = SCRIPT_DIR / "eval_charts"


# ==============================================================================
# 工具函數
# ==============================================================================

def percentile(sorted_data: list[float], p: float) -> float:
    """計算第 p 百分位數 (0 <= p <= 100)，使用線性插值法。

    Args:
        sorted_data: 已排序的數值清單（由小到大）
        p: 百分位，例如 50 代表中位數、95 代表 P95

    Returns:
        插值後的百分位數值；若資料為空則回傳 0.0
    """
    if not sorted_data:
        return 0.0
    n = len(sorted_data)
    k = (p / 100.0) * (n - 1)
    f = int(k)
    c = f + 1 if f + 1 < n else f
    d = k - f
    if d == 0:
        return sorted_data[f]
    return sorted_data[f] + d * (sorted_data[c] - sorted_data[f])


def _compute_latency_stats(latencies: list[float]) -> dict[str, float]:
    """從延遲清單 (單位: 秒) 計算 min/max/avg/p50/p95/p99 (單位: 毫秒)"""
    if not latencies:
        return {"min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}
    sorted_lat = sorted(latencies)
    return {
        "min": round(min(latencies) * 1000, 1),
        "max": round(max(latencies) * 1000, 1),
        "avg": round(statistics.mean(latencies) * 1000, 1),
        "p50": round(percentile(sorted_lat, 50) * 1000, 1),
        "p95": round(percentile(sorted_lat, 95) * 1000, 1),
        "p99": round(percentile(sorted_lat, 99) * 1000, 1),
    }


# ==============================================================================
# 伺服器生命週期管理
# ==============================================================================

def start_server() -> subprocess.Popen | None:
    """啟動 uvicorn 子行程，執行 api_server:app 於 port 8505。

    Returns:
        subprocess.Popen 物件；若無法啟動則回傳 None
    """
    try:
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "api_server:app",
                "--host", "0.0.0.0",
                "--port", str(API_PORT),
                "--log-level", "warning",
            ],
            cwd=str(SCRIPT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"[Benchmark] 啟動 uvicorn 伺服器 (PID={proc.pid})，port={API_PORT}")
        return proc
    except FileNotFoundError:
        print("[Benchmark] 錯誤: 找不到 uvicorn，請確認已安裝 (pip install uvicorn)")
        return None
    except Exception as e:
        print(f"[Benchmark] 錯誤: 無法啟動伺服器: {e}")
        return None


def wait_for_ready(timeout: int = MODEL_LOAD_TIMEOUT) -> bool:
    """輪詢 GET /api/v1/health 直到伺服器狀態為 'ready'。

    Args:
        timeout: 最長等候秒數 (預設 600s = 10 分鐘，OPF 1.5B 模型載入可能較慢)

    Returns:
        True 若伺服器開始回應 ready；False 若逾時
    """
    print(f"[Benchmark] 等待 OPF 模型載入 (最長 {timeout}s)...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(HEALTH_URL, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "")
                if status == "ready":
                    elapsed = timeout - (deadline - time.time())
                    print(f"[Benchmark] 模型已就緒 (模型載入耗時 ~{elapsed:.0f}s)")
                    return True
                print(f"[Benchmark] 伺服器狀態: {status}，繼續等待...")
        except requests.ConnectionError:
            # 伺服器尚未開始監聽
            pass
        except Exception as e:
            print(f"[Benchmark] 健康檢查異常: {e}")
        time.sleep(HEALTH_POLL_INTERVAL)
    print(f"[Benchmark] 錯誤: 模型載入逾時 ({timeout}s)，請檢查伺服器日誌")
    return False


def stop_server(proc: subprocess.Popen | None) -> None:
    """優雅關閉 uvicorn 子行程 (SIGTERM → 等候 → SIGKILL)"""
    if proc is None:
        return
    if proc.poll() is not None:
        print(f"[Benchmark] 伺服器已自行終止 (exit code={proc.returncode})")
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=10)
            print(f"[Benchmark] 伺服器已關閉 (exit code={proc.returncode})")
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            print("[Benchmark] 伺服器已被強制終止 (SIGKILL)")
    except Exception as e:
        print(f"[Benchmark] 關閉伺服器時發生錯誤: {e}")


# ==============================================================================
# 單文本請求 (內部函數，由執行緒池呼叫)
# ==============================================================================

def _single_request(text: str) -> dict[str, Any]:
    """對 /api/v1/redact 發送 POST 請求，量測單次延遲。

    Args:
        text: 待過濾文本

    Returns:
        {"success": bool, "elapsed": float|None, "status": int, "error": str|None}
        elapsed 單位為秒，僅在成功時有意義
    """
    try:
        t0 = time.perf_counter()
        resp = requests.post(
            REDACT_URL,
            json={"text": text, "return_records": False, "return_mapping": False},
            timeout=REQUEST_TIMEOUT,
        )
        elapsed = time.perf_counter() - t0
        return {
            "success": resp.ok,
            "elapsed": elapsed,
            "status": resp.status_code,
            "error": None if resp.ok else f"HTTP {resp.status_code}: {resp.text[:200]}",
        }
    except requests.ConnectionError as e:
        return {"success": False, "elapsed": None, "status": 0, "error": f"ConnectionError: {e}"}
    except requests.Timeout as e:
        return {"success": False, "elapsed": None, "status": 0, "error": f"Timeout: {e}"}
    except Exception as e:
        return {"success": False, "elapsed": None, "status": 0, "error": f"Exception: {type(e).__name__}: {e}"}


# ==============================================================================
# 批次請求 (內部函數，由執行緒池呼叫)
# ==============================================================================

def _batch_request(texts: list[str]) -> dict[str, Any]:
    """對 /api/v1/redact/batch 發送 POST 請求，量測單次批次延遲。

    Args:
        texts: 文本清單 (長度 = batch_size)

    Returns:
        {"success": bool, "elapsed": float|None, "status": int, "batch_size": int, "error": str|None}
    """
    try:
        t0 = time.perf_counter()
        resp = requests.post(
            BATCH_URL,
            json={"texts": texts},
            timeout=REQUEST_TIMEOUT,
        )
        elapsed = time.perf_counter() - t0
        return {
            "success": resp.ok,
            "elapsed": elapsed,
            "status": resp.status_code,
            "batch_size": len(texts),
            "error": None if resp.ok else f"HTTP {resp.status_code}: {resp.text[:200]}",
        }
    except requests.ConnectionError as e:
        return {"success": False, "elapsed": None, "status": 0, "batch_size": len(texts), "error": f"ConnectionError: {e}"}
    except requests.Timeout as e:
        return {"success": False, "elapsed": None, "status": 0, "batch_size": len(texts), "error": f"Timeout: {e}"}
    except Exception as e:
        return {"success": False, "elapsed": None, "status": 0, "batch_size": len(texts), "error": f"Exception: {type(e).__name__}: {e}"}


# ==============================================================================
# 並發測試執行核心
# ==============================================================================

def run_single_concurrent_test(config: dict) -> dict:
    """對 /api/v1/redact 端點執行一組並發測試。

    Args:
        config: {"workers": int, "num_requests": int}

    Returns:
        測試結果 dict，包含 wall_time、延遲分佈、QPS、成功率等
    """
    workers = config["workers"]
    num_requests = config["num_requests"]

    # 輪替分配文本: 確保不同長度的文本均勻出現在請求中
    texts = [TEXT_POOL[i % len(TEXT_POOL)] for i in range(num_requests)]

    pool = ThreadPoolExecutor(max_workers=workers)
    futures = [pool.submit(_single_request, t) for t in texts]

    t_wall_start = time.perf_counter()

    latencies: list[float] = []
    errors: list[dict] = []
    status_codes: dict[int, int] = defaultdict(int)

    for fut in as_completed(futures):
        r = fut.result()
        status_codes[r["status"]] += 1
        if r["success"] and r["elapsed"] is not None:
            latencies.append(r["elapsed"])
        else:
            errors.append(r)

    t_wall_end = time.perf_counter()
    pool.shutdown(wait=True)

    wall_time = t_wall_end - t_wall_start
    n = num_requests
    n_success = len(latencies)
    n_errors = len(errors)

    result = {
        "endpoint": "/api/v1/redact",
        "config": {
            "workers": workers,
            "num_requests": num_requests,
        },
        "text_breakdown": {
            "short_cn_count": texts.count(SHORT_CN),
            "short_en_count": texts.count(SHORT_EN),
            "medium_teams_count": texts.count(MEDIUM_TEAMS),
            "long_count": texts.count(LONG_TEXT),
        },
        "wall_time_s": round(wall_time, 3),
        "total_requests": n,
        "successful_requests": n_success,
        "failed_requests": n_errors,
        "success_rate": round(n_success / n, 4) if n > 0 else 0.0,
        "qps": round(n / wall_time, 2) if wall_time > 0 else 0.0,
        "latency_ms": _compute_latency_stats(latencies),
        "status_code_distribution": {
            str(k): status_codes[k] for k in sorted(status_codes)
        },
    }
    if errors:
        result["error_samples"] = errors[:5]  # 只保留前 5 筆錯誤細節

    return result


def run_batch_concurrent_test(config: dict) -> dict:
    """對 /api/v1/redact/batch 端點執行一組並發測試。

    Args:
        config: {"workers": int, "num_requests": int, "batch_size": int}

    Returns:
        測試結果 dict，包含 wall_time、每批次/每文本延遲、QPS 等
    """
    workers = config["workers"]
    num_requests = config["num_requests"]
    batch_size = config["batch_size"]

    # 每筆批次請求從短文本池中取 batch_size 筆文本 (輪替以避免重複)
    batch_payloads: list[list[str]] = []
    for i in range(num_requests):
        start = (i * batch_size) % len(BATCH_TEXT_POOL)
        batch_texts = []
        for j in range(batch_size):
            idx = (start + j) % len(BATCH_TEXT_POOL)
            batch_texts.append(BATCH_TEXT_POOL[idx])
        batch_payloads.append(batch_texts)

    pool = ThreadPoolExecutor(max_workers=workers)
    futures = [pool.submit(_batch_request, texts) for texts in batch_payloads]

    t_wall_start = time.perf_counter()

    latencies: list[float] = []          # 每批次請求延遲 (秒)
    per_text_latencies: list[float] = [] # 均攤後每文本延遲 (秒): elapsed / batch_size
    errors: list[dict] = []
    status_codes: dict[int, int] = defaultdict(int)

    for fut in as_completed(futures):
        r = fut.result()
        status_codes[r["status"]] += 1
        if r["success"] and r["elapsed"] is not None:
            latencies.append(r["elapsed"])
            # 批次 API 內部是逐筆處理，均攤後約略估計每文本延遲
            actual_batch_size = r.get("batch_size", batch_size)
            if actual_batch_size > 0:
                per_text_latencies.append(r["elapsed"] / actual_batch_size)
        else:
            errors.append(r)

    t_wall_end = time.perf_counter()
    pool.shutdown(wait=True)

    wall_time = t_wall_end - t_wall_start
    n = num_requests
    n_success = len(latencies)
    n_errors = len(errors)
    total_texts = n_success * batch_size  # 成功處理的總文本數

    result = {
        "endpoint": "/api/v1/redact/batch",
        "config": {
            "workers": workers,
            "num_requests": num_requests,
            "batch_size": batch_size,
        },
        "wall_time_s": round(wall_time, 3),
        "total_requests": n,
        "successful_requests": n_success,
        "failed_requests": n_errors,
        "success_rate": round(n_success / n, 4) if n > 0 else 0.0,
        "batch_qps": round(n / wall_time, 2) if wall_time > 0 else 0.0,
        # 等效單文本 QPS: 成功處理的總文本數 / 總牆壁時間
        "equivalent_text_qps": round(total_texts / wall_time, 2) if wall_time > 0 else 0.0,
        "total_texts_processed": total_texts,
        "latency_ms": _compute_latency_stats(latencies),
        "per_text_latency_estimate_ms": _compute_latency_stats(per_text_latencies),
        "status_code_distribution": {
            str(k): status_codes[k] for k in sorted(status_codes)
        },
    }
    if errors:
        result["error_samples"] = errors[:5]

    return result


# ==============================================================================
# 摘要生成
# ==============================================================================

def generate_summary(raw_results: dict) -> dict:
    """從原始測試結果產生重點指標彙整表，用於論文圖表與快速比對。

    Args:
        raw_results: 完整的原始測試結果 dict，包含 "single_text" 與 "batch" 兩區

    Returns:
        摘要 dict，包含各維度的對比表
    """
    summary: dict[str, Any] = {
        "title": "PII Pipeline API 並發效能基準測試摘要",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "test_environment": {
            "server_port": API_PORT,
            "single_text_configs": SINGLE_CONFIGS,
            "batch_configs": BATCH_CONFIGS,
            "text_pool_lengths": {
                "short_cn": len(SHORT_CN),
                "short_en": len(SHORT_EN),
                "medium_teams": len(MEDIUM_TEAMS),
                "long_text": len(LONG_TEXT),
            },
        },
    }

    # ── 單文本摘要 ──
    single_tests = raw_results.get("single_text", [])
    single_table: list[dict] = []
    for t in single_tests:
        cfg = t["config"]
        lat = t["latency_ms"]
        single_table.append({
            "workers": cfg["workers"],
            "num_requests": cfg["num_requests"],
            "wall_time_s": t["wall_time_s"],
            "qps": t["qps"],
            "success_rate": t["success_rate"],
            "avg_latency_ms": lat["avg"],
            "p50_latency_ms": lat["p50"],
            "p95_latency_ms": lat["p95"],
            "p99_latency_ms": lat["p99"],
            "min_latency_ms": lat["min"],
            "max_latency_ms": lat["max"],
        })
    summary["single_text"] = {
        "full_table": single_table,
    }

    # 依 workers 分組平均
    for group_name, group_key in [("by_workers", "workers"), ("by_num_requests", "num_requests")]:
        grouped: dict[int, list[dict]] = defaultdict(list)
        for t in single_tests:
            grouped[t["config"][group_key]].append(t)
        group_summary = []
        for key in sorted(grouped):
            items = grouped[key]
            avg_qps = statistics.mean(it["qps"] for it in items)
            avg_lat = statistics.mean(it["latency_ms"]["avg"] for it in items)
            avg_p95 = statistics.mean(it["latency_ms"]["p95"] for it in items)
            group_summary.append({
                group_key: key,
                "test_count": len(items),
                "avg_qps": round(avg_qps, 2),
                "avg_latency_ms": round(avg_lat, 1),
                "avg_p95_latency_ms": round(avg_p95, 1),
            })
        summary["single_text"][group_name] = group_summary

    # ── 批次摘要 ──
    batch_tests = raw_results.get("batch", [])
    batch_table: list[dict] = []
    for t in batch_tests:
        cfg = t["config"]
        lat = t["latency_ms"]
        batch_table.append({
            "workers": cfg["workers"],
            "num_requests": cfg["num_requests"],
            "batch_size": cfg["batch_size"],
            "wall_time_s": t["wall_time_s"],
            "batch_qps": t["batch_qps"],
            "equivalent_text_qps": t["equivalent_text_qps"],
            "success_rate": t["success_rate"],
            "avg_batch_latency_ms": lat["avg"],
            "p50_batch_latency_ms": lat["p50"],
            "p95_batch_latency_ms": lat["p95"],
            "total_texts_processed": t["total_texts_processed"],
        })
    summary["batch"] = {
        "full_table": batch_table,
    }

    # 依 batch_size 分組
    bs_grouped: dict[int, list[dict]] = defaultdict(list)
    for t in batch_tests:
        bs_grouped[t["config"]["batch_size"]].append(t)
    bs_summary = []
    for bs in sorted(bs_grouped):
        items = bs_grouped[bs]
        avg_eq_qps = statistics.mean(it["equivalent_text_qps"] for it in items)
        avg_lat = statistics.mean(it["latency_ms"]["avg"] for it in items)
        bs_summary.append({
            "batch_size": bs,
            "test_count": len(items),
            "avg_equivalent_text_qps": round(avg_eq_qps, 2),
            "avg_batch_latency_ms": round(avg_lat, 1),
        })
    summary["batch"]["by_batch_size"] = bs_summary

    return summary


# ==============================================================================
# 主程式
# ==============================================================================

def main() -> int:
    """主程式: 啟動伺服器 → 執行所有並發測試 → 儲存結果 → 關閉伺服器"""
    print("=" * 70)
    print("  PII Pipeline API 並發效能基準測試 (Concurrency Benchmark)")
    print("=" * 70)
    print(f"  單文本測試配置數: {len(SINGLE_CONFIGS)}")
    print(f"  批次測試配置數:   {len(BATCH_CONFIGS)}")
    print(f"  API port:          {API_PORT}")
    print(f"  輸出目錄:          {CHARTS_DIR}")
    print("=" * 70)

    # 確儲輸出目錄存在
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. 啟動伺服器 ──
    server_proc = start_server()
    if server_proc is None:
        return 1

    # 確保腳本結束時關閉伺服器 (含 Ctrl-C)
    # 使用函數內部的 cleanup 旗標避免重複關閉
    _cleanup_done = False

    def _cleanup():
        nonlocal _cleanup_done
        if not _cleanup_done:
            _cleanup_done = True
            stop_server(server_proc)

    import atexit
    atexit.register(_cleanup)

    # SIGINT / SIGTERM 處理
    def _signal_handler(signum, frame):
        print(f"\n[Benchmark] 收到信號 {signum}，正在清理...")
        _cleanup()
        sys.exit(1)

    original_sigint = signal.signal(signal.SIGINT, _signal_handler)
    original_sigterm = signal.signal(signal.SIGTERM, _signal_handler)

    # ── 2. 等待模型載入 ──
    if not wait_for_ready():
        _cleanup()
        return 1

    # ── 3. 執行並發測試 ──
    raw_results: dict[str, list] = {
        "meta": {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "api_base_url": BASE_URL,
            "request_timeout_s": REQUEST_TIMEOUT,
        },
        "single_text": [],
        "batch": [],
    }

    # 3a. 單文本測試
    print("\n" + "-" * 70)
    print("  [Phase 1] 單文本端點 (/api/v1/redact) 並發測試")
    print("-" * 70)

    for i, cfg in enumerate(SINGLE_CONFIGS, 1):
        w = cfg["workers"]
        r = cfg["num_requests"]
        print(f"  [{i}/{len(SINGLE_CONFIGS)}] workers={w}, requests={r} ... ", end="", flush=True)
        try:
            result = run_single_concurrent_test(cfg)
            raw_results["single_text"].append(result)
            lat = result["latency_ms"]
            print(
                f"done | wall={result['wall_time_s']}s | "
                f"QPS={result['qps']} | "
                f"success={result['success_rate']:.1%} | "
                f"avg={lat['avg']}ms | p95={lat['p95']}ms | p99={lat['p99']}ms"
            )
        except Exception as e:
            print(f"FAILED: {e}")
            raw_results["single_text"].append({
                "config": cfg,
                "error": str(e),
                "wall_time_s": 0,
                "qps": 0,
            })

    # 3b. 批次測試
    print("\n" + "-" * 70)
    print("  [Phase 2] 批次端點 (/api/v1/redact/batch) 並發測試")
    print("-" * 70)

    for i, cfg in enumerate(BATCH_CONFIGS, 1):
        w = cfg["workers"]
        bs = cfg["batch_size"]
        print(f"  [{i}/{len(BATCH_CONFIGS)}] workers={w}, batch_size={bs} ... ", end="", flush=True)
        try:
            result = run_batch_concurrent_test(cfg)
            raw_results["batch"].append(result)
            lat = result["latency_ms"]
            eq_qps = result["equivalent_text_qps"]
            print(
                f"done | wall={result['wall_time_s']}s | "
                f"batch_QPS={result['batch_qps']} | eq_text_QPS={eq_qps} | "
                f"success={result['success_rate']:.1%} | "
                f"avg_batch={lat['avg']}ms | p95_batch={lat['p95']}ms"
            )
        except Exception as e:
            print(f"FAILED: {e}")
            raw_results["batch"].append({
                "config": cfg,
                "error": str(e),
                "wall_time_s": 0,
            })

    # ── 4. 儲存原始結果 ──
    raw_path = CHARTS_DIR / "concurrency_raw.json"
    print(f"\n[Benchmark] 儲存原始結果至 {raw_path}")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw_results, f, ensure_ascii=False, indent=2)

    # ── 5. 生成摘要 ──
    summary = generate_summary(raw_results)
    summary_path = CHARTS_DIR / "concurrency_summary.json"
    print(f"[Benchmark] 儲存摘要至 {summary_path}")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # ── 6. 關閉伺服器 ──
    print()
    _cleanup()

    # 恢復原始信號處理
    signal.signal(signal.SIGINT, original_sigint)
    signal.signal(signal.SIGTERM, original_sigterm)

    # ── 7. 輸出最終摘要 ──
    print("\n" + "=" * 70)
    print("  測試完成 — 重點摘要")
    print("=" * 70)

    single_tests = raw_results.get("single_text", [])
    if single_tests:
        all_qps = [t["qps"] for t in single_tests if t.get("qps", 0) > 0]
        all_avg = [t["latency_ms"]["avg"] for t in single_tests if "latency_ms" in t]
        print(f"  單文本端點: {len(single_tests)} 組測試完成")
        if all_qps:
            print(f"    QPS 範圍: {min(all_qps):.2f} ~ {max(all_qps):.2f}")
        if all_avg:
            print(f"    平均延遲範圍: {min(all_avg):.1f}ms ~ {max(all_avg):.1f}ms")

    batch_tests = raw_results.get("batch", [])
    if batch_tests:
        all_eq_qps = [t["equivalent_text_qps"] for t in batch_tests if t.get("equivalent_text_qps", 0) > 0]
        print(f"  批次端點: {len(batch_tests)} 組測試完成")
        if all_eq_qps:
            print(f"    等效文本 QPS 範圍: {min(all_eq_qps):.2f} ~ {max(all_eq_qps):.2f}")

    print(f"\n  原始數據: {raw_path}")
    print(f"  摘要數據: {summary_path}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
