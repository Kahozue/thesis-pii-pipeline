"""一致性驗證實驗(Graph API Schema 版,五分法)。

流程:
1. 載入 6 組 Graph API ChatMessage 樣本(A/B/C 來自 Mock dataset,D/E/F 為自製但符合 Schema)。
2. 對每一樣本,執行 N 次獨立 LLM 呼叫(每次新建 OpenAI client,不保留歷史對話),取得 JSON 結構化判讀。
3. 解析輸出,儲存原始 raw 回應與解析後 parsed 結果至 CSV。
4. 計算:
   (a) 風險等級一致率(多數決之吻合率)
   (b) 關鍵訊息定位 Jaccard 相似度(所有 N 次配對之平均)
   (c) 判讀理由語意相似度(text-embedding-3-small 向量兩兩 cosine 平均)
   (d) 異常判讀率(JSON 解析失敗 or 與多數決風險等級不一致之次數)
   (e) 相鄰等級容忍一致率(序數差 ≤ 1 視為一致)
   (f) risk_score 標準差(N 次分數)
   (g) risk_score MAE(所有配對之平均絕對差)
5. 輸出總表 metrics.csv 與統計摘要 summary.json。

執行前請設定環境變數 OPENAI_API_KEY。
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from itertools import combinations
from pathlib import Path
from statistics import mean, stdev

from openai import OpenAI

BASE = Path(__file__).parent
MOCK_PATH = BASE.parent / "Mock_SocialEngineering_Dataset.json"
CUSTOM_PATH = BASE / "custom_samples.json"

# ----- 控制變數(務必於論文中如實記錄) -----
MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"
TEMPERATURE = 0.2
MAX_TOKENS = 1200
TOP_P = 1.0
N_RUNS = 5
SEED = None  # 刻意不設 seed,以觀察原生分佈

# 五級風險序數映射
RISK_ORDINAL = {
    "Critical": 4,
    "High": 3,
    "Mid": 2,
    "Low": 1,
    "Minimal": 0,
}

SYSTEM_PROMPT = (
    "你是企業資安分析員,負責從 Microsoft Teams 聊天紀錄(符合 Microsoft Graph API v1.0 ChatMessage schema 之 JSON)"
    "判讀是否存在社交工程風險。\n"
    "請依下列規則輸出 JSON(不可含 markdown code fence):\n"
    "{\n"
    "  \"risk_level\": \"Critical\" | \"High\" | \"Mid\" | \"Low\" | \"Minimal\",\n"
    "  \"risk_score\": <整數 0-10>,\n"
    "  \"threat_message_ids\": [\"<chatMessage.id>\", ...],\n"
    "  \"reason\": \"以繁體中文台灣用語,條列三至五個關鍵判讀依據,單一段落內以分號分隔\"\n"
    "}\n"
    "判讀原則:\n"
    "- Critical：明確惡意行動已啟動（資金已轉、憑證已洩露、MFA 已繞過），無法挽回或立即高危。\n"
    "- High：明確釣魚、假冒身分、BEC、惡意連結、資金/憑證誘導，但尚未成功；對方明確回絕後仍持續施壓。\n"
    "- Mid：具可疑徵兆但尚未觸發核心誘導（例如供應商帳戶變更但尚未匯款），或一方質疑後無具體結果。\n"
    "- Low：輕微疑慮，如輕度試探性提問，但無直接誘導或異常施壓。\n"
    "- Minimal：純日常工作溝通，無任何社交工程跡象。\n"
    "分數映射（LLM 參考）：Critical=9–10, High=7–8, Mid=4–6, Low=2–3, Minimal=0–1。\n"
    "threat_message_ids 僅列出具體構成威脅的訊息 id(來自 JSON 欄位 id),若為 Low 或 Minimal 可為空陣列。"
)


def load_samples() -> dict[str, dict]:
    mock = json.loads(MOCK_PATH.read_text(encoding="utf-8"))
    custom = json.loads(CUSTOM_PATH.read_text(encoding="utf-8"))
    result: dict[str, dict] = {}
    for sid, s in mock["scenarios"].items():
        result[sid] = {"source": "mock_dataset (另一 agent 產出)", "payload": s}
    for sid, s in custom["scenarios"].items():
        result[sid] = {"source": "self-made (符合 Graph API Schema,明確標註為自製)", "payload": s}
    return result


def build_user_prompt(sample_json: dict) -> str:
    payload = json.dumps(sample_json, ensure_ascii=False)
    return (
        "以下為單一 Microsoft Teams chat 之 chatMessage 陣列 JSON(Graph API v1.0 格式),"
        "請依系統提示輸出 JSON 判讀:\n" + payload
    )


def single_call(api_key: str, sample_json: dict) -> tuple[str, dict | None]:
    """每次新建 client;messages 僅含 system + user,不帶歷史,等同於 session 清空。"""
    client = OpenAI(api_key=api_key)
    rsp = client.chat.completions.create(
        model=MODEL,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        max_tokens=MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(sample_json)},
        ],
    )
    raw = rsp.choices[0].message.content or ""
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    return raw, parsed


def embed(client: OpenAI, text: str) -> list[float]:
    rsp = client.embeddings.create(model=EMBEDDING_MODEL, input=text[:6000])
    return rsp.data[0].embedding


def cosine(a: list[float], b: list[float]) -> float:
    s = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return s / (na * nb) if na and nb else 0.0


def jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    return len(set_a & set_b) / len(union) if union else 1.0


def majority(items: list[str]) -> tuple[str, float]:
    counts: dict[str, int] = {}
    for x in items:
        counts[x] = counts.get(x, 0) + 1
    top = max(counts.items(), key=lambda kv: kv[1])
    return top[0], top[1] / len(items)


def risk_adjacent_consistency(risk_levels: list[str]) -> float:
    """計算相鄰等級容忍一致率：序數差 <= 1 視為容忍一致，返回所有配對中容忍一致的比例。"""
    valid = [r for r in risk_levels if r in RISK_ORDINAL]
    if len(valid) < 2:
        return 0.0
    pairs = list(combinations(valid, 2))
    tolerant = sum(1 for a, b in pairs if abs(RISK_ORDINAL[a] - RISK_ORDINAL[b]) <= 1)
    return tolerant / len(pairs)


def score_std(scores: list[int | float]) -> float:
    """N 次 risk_score 之標準差；N<2 回傳 0.0。"""
    valid = [s for s in scores if isinstance(s, (int, float))]
    if len(valid) < 2:
        return 0.0
    return stdev(valid)


def score_mae(scores: list[int | float]) -> float:
    """所有配對 |score_i - score_j| 之平均。"""
    valid = [s for s in scores if isinstance(s, (int, float))]
    if len(valid) < 2:
        return 0.0
    pairs = list(combinations(valid, 2))
    return mean(abs(a - b) for a, b in pairs)


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: 環境變數 OPENAI_API_KEY 未設定", file=sys.stderr)
        sys.exit(1)

    samples = load_samples()
    raw_rows = []
    sample_metrics = []
    emb_client = OpenAI(api_key=api_key)

    for sid in sorted(samples.keys()):
        info = samples[sid]
        payload = info["payload"]
        print(f"[{sid}] running {N_RUNS} times...")
        run_results = []
        for i in range(N_RUNS):
            raw, parsed = single_call(api_key, payload)
            ok = parsed is not None and all(
                k in parsed for k in ("risk_level", "risk_score", "threat_message_ids", "reason")
            )
            risk = parsed.get("risk_level") if ok else ""
            rscore = parsed.get("risk_score") if ok else None
            ids = parsed.get("threat_message_ids", []) if ok else []
            reason = parsed.get("reason", "") if ok else ""
            run_results.append({
                "ok": ok, "risk": risk, "risk_score": rscore,
                "ids": ids, "reason": reason, "raw": raw,
            })
            raw_rows.append({
                "sample_id": sid,
                "run_index": i + 1,
                "json_ok": int(ok),
                "risk_level": risk,
                "risk_score": rscore if rscore is not None else "",
                "threat_ids": "|".join(ids) if isinstance(ids, list) else str(ids),
                "reason": reason,
                "raw": raw,
            })
            time.sleep(0.4)

        # --- 指標 ---
        # (a) 風險等級一致率 = 多數決占比
        risks = [r["risk"] for r in run_results if r["ok"]]
        if risks:
            majority_risk, risk_consistency = majority(risks)
        else:
            majority_risk, risk_consistency = "", 0.0

        # (b) 訊息 id Jaccard 兩兩平均
        id_sets = [set(r["ids"]) for r in run_results if r["ok"]]
        if len(id_sets) >= 2:
            jac = mean(jaccard(a, b) for a, b in combinations(id_sets, 2))
        else:
            jac = 0.0

        # (c) 理由語意相似度(兩兩 cosine 平均)
        reasons = [r["reason"] for r in run_results if r["ok"] and r["reason"]]
        if len(reasons) >= 2:
            vecs = [embed(emb_client, t) for t in reasons]
            cos = mean(cosine(a, b) for a, b in combinations(vecs, 2))
        else:
            cos = 0.0

        # (d) 異常判讀率 = (非多數決風險 + JSON 失敗) / N
        anomalies = sum(1 for r in run_results if (not r["ok"]) or r["risk"] != majority_risk)
        anomaly_rate = anomalies / N_RUNS

        # (e) 相鄰等級容忍一致率
        adj_consistency = risk_adjacent_consistency(risks)

        # (f) risk_score 標準差
        rscores = [r["risk_score"] for r in run_results if r["ok"] and r["risk_score"] is not None]
        s_std = score_std(rscores)

        # (g) risk_score MAE
        s_mae = score_mae(rscores)

        sample_metrics.append({
            "sample_id": sid,
            "source": info["source"],
            "n_runs": N_RUNS,
            "majority_risk": majority_risk,
            "risk_consistency": round(risk_consistency, 4),
            "id_jaccard_mean": round(jac, 4),
            "reason_cosine_mean": round(cos, 4),
            "anomaly_rate": round(anomaly_rate, 4),
            "risk_adjacent_consistency": round(adj_consistency, 4),
            "score_std": round(s_std, 4),
            "score_mae": round(s_mae, 4),
            "risk_scores": rscores,
        })

    # --- 寫檔 ---
    with (BASE / "raw_outputs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "sample_id", "run_index", "json_ok", "risk_level", "risk_score",
            "threat_ids", "reason", "raw",
        ])
        w.writeheader()
        w.writerows(raw_rows)

    with (BASE / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "sample_id", "source", "n_runs", "majority_risk",
            "risk_consistency", "id_jaccard_mean", "reason_cosine_mean", "anomaly_rate",
            "risk_adjacent_consistency", "score_std", "score_mae",
        ])
        w.writeheader()
        for row in sample_metrics:
            # 寫 CSV 時不含 risk_scores list
            w.writerow({k: v for k, v in row.items() if k != "risk_scores"})

    agg = {
        "model": MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "n_runs_per_sample": N_RUNS,
        "mean_risk_consistency": round(mean(r["risk_consistency"] for r in sample_metrics), 4),
        "mean_id_jaccard": round(mean(r["id_jaccard_mean"] for r in sample_metrics), 4),
        "mean_reason_cosine": round(mean(r["reason_cosine_mean"] for r in sample_metrics), 4),
        "mean_anomaly_rate": round(mean(r["anomaly_rate"] for r in sample_metrics), 4),
        "mean_risk_adjacent_consistency": round(
            mean(r["risk_adjacent_consistency"] for r in sample_metrics), 4
        ),
        "mean_score_std": round(mean(r["score_std"] for r in sample_metrics), 4),
        "mean_score_mae": round(mean(r["score_mae"] for r in sample_metrics), 4),
        "samples": sample_metrics,
    }
    (BASE / "summary.json").write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(agg, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
