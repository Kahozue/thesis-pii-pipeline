"""compare_3v5.py

讀舊版 summary_v3.json(三分法備份)與新版 summary.json(五分法),
並排輸出對照表。
"""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).parent
V3_PATH = BASE / "summary_v3.json"
V5_PATH = BASE / "summary.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def get_sample_field(samples: list[dict], sid: str, field: str, default="-"):
    for s in samples:
        if s["sample_id"] == sid:
            val = s.get(field, default)
            if val is None:
                return default
            return val
    return default


def fmt(val, decimals=3):
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    return str(val)


def main():
    if not V3_PATH.exists():
        print(f"ERROR: {V3_PATH} 不存在，請先備份舊版 summary.json 為 summary_v3.json。")
        return
    if not V5_PATH.exists():
        print(f"ERROR: {V5_PATH} 不存在，請先執行新版實驗。")
        return

    v3 = load(V3_PATH)
    v5 = load(V5_PATH)

    v3_samples = v3.get("samples", [])
    v5_samples = v5.get("samples", [])

    all_ids = sorted(set(
        [s["sample_id"] for s in v3_samples] +
        [s["sample_id"] for s in v5_samples]
    ))

    # 欄位寬度
    col_widths = [10, 10, 10, 10, 10, 14, 12]
    headers = ["sample", "risk_v3", "risk_v5", "consist_v3", "consist_v5", "adj_consist_v5", "score_std_v5"]

    sep = "  ".join("-" * w for w in col_widths)
    header_str = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))

    print(header_str)
    print(sep)

    consist_v3_vals = []
    consist_v5_vals = []
    adj_vals = []
    std_vals = []

    for sid in all_ids:
        risk_v3 = get_sample_field(v3_samples, sid, "majority_risk")
        risk_v5 = get_sample_field(v5_samples, sid, "majority_risk")
        consist_v3 = get_sample_field(v3_samples, sid, "risk_consistency")
        consist_v5 = get_sample_field(v5_samples, sid, "risk_consistency")
        adj_v5 = get_sample_field(v5_samples, sid, "risk_adjacent_consistency")
        std_v5 = get_sample_field(v5_samples, sid, "score_std")

        row = [
            sid,
            str(risk_v3),
            str(risk_v5),
            fmt(consist_v3) if isinstance(consist_v3, float) else str(consist_v3),
            fmt(consist_v5) if isinstance(consist_v5, float) else str(consist_v5),
            fmt(adj_v5) if isinstance(adj_v5, float) else str(adj_v5),
            fmt(std_v5) if isinstance(std_v5, float) else str(std_v5),
        ]
        print("  ".join(v.ljust(w) for v, w in zip(row, col_widths)))

        if isinstance(consist_v3, float):
            consist_v3_vals.append(consist_v3)
        if isinstance(consist_v5, float):
            consist_v5_vals.append(consist_v5)
        if isinstance(adj_v5, float):
            adj_vals.append(adj_v5)
        if isinstance(std_v5, float):
            std_vals.append(std_v5)

    print(sep)

    def safe_mean(lst):
        return sum(lst) / len(lst) if lst else 0.0

    overall_row = [
        "overall mean",
        "-",
        "-",
        fmt(safe_mean(consist_v3_vals)),
        fmt(safe_mean(consist_v5_vals)),
        fmt(safe_mean(adj_vals)),
        fmt(safe_mean(std_vals)),
    ]
    print("  ".join(v.ljust(w) for v, w in zip(overall_row, col_widths)))

    print()
    print(f"[v3 summary] mean_risk_consistency={v3.get('mean_risk_consistency')}  "
          f"mean_id_jaccard={v3.get('mean_id_jaccard')}  "
          f"mean_reason_cosine={v3.get('mean_reason_cosine')}  "
          f"mean_anomaly_rate={v3.get('mean_anomaly_rate')}")
    print(f"[v5 summary] mean_risk_consistency={v5.get('mean_risk_consistency')}  "
          f"mean_id_jaccard={v5.get('mean_id_jaccard')}  "
          f"mean_reason_cosine={v5.get('mean_reason_cosine')}  "
          f"mean_anomaly_rate={v5.get('mean_anomaly_rate')}")
    print(f"[v5 新增]    mean_risk_adjacent_consistency={v5.get('mean_risk_adjacent_consistency')}  "
          f"mean_score_std={v5.get('mean_score_std')}  "
          f"mean_score_mae={v5.get('mean_score_mae')}")


if __name__ == "__main__":
    main()
