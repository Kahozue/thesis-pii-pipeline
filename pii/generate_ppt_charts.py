"""
Generate PPT-ready charts from system performance evaluation.
Focus: deployment feasibility, not NLP benchmark.
"""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUMMARY = HERE / "eval_charts" / "eval_summary.json"
RAW = HERE / "eval_charts" / "eval_raw.json"
CONCURRENCY = HERE / "eval_charts" / "concurrency_summary.json"
OUT_DIR = HERE / "eval_charts"


def load_data():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    concurrency = None
    if CONCURRENCY.exists():
        concurrency = json.loads(CONCURRENCY.read_text(encoding="utf-8"))
    return summary, raw, concurrency


def setup_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    cjk = ["PingFang TC", "Noto Sans CJK TC", "Heiti TC", "STHeiti", "Arial Unicode MS"]
    for fname in cjk:
        for f in fm.fontManager.ttflist:
            if f.name == fname:
                plt.rcParams["font.sans-serif"] = [fname] + cjk
                break
        else:
            continue
        break
    plt.rcParams.update({"font.family": "sans-serif", "axes.unicode_minus": False,
                         "figure.dpi": 150, "savefig.dpi": 150,
                         "savefig.bbox": "tight", "savefig.pad_inches": 0.15})
    return plt


# ══════════════════════════════════════════════════════════════════════════════
# Chart 1: System Performance Dashboard (load time + memory + cold/warm)
# ══════════════════════════════════════════════════════════════════════════════

def chart_system_dashboard(plt, summary):
    h = summary["headline"]
    load = summary["load"]
    warmup = summary["warmup"]

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))

    # Left: Model load
    ax = axes[0]
    hw_info = summary.get("hardware", {})
    hw_label = f"{hw_info.get('cpu', 'Unknown')} ({hw_info.get('ram_total_gb', '?')}GB)"
    ax.text(0.5, 0.9, hw_label, transform=ax.transAxes, ha="center", fontsize=9, color="#808080")
    ax.text(0.5, 0.8, f"載入耗時: {load['load_time_seconds']}s", transform=ax.transAxes, ha="center", fontsize=13, fontweight="bold", color="#0a72ef")
    ax.text(0.5, 0.65, f"Process VMS (含mmap): {load['proc_vms_delta_mb']:.0f} MB Δ", transform=ax.transAxes, ha="center", fontsize=10)
    ax.text(0.5, 0.55, f"System RAM Δ: {load['system_ram_delta_gb']:.2f} GB", transform=ax.transAxes, ha="center", fontsize=10)
    mem_obs = h.get("External_iStats_obs_GB", f'{load["system_ram_delta_gb"]:.2f} GB')
    ax.text(0.5, 0.45, f"記憶體佔用: {mem_obs}", transform=ax.transAxes, ha="center", fontsize=10, fontweight="bold", color="#ff5b4f")
    ax.text(0.5, 0.35, f"模型權重: 1.5B params BF16 (~3GB)", transform=ax.transAxes, ha="center", fontsize=9, color="#808080")
    ax.set_title("模型部署規格", fontsize=12, fontweight="bold")
    ax.axis("off")

    # Middle: Cold vs Warm
    ax = axes[1]
    colors_warmup = ["#ff5b4f", "#0a72ef"] + ["#c8daf5"] * (len(warmup["all_times_ms"]) - 1)
    ax.bar(range(len(warmup["all_times_ms"])), warmup["all_times_ms"], color=colors_warmup, alpha=0.85)
    ax.axhline(y=warmup["warm_avg_ms"], color="#0a72ef", linestyle="--", linewidth=1,
               label=f'Warm avg: {warmup["warm_avg_ms"]:.0f}ms')
    ax.set_title(f"Cold/Warm 推論 ({warmup['cold_warm_ratio']}x 差距)", fontsize=12, fontweight="bold")
    ax.set_xlabel("推論次數", fontsize=9)
    ax.set_ylabel("延遲 (ms)", fontsize=10)
    ax.legend(fontsize=9, loc="upper right")

    # Right: Key metrics summary
    ax = axes[2]
    h = summary["headline"]
    lines = [
        f"每千字推論: {h['每千字推論時間_ms']:.0f}ms",
        f"字數時間 R²: {h['字數時間R²']:.3f}",
        f"整體 F1: {h['整體F1']:.1%}",
        f"Negative FP: {h['Negative_FP_rate']:.4f}",
    ]
    for i, line in enumerate(lines):
        ax.text(0.5, 0.85 - i * 0.15, line, ha="center", fontsize=13, fontweight="bold", color="#171717",
                transform=ax.transAxes)
    ax.set_title("關鍵效能指標", fontsize=12, fontweight="bold")
    ax.axis("off")

    fig.suptitle("System Performance Dashboard — 部署可行性評估", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "chart_system_dashboard.png")
    plt.close(fig)
    print("  [OK] chart_system_dashboard.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 2: Char-Time Correlation (scatter + regression)
# ══════════════════════════════════════════════════════════════════════════════

def chart_char_time(plt, summary, raw):
    # Extract all (chars, time) pairs from raw data (first run only)
    points = []
    for r in raw["results"]:
        if r["run_index"] == 0:
            points.append((r["text_length"], r["inference_ms"], r["group"], r["id"]))

    reg = summary["char_time_regression"]
    buckets = summary["char_time_buckets"]

    fig, ax = plt.subplots(figsize=(10, 6.5))

    group_colors = {"SHORT": "#0a72ef", "MEDIUM": "#de1d8d", "LONG": "#ff5b4f",
                    "ORAL": "#166534", "STRUCT": "#6d28d9", "MULTI": "#0e7490", "NEGATIVE": "#808080"}
    group_markers = {"SHORT": "o", "MEDIUM": "s", "LONG": "^", "ORAL": "D", "STRUCT": "X", "MULTI": "P", "NEGATIVE": "v"}

    for g in set(p[2] for p in points):
        g_pts = [(x, y) for x, y, grp, _ in points if grp == g]
        ax.scatter([x for x, _ in g_pts], [y for _, y in g_pts],
                   c=group_colors.get(g, "#333"), marker=group_markers.get(g, "o"),
                   label=g, alpha=0.7, s=50, edgecolors="white", linewidth=0.5)

    # Regression line
    x_vals = [p[0] for p in points]
    if x_vals:
        slope = reg["slope_ms_per_char"]
        intercept = reg["intercept_ms"]
        x_line = [0, max(x_vals) * 1.05]
        y_line = [intercept, slope * x_line[1] + intercept]
        ax.plot(x_line, y_line, "--", color="#171717", linewidth=2, alpha=0.6,
                label=f'R²={reg["r_squared"]:.3f} ({slope:.1f}ms/char)')

    ax.set_xlabel("文本長度 (字元數)", fontsize=11, fontweight="bold")
    ax.set_ylabel("推論時間 (ms)", fontsize=11, fontweight="bold")
    ax.set_title(f"字數-時間線性關聯 (R²={reg['r_squared']:.3f})", fontsize=13, fontweight="bold", pad=15)
    ax.legend(fontsize=8, loc="lower right", ncol=2, framealpha=0.9)
    ax.grid(alpha=0.2)

    # Bucket labels
    bucket_annotation = "  ".join([
        f"{b}: {d['avg_ms']:.0f}ms" for b, d in buckets.items()
    ])
    ax.text(0.5, -0.12, f"字數區間平均: {bucket_annotation}",
            transform=ax.transAxes, ha="center", fontsize=8, color="#808080")

    fig.tight_layout()
    fig.savefig(OUT_DIR / "chart_char_time.png")
    plt.close(fig)
    print("  [OK] chart_char_time.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 3: Per-Group Performance (F1 + Time bar chart)
# ══════════════════════════════════════════════════════════════════════════════

def chart_group_performance(plt, summary):
    groups = summary["per_group"]
    group_order = ["SHORT", "MEDIUM", "LONG", "ORAL", "STRUCT", "MULTI", "NEGATIVE"]

    names = [groups[g]["name"] for g in group_order if g in groups]
    f1_vals = [groups[g]["f1"] * 100 for g in group_order if g in groups]
    times = [groups[g]["avg_inference_ms"] for g in group_order if g in groups]
    counts = [groups[g]["count"] for g in group_order if g in groups]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: F1
    colors_f1 = []
    for f in f1_vals:
        if f >= 80: colors_f1.append("#166534")
        elif f >= 65: colors_f1.append("#0a72ef")
        elif f >= 50: colors_f1.append("#de1d8d")
        else: colors_f1.append("#ff5b4f")

    bars = ax1.barh(range(len(names)), f1_vals, color=colors_f1, alpha=0.85, height=0.6)
    for bar, f, c in zip(bars, f1_vals, counts):
        ax1.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                 f"{f:.1f}% (n={c})", va="center", fontsize=10, fontweight="bold")
    ax1.set_yticks(range(len(names)))
    ax1.set_yticklabels(names, fontsize=11)
    ax1.set_xlabel("F1 Score (%)", fontsize=10, fontweight="bold")
    ax1.set_title("各類別偵測成功率", fontsize=12, fontweight="bold")
    ax1.set_xlim(0, 115)
    ax1.invert_yaxis()
    ax1.grid(axis="x", alpha=0.2)

    # Right: Time
    ax2.barh(range(len(names)), times, color="#0a72ef", alpha=0.85, height=0.6)
    for i, t in enumerate(times):
        ax2.text(t + 30, i, f"{t:.0f}ms", va="center", fontsize=10, fontweight="bold")
    ax2.set_yticks(range(len(names)))
    ax2.set_yticklabels(names, fontsize=11)
    ax2.set_xlabel("平均推論時間 (ms)", fontsize=10, fontweight="bold")
    ax2.set_title("各類別推論時間", fontsize=12, fontweight="bold")
    ax2.invert_yaxis()
    ax2.grid(axis="x", alpha=0.2)

    fig.suptitle("各測試類別效能比較 — 成功率 vs 推論時間", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "chart_group_performance.png")
    plt.close(fig)
    print("  [OK] chart_group_performance.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 4: Language Challenge Matrix
# ══════════════════════════════════════════════════════════════════════════════

def chart_language_challenge(plt, summary):
    lang = summary["per_language"]

    fig, ax = plt.subplots(figsize=(8, 5.5))
    langs = list(lang.keys())
    f1_scores = [lang[l]["f1"] * 100 for l in langs]
    times = [lang[l]["avg_inference_ms"] for l in langs]
    counts = [lang[l]["count"] for l in langs]

    x = range(len(langs))
    w = 0.35

    bars_f1 = ax.bar([p - w / 2 for p in x], f1_scores, w, label="F1 (%)", color="#0a72ef", alpha=0.85)
    ax_twin = ax.twinx()
    bars_t = ax_twin.bar([p + w / 2 for p in x], times, w, label="Avg Time (ms)", color="#de1d8d", alpha=0.85)

    for bar, f, c in zip(bars_f1, f1_scores, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                f"{f:.1f}%", ha="center", fontsize=9, fontweight="bold")
    for bar, t in zip(bars_t, times):
        ax_twin.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                     f"{t:.0f}ms", ha="center", fontsize=8, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(langs, fontsize=10, fontweight="bold")
    ax.set_ylabel("F1 Score (%)", fontsize=10, fontweight="bold", color="#0a72ef")
    ax_twin.set_ylabel("Avg Inference Time (ms)", fontsize=10, fontweight="bold", color="#de1d8d")
    ax.set_title("各語言 PII 偵測挑戰度 (F1 + 推論時間)", fontsize=13, fontweight="bold", pad=15)

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax_twin.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=9)

    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "chart_language_challenge.png")
    plt.close(fig)
    print("  [OK] chart_language_challenge.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 5: Failure Mode Analysis (FN/FP distribution by group)
# ══════════════════════════════════════════════════════════════════════════════

def chart_failure_analysis(plt, summary):
    groups = summary["per_group"]
    group_order = ["SHORT", "MEDIUM", "LONG", "ORAL", "STRUCT", "MULTI"]

    names = [groups[g]["name"] for g in group_order if g in groups]
    fn_vals = [groups[g]["fn"] for g in group_order if g in groups]
    fp_vals = [groups[g]["fp"] for g in group_order if g in groups]
    tp_vals = [groups[g]["tp"] for g in group_order if g in groups]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: stacked bar TP/FN/FP
    x = range(len(names))
    w = 0.6
    ax1.bar(x, tp_vals, w, label="True Positive", color="#166534", alpha=0.85)
    ax1.bar(x, fn_vals, w, bottom=tp_vals, label="False Negative (漏抓)", color="#ff5b4f", alpha=0.85)
    ax1.bar(x, fp_vals, w, bottom=[t + f for t, f in zip(tp_vals, fn_vals)],
            label="False Positive (誤判)", color="#de1d8d", alpha=0.85)
    ax1.set_xticks(x)
    ax1.set_xticklabels(names, fontsize=9)
    ax1.set_ylabel("PII 數量", fontsize=10, fontweight="bold")
    ax1.set_title("偵測結果分類 (TP / FN / FP)", fontsize=12, fontweight="bold")
    ax1.legend(fontsize=9, loc="upper right")
    ax1.grid(axis="y", alpha=0.2)

    # Right: FN rate as % of expected
    fn_rates = []
    for g in group_order:
        if g in groups:
            total_exp = groups[g]["total_expected_pii"]
            fn_rates.append(groups[g]["fn"] / max(total_exp, 1) * 100)
    fp_rates = []
    for g in group_order:
        if g in groups:
            total_det = groups[g]["total_detected_pii"]
            fp_rates.append(groups[g]["fp"] / max(total_det, 1) * 100)

    ax2.barh(range(len(names)), fn_rates, 0.35, label="漏抓率 (%)", color="#ff5b4f", alpha=0.85)
    ax2.barh([p + 0.35 for p in range(len(names))], fp_rates, 0.35, label="誤判率 (%)", color="#de1d8d", alpha=0.85)
    for i, (fn_r, fp_r) in enumerate(zip(fn_rates, fp_rates)):
        ax2.text(fn_r + 1, i, f"{fn_r:.1f}%", va="center", fontsize=9, fontweight="bold", color="#ff5b4f")
        ax2.text(fp_r + 1, i + 0.35, f"{fp_r:.1f}%", va="center", fontsize=9, fontweight="bold", color="#de1d8d")
    ax2.set_yticks([p + 0.175 for p in range(len(names))])
    ax2.set_yticklabels(names, fontsize=9)
    ax2.set_xlabel("比例 (%)", fontsize=10, fontweight="bold")
    ax2.set_title("漏抓率 vs 誤判率", fontsize=12, fontweight="bold")
    ax2.legend(fontsize=9, loc="lower right")
    ax2.grid(axis="x", alpha=0.2)

    fig.suptitle("失敗模式分析 — 各類別的漏抓與誤判分佈", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "chart_failure_analysis.png")
    plt.close(fig)
    print("  [OK] chart_failure_analysis.png")


# ══════════════════════════════════════════════════════════════════════════════
# Chart 6: Concurrency Throughput (from concurrency_summary.json)
# ══════════════════════════════════════════════════════════════════════════════

def chart_concurrency(plt, concurrency_data):
    if not concurrency_data:
        print("  [SKIP] chart_concurrency.png (no concurrency data yet)")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: Single request QPS vs Workers
    single = concurrency_data.get("single_text", {})
    by_workers = single.get("by_workers", [])
    if by_workers:
        workers_sorted = sorted(item["workers"] for item in by_workers)
        qps_vals = [item["avg_qps"] for item in by_workers]
        lat_vals = [item["avg_latency_ms"] for item in by_workers]
        p95_vals = [item["avg_p95_latency_ms"] for item in by_workers]

        ax1.plot(workers_sorted, qps_vals, "o-", color="#0a72ef", linewidth=2, markersize=8, label="Avg QPS")
        ax1.set_xlabel("Concurrent Workers", fontsize=10, fontweight="bold")
        ax1.set_ylabel("Queries Per Second", fontsize=10, fontweight="bold", color="#0a72ef")
        ax1.set_title("並行推論吞吐量 (QPS vs Workers)", fontsize=12, fontweight="bold")
        ax1.grid(alpha=0.2)
        for w, q in zip(workers_sorted, qps_vals):
            ax1.annotate(f"{q:.2f}", (w, q), textcoords="offset points", xytext=(0, 10),
                         ha="center", fontsize=9, fontweight="bold")

        ax1_twin = ax1.twinx()
        ax1_twin.plot(workers_sorted, lat_vals, "s--", color="#de1d8d", linewidth=2, markersize=8, label="Avg Latency")
        ax1_twin.plot(workers_sorted, p95_vals, "x:", color="#ff5b4f", linewidth=1.5, markersize=7, label="P95 Latency")
        ax1_twin.set_ylabel("Latency (ms)", fontsize=10, fontweight="bold", color="#de1d8d")
        for w, l in zip(workers_sorted, lat_vals):
            ax1_twin.annotate(f"{l:.0f}ms", (w, l), textcoords="offset points", xytext=(0, -15),
                              ha="center", fontsize=8, color="#de1d8d")

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax1_twin.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8)

    # Right: Batch throughput
    batch = concurrency_data.get("batch", {})
    by_batch = batch.get("by_batch_size", [])
    if by_batch:
        batch_sizes = sorted(item["batch_size"] for item in by_batch)
        batch_qps = [item["avg_equivalent_text_qps"] for item in by_batch]
        batch_lat = [item["avg_batch_latency_ms"] for item in by_batch]

        bars = ax2.bar(range(len(batch_sizes)), batch_qps, color="#166534", alpha=0.85, label="等效 QPS")
        ax2.set_xticks(range(len(batch_sizes)))
        ax2.set_xticklabels([f"Batch {bs}" for bs in batch_sizes], fontsize=10)
        ax2.set_ylabel("Per-Text QPS", fontsize=10, fontweight="bold")
        ax2.set_title("批次推論吞吐量 (等效 QPS)", fontsize=12, fontweight="bold")
        ax2.grid(axis="y", alpha=0.2)
        for i, q in enumerate(batch_qps):
            ax2.text(i, q + 0.02, f"{q:.1f}", ha="center", fontsize=10, fontweight="bold")

        ax2_twin = ax2.twinx()
        ax2_twin.plot(range(len(batch_sizes)), batch_lat, "o--", color="#de1d8d", linewidth=2, markersize=8, label="Batch Latency")
        ax2_twin.set_ylabel("Batch Latency (ms)", fontsize=10, fontweight="bold", color="#de1d8d")
        for i, l in enumerate(batch_lat):
            ax2_twin.annotate(f"{l:.0f}ms", (i, l), textcoords="offset points", xytext=(0, -15),
                              ha="center", fontsize=8, color="#de1d8d")

        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_twin.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=8)

    fig.suptitle("並行與批次處理效能", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "chart_concurrency.png")
    plt.close(fig)
    print("  [OK] chart_concurrency.png")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    summary, raw, concurrency = load_data()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plt = setup_matplotlib()

    print("產生 PPT 圖表...")
    chart_system_dashboard(plt, summary)
    chart_char_time(plt, summary, raw)
    chart_group_performance(plt, summary)
    chart_language_challenge(plt, summary)
    chart_failure_analysis(plt, summary)
    chart_concurrency(plt, concurrency)

    print(f"\n全部輸出至: {OUT_DIR}/")
    print("可用圖表:")
    print("  1. chart_system_dashboard.png    — 部署可行性（載入/記憶體/Cold-Warm）")
    print("  2. chart_char_time.png           — 字數-時間線性關聯")
    print("  3. chart_group_performance.png   — 各類別成功率 vs 時間")
    print("  4. chart_language_challenge.png  — 語言挑戰矩陣")
    print("  5. chart_failure_analysis.png    — 漏抓/誤判分析")
    print("  6. chart_concurrency.png         — 並行吞吐量")


if __name__ == "__main__":
    main()
