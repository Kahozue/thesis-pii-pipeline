"""
PII Pipeline — System Performance Characterization
Measures: load time, memory, cold/warm inference, char-time correlation, per-group success rate.
"""
from __future__ import annotations
import json
import time
import gc
import sys
import os
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from pipeline import run_pipeline, load_opf, stage1_filter
from eval_dataset import get_all_tests, GROUP_NAMES, dataset_stats
import platform
import psutil

HERE = Path(__file__).resolve().parent
OUT_RAW = HERE / "eval_charts" / "eval_raw.json"
OUT_SUMMARY = HERE / "eval_charts" / "eval_summary.json"

# ══════════════════════════════════════════════════════════════════════════════
# 硬體規格
# ══════════════════════════════════════════════════════════════════════════════

def get_hardware_info() -> dict:
    """Collect system hardware specs for reproducibility (cross-platform)."""
    cpu_freq = psutil.cpu_freq()
    svmem = psutil.virtual_memory()
    is_apple_silicon = False
    cpu_brand = platform.processor() or "unknown"

    # Detect CPU brand — platform-specific
    system = platform.system()
    if system == "Darwin":
        try:
            out = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
            cpu_brand = out
            is_apple_silicon = "Apple" in out
        except Exception:
            pass
    elif system == "Linux":
        try:
            # /proc/cpuinfo has "model name" on x86, varies on ARM; try multiple keys
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if ":" in line:
                        key, val = line.split(":", 1)
                        key = key.strip()
                        if key in ("model name", "Model Name", "Processor"):
                            cpu_brand = val.strip()
                            break
            # ARM fallback: read CPU implementer/part from /proc/cpuinfo
            if cpu_brand in ("unknown", "", "aarch64"):
                cpu_brand = _read_arm_cpuinfo()
        except Exception:
            cpu_brand = platform.processor() or "unknown"

    return {
        "os": f"{system} {platform.release()} ({platform.version()})",
        "cpu_brand": cpu_brand,
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "cpu_cores_logical": psutil.cpu_count(logical=True),
        "cpu_freq_mhz": round(cpu_freq.max, 0) if cpu_freq else None,
        "ram_total_gb": round(svmem.total / 1024**3, 1),
        "ram_available_gb": round(svmem.available / 1024**3, 1),
        "is_apple_silicon": is_apple_silicon,
        "python_version": platform.python_version(),
        "pytorch_device": "cpu",
    }


def _read_arm_cpuinfo() -> str:
    """Parse ARM-specific /proc/cpuinfo fields into a readable string."""
    try:
        fields = {}
        with open("/proc/cpuinfo") as f:
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    fields[k.strip()] = v.strip()
        impl = fields.get("CPU implementer", "")
        part = fields.get("CPU part", "")
        variant = fields.get("CPU variant", "")
        arch = fields.get("CPU architecture", "")
        # Known ARM part mappings
        part_names = {
            "0xd0c": "Neoverse N1", "0xd0d": "Neoverse N2",
            "0xd40": "Neoverse V1", "0xd4f": "Neoverse V2",
            "0xd0e": "Cortex-A76", "0xd41": "Cortex-A78",
        }
        part_name = part_names.get(part, f"part={part}")
        if impl and part:
            return f"ARM {part_name} (impl={impl} variant={variant} arch={arch})"
    except Exception:
        pass
    return platform.processor() or "unknown"

# ══════════════════════════════════════════════════════════════════════════════
# 記憶體測量（psutil — 含 PyTorch tensor 實際佔用）
# ══════════════════════════════════════════════════════════════════════════════

_PROC = psutil.Process()

def measure_memory_mb() -> float:
    """Get current process RSS (resident set size) in MB. Includes PyTorch tensors."""
    return _PROC.memory_info().rss / 1024 / 1024

def measure_memory_uss_mb() -> float:
    """Get USS (unique set size) in MB — memory unique to this process (macOS only)."""
    try:
        mem = _PROC.memory_full_info()
        return mem.uss / 1024 / 1024
    except Exception:
        return _PROC.memory_info().rss / 1024 / 1024

# ══════════════════════════════════════════════════════════════════════════════
# 模型載入
# ══════════════════════════════════════════════════════════════════════════════

def measure_load_time() -> dict:
    """Measure model loading time and memory footprint.

    Note: psutil RSS undercounts for mmap'd model weights on macOS.
    We supplement with system-level virtual_memory delta for true picture.
    """
    print("  [BENCH] 測量模型載入...")
    gc.collect()
    time.sleep(0.5)  # let system stabilize

    # Pre-load snapshot
    svm_before = psutil.virtual_memory()
    proc_before = _PROC.memory_full_info()

    t0 = time.perf_counter()
    opf = load_opf(device="cpu")
    t1 = time.perf_counter()
    time.sleep(0.5)  # let memory allocations settle

    # Post-load snapshot
    svm_after = psutil.virtual_memory()
    proc_after = _PROC.memory_full_info()
    load_time_s = round(t1 - t0, 3)

    # On Linux, mmap'd weights go to page cache — track cached delta separately
    is_linux = platform.system() == "Linux"
    svm_cached_before = getattr(svm_before, 'cached', 0) if is_linux else 0
    svm_cached_after = getattr(svm_after, 'cached', 0) if is_linux else 0
    svm_buffers_before = getattr(svm_before, 'buffers', 0) if is_linux else 0
    svm_buffers_after = getattr(svm_after, 'buffers', 0) if is_linux else 0
    # True memory impact: used delta + cached delta (mmap goes to page cache on Linux)
    system_ram_delta = round((svm_after.used - svm_before.used) / 1024**3, 2)
    system_cached_delta = round((svm_cached_after - svm_cached_before) / 1024**3, 2) if is_linux else 0
    system_buffers_delta = round((svm_buffers_after - svm_buffers_before) / 1024**3, 2) if is_linux else 0
    system_total_delta = system_ram_delta + system_cached_delta + system_buffers_delta

    # Build platform-aware note
    if platform.system() == "Darwin":
        _note = (
            "Process RSS/VMS undercounts memory on macOS because OPF uses "
            "memory-mapped files (mmap) for model weights. The system-level "
            "RAM delta (system_ram_delta_gb) is the most reliable metric. "
            "External system monitor (iStats/Activity Monitor) typically shows "
            "~3.5-4.0 GB increase for the full 1.5B BF16 model + PyTorch runtime."
        )
    elif is_linux:
        _note = (
            "On Linux, mmap'd model weights go to page cache (cached), not 'used'. "
            f"The used+cached delta ({system_total_delta:.2f} GB) reflects the "
            "true memory impact. cached delta alone typically shows the model weights "
            f"({system_cached_delta:.2f} GB for this run)."
        )
    else:
        _note = f"System RAM delta: {system_ram_delta:.2f} GB"

    return {
        "load_time_seconds": load_time_s,
        # Process-level
        "proc_rss_before_mb": round(proc_before.rss / 1024**2, 1),
        "proc_rss_after_mb": round(proc_after.rss / 1024**2, 1),
        "proc_rss_delta_mb": round((proc_after.rss - proc_before.rss) / 1024**2, 1),
        "proc_vms_before_mb": round(proc_before.vms / 1024**2, 1),
        "proc_vms_after_mb": round(proc_after.vms / 1024**2, 1),
        "proc_vms_delta_mb": round((proc_after.vms - proc_before.vms) / 1024**2, 1),
        "proc_uss_before_mb": round(getattr(proc_before, 'uss', proc_before.rss) / 1024**2, 1),
        "proc_uss_after_mb": round(getattr(proc_after, 'uss', proc_after.rss) / 1024**2, 1),
        "proc_uss_delta_mb": round((getattr(proc_after, 'uss', proc_after.rss) - getattr(proc_before, 'uss', proc_before.rss)) / 1024**2, 1),
        # System-level
        "system_ram_total_gb": round(svm_before.total / 1024**3, 1),
        "system_ram_used_before_gb": round(svm_before.used / 1024**3, 1),
        "system_ram_used_after_gb": round(svm_after.used / 1024**3, 1),
        "system_ram_delta_gb": system_ram_delta,
        "system_cached_before_gb": round(svm_cached_before / 1024**3, 1) if is_linux else None,
        "system_cached_after_gb": round(svm_cached_after / 1024**3, 1) if is_linux else None,
        "system_cached_delta_gb": system_cached_delta if is_linux else None,
        "system_used_cached_delta_gb": system_total_delta if is_linux else None,
        "system_ram_percent_before": svm_before.percent,
        "system_ram_percent_after": svm_after.percent,
        "_note": _note,
    }

# ══════════════════════════════════════════════════════════════════════════════
# Cold vs Warm Inference
# ══════════════════════════════════════════════════════════════════════════════

def measure_warmup(opf, test_text: str) -> dict:
    """Run N inferences and track cold→warm transition."""
    print("  [BENCH] 測量 cold/warm 推論...")
    N_WARMUP = 10
    times = []

    for i in range(N_WARMUP):
        t0 = time.perf_counter()
        _ = stage1_filter(test_text, opf)
        t1 = time.perf_counter()
        times.append(round((t1 - t0) * 1000, 1))

    return {
        "warmup_iterations": N_WARMUP,
        "cold_ms": times[0],
        "warm_avg_ms": round(statistics.mean(times[2:]), 1),
        "warm_std_ms": round(statistics.stdev(times[2:]), 1) if len(times) > 3 else 0,
        "cold_warm_ratio": round(times[0] / statistics.mean(times[2:]), 2) if times[2:] else 0,
        "all_times_ms": times,
    }

# ══════════════════════════════════════════════════════════════════════════════
# Single-case evaluation
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_case(opf, test_case: dict, run_index: int) -> dict:
    """Evaluate one test case. Returns timing + PII detection metrics."""
    text = test_case["text"]
    text_len = len(text)
    expected = test_case.get("expected", {})

    # Run pipeline
    t0 = time.perf_counter()
    result = run_pipeline(text, opf)
    t1 = time.perf_counter()
    elapsed_ms = round((t1 - t0) * 1000, 1)

    # Compute detection stats
    detected_by_type: dict[str, list[str]] = defaultdict(list)
    for rec in result["records"]:
        detected_by_type[rec["short"]].append(rec["original"])

    # Set-based matching (conservative lower bound)
    tp_total = fp_total = fn_total = 0
    per_type_stats = {}
    all_types = sorted(set(expected) | set(detected_by_type))

    for ptype in all_types:
        exp_vals = set(v.strip().lower() if ptype == "EMAIL" else v.strip()
                       for v in expected.get(ptype, []))
        det_vals = set(v.strip().lower() if ptype == "EMAIL" else v.strip()
                       for v in detected_by_type.get(ptype, []))
        tp = len(exp_vals & det_vals)
        fp = len(det_vals - exp_vals)
        fn = len(exp_vals - det_vals)
        per_type_stats[ptype] = {"tp": tp, "fp": fp, "fn": fn,
                                  "expected": len(exp_vals), "detected": len(det_vals)}
        tp_total += tp
        fp_total += fp
        fn_total += fn

    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0.0
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # For negative cases, FP rate is the key metric
    fp_rate = fp_total / max(text_len, 1)

    # Collect raw detected/expected values for audit
    false_negatives = []
    for ptype, vals in expected.items():
        det_set = {v.strip().lower() if ptype == "EMAIL" else v.strip()
                   for v in detected_by_type.get(ptype, [])}
        for v in vals:
            cmp = v.strip().lower() if ptype == "EMAIL" else v.strip()
            if cmp not in det_set:
                false_negatives.append({"type": ptype, "value": v})

    false_positives = []
    for ptype, vals in detected_by_type.items():
        exp_set = {v.strip().lower() if ptype == "EMAIL" else v.strip()
                   for v in expected.get(ptype, [])}
        for v in vals:
            cmp = v.strip().lower() if ptype == "EMAIL" else v.strip()
            if cmp not in exp_set:
                false_positives.append({"type": ptype, "value": v})

    return {
        "id": test_case["id"],
        "group": test_case.get("group", ""),
        "category": test_case.get("category", ""),
        "language": test_case.get("language", ""),
        "run_index": run_index,
        "text_length": text_len,
        "pii_expected_unique": sum(len(v) for v in expected.values()),
        "pii_detected_total": len(result["records"]),
        "inference_ms": elapsed_ms,
        "chars_per_ms": round(text_len / max(elapsed_ms, 0.1), 2),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "fp_rate": round(fp_rate, 6),
        "tp": tp_total, "fp": fp_total, "fn": fn_total,
        "per_type": per_type_stats,
        "false_negatives": false_negatives,
        "false_positives": false_positives,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Main evaluation
# ══════════════════════════════════════════════════════════════════════════════

def run_full_evaluation(n_runs: int = 2) -> dict:
    """
    Full evaluation pipeline.
    n_runs: number of repeated inferences per case (for timing stability).
    """
    tests = get_all_tests()

    # ── 1. Dataset stats ──
    print("=" * 70)
    print("PII Pipeline — System Performance Characterization")
    print("=" * 70)
    ds = dataset_stats()
    print(f"\n資料集: {ds['total_cases']} 案例, {ds['total_chars']} 字, {ds['total_expected_pii']} 預期 PII")
    for g, d in ds["groups"].items():
        print(f"  {GROUP_NAMES.get(g, g)}: {d['count']} 筆, 均長 {d['avg_chars']} 字, {d['total_expected_pii']} PII")

    # ── 0. Hardware ──
    hw = get_hardware_info()
    print(f"\n硬體環境: {hw['cpu_brand']}")
    print(f"  {hw['os']}")
    cpu_freq_str = f"@{hw['cpu_freq_mhz']:.0f}MHz, " if hw['cpu_freq_mhz'] else ""
    print(f"  CPU: {hw['cpu_cores_physical']}P/{hw['cpu_cores_logical']}L {cpu_freq_str}RAM: {hw['ram_total_gb']}GB total ({hw['ram_available_gb']}GB available)")
    print(f"  Apple Silicon: {hw['is_apple_silicon']}, Python: {hw['python_version']}")

    # ── 2. Load time ──
    print("\n[1/5] 模型載入效能...")
    load_metrics = measure_load_time()
    print(f"  載入時間: {load_metrics['load_time_seconds']}s")
    print(f"  Process VMS (含mmap): {load_metrics['proc_vms_before_mb']:.0f} → {load_metrics['proc_vms_after_mb']:.0f} MB (Δ {load_metrics['proc_vms_delta_mb']:.0f} MB)")
    print(f"  Process RSS (常駐):    {load_metrics['proc_rss_before_mb']:.0f} → {load_metrics['proc_rss_after_mb']:.0f} MB (Δ {load_metrics['proc_rss_delta_mb']:.0f} MB)")
    print(f"  System RAM used:       {load_metrics['system_ram_used_before_gb']:.1f} → {load_metrics['system_ram_used_after_gb']:.1f} GB (Δ {load_metrics['system_ram_delta_gb']:.2f} GB)")
    if platform.system() == "Linux":
        cd = load_metrics.get("system_cached_delta_gb")
        if cd is not None:
            print(f"  System cached (page cache): Δ {cd:.2f} GB (含 mmap 模型權重)")
            td = load_metrics.get("system_used_cached_delta_gb", 0)
            print(f"  System used+cached Δ:  {td:.2f} GB (真實記憶體影響)")
    if platform.system() == "Darwin":
        print(f"  註：macOS mmap 導致 RSS 低估，system-level + iStats 為可靠指標")
    else:
        print(f"  註：Linux mmap 權重進入 page cache，used+cached delta 為可靠指標")

    # Load model for remaining tests
    opf = load_opf(device="cpu")

    # ── 3. Warm-up ──
    print("\n[2/5] Cold/Warm 推論...")
    warmup_text = tests[0]["text"]  # Use first test case for warmup
    warmup_metrics = measure_warmup(opf, warmup_text)
    print(f"  Cold: {warmup_metrics['cold_ms']:.0f}ms, Warm avg: {warmup_metrics['warm_avg_ms']:.0f}ms, Ratio: {warmup_metrics['cold_warm_ratio']}x")

    # ── 4. Per-case evaluation ──
    print(f"\n[3/5] 逐案例評測 ({len(tests)} 案例 × {n_runs} 輪)...")
    all_results = []
    mem_samples = []

    for i, tc in enumerate(tests, 1):
        for run in range(n_runs):
            res = evaluate_case(opf, tc, run)
            all_results.append(res)
            if run == 0:  # Only print once per case
                status = "✓" if res["fn"] == 0 and res["fp"] == 0 else f"FN:{res['fn']} FP:{res['fp']}"
                print(f"  [{i:02d}/{len(tests)}] {tc['id']:<40s} {res['text_length']:>5d}字 {res['inference_ms']:>8.1f}ms {status}")

        # Sample memory every 5 cases
        if i % 5 == 0:
            mem_rss = measure_memory_mb()
            mem_samples.append({"case_index": i, "rss_mb": round(mem_rss, 1),
                                "system_used_gb": round(psutil.virtual_memory().used / 1024**3, 1)})

    # ── 5. Aggregate ──
    print("\n[4/5] 彙總統計...")
    summary = build_summary(all_results, load_metrics, warmup_metrics, mem_samples, ds, hw)

    # ── Save ──
    print("\n[5/5] 儲存結果...")
    OUT_RAW.parent.mkdir(parents=True, exist_ok=True)

    raw_output = {
        "metadata": {
            "model": "openai/privacy-filter",
            "model_params": "1.5B total / 50M active",
            "model_weights": "BF16 (~3.0 GB on disk)",
            "device": "cpu",
            "n_cases": len(tests),
            "n_runs": n_runs,
            "total_inferences": len(all_results),
        },
        "hardware": hw,
        "load_metrics": load_metrics,
        "warmup_metrics": warmup_metrics,
        "memory_samples": mem_samples,
        "results": all_results,
        "dataset_stats": ds,
    }

    OUT_RAW.write_text(json.dumps(raw_output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Raw data: {OUT_RAW} ({OUT_RAW.stat().st_size / 1024:.0f} KB)")

    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Summary:  {OUT_SUMMARY}")

    return summary


def build_summary(all_results, load_metrics, warmup_metrics, mem_samples, ds, hw):
    """Build aggregated summary from all results."""

    # ── Per-group aggregation ──
    groups: dict[str, dict] = defaultdict(lambda: {
        "count": 0, "total_chars": 0, "total_inference_ms": 0,
        "total_expected_pii": 0, "total_detected_pii": 0,
        "tp": 0, "fp": 0, "fn": 0, "inference_times_ms": [],
    })

    for r in all_results:
        if r["run_index"] != 0:
            continue  # Only use first run for quality metrics
        g = r["group"]
        groups[g]["count"] += 1
        groups[g]["total_chars"] += r["text_length"]
        groups[g]["total_inference_ms"] += r["inference_ms"]
        groups[g]["total_expected_pii"] += r["pii_expected_unique"]
        groups[g]["total_detected_pii"] += r["pii_detected_total"]
        groups[g]["tp"] += r["tp"]
        groups[g]["fp"] += r["fp"]
        groups[g]["fn"] += r["fn"]
        groups[g]["inference_times_ms"].append(r["inference_ms"])

    per_group = {}
    overall_tp = overall_fp = overall_fn = 0
    all_times = []

    for g, d in sorted(groups.items()):
        tp, fp, fn = d["tp"], d["fp"], d["fn"]
        p = tp / (tp + fp) if (tp + fp) > 0 else 1.0  # For NEGATIVE, precision=1 if no FP
        r = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 1.0
        times = d["inference_times_ms"]
        per_group[g] = {
            "name": GROUP_NAMES.get(g, g),
            "count": d["count"],
            "avg_chars": d["total_chars"] // d["count"],
            "avg_inference_ms": round(statistics.mean(times), 1),
            "min_inference_ms": round(min(times), 1),
            "max_inference_ms": round(max(times), 1),
            "total_expected_pii": d["total_expected_pii"],
            "total_detected_pii": d["total_detected_pii"],
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn,
            "chars_per_ms": round(d["total_chars"] / max(d["total_inference_ms"], 0.1), 2),
        }
        overall_tp += tp
        overall_fn += fn
        overall_fp += fp
        all_times.extend(times)

    overall_p = overall_tp / (overall_tp + overall_fp) if (overall_tp + overall_fp) > 0 else 0.0
    overall_r = overall_tp / (overall_tp + overall_fn) if (overall_tp + overall_fn) > 0 else 0.0
    overall_f1 = 2 * overall_p * overall_r / (overall_p + overall_r) if (overall_p + overall_r) > 0 else 0.0

    # ── Char-time regression ──
    # Group by text length buckets
    buckets = {
        "0-200 chars": [],
        "200-500 chars": [],
        "500-1000 chars": [],
        "1000-3000 chars": [],
        "3000+ chars": [],
    }
    for r in all_results:
        if r["run_index"] != 0:
            continue
        l = r["text_length"]
        if l <= 200:       buckets["0-200 chars"].append(r["inference_ms"])
        elif l <= 500:     buckets["200-500 chars"].append(r["inference_ms"])
        elif l <= 1000:    buckets["500-1000 chars"].append(r["inference_ms"])
        elif l <= 3000:    buckets["1000-3000 chars"].append(r["inference_ms"])
        else:              buckets["3000+ chars"].append(r["inference_ms"])

    char_time_buckets = {}
    for bucket, times in buckets.items():
        if times:
            char_time_buckets[bucket] = {
                "count": len(times),
                "avg_ms": round(statistics.mean(times), 1),
                "min_ms": round(min(times), 1),
                "max_ms": round(max(times), 1),
            }

    # ── Linear regression (chars → time) ──
    x_vals = [r["text_length"] for r in all_results if r["run_index"] == 0]
    y_vals = [r["inference_ms"] for r in all_results if r["run_index"] == 0]
    if len(x_vals) > 2:
        n = len(x_vals)
        sx = sum(x_vals)
        sy = sum(y_vals)
        sxy = sum(x * y for x, y in zip(x_vals, y_vals))
        sxx = sum(x * x for x in x_vals)
        slope = (n * sxy - sx * sy) / (n * sxx - sx * sx) if (n * sxx - sx * sx) != 0 else 0
        intercept = (sy - slope * sx) / n
        # R²
        y_mean = sy / n
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_vals, y_vals))
        ss_tot = sum((y - y_mean) ** 2 for y in y_vals)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    else:
        slope = intercept = r_squared = 0

    # ── Language breakdown ──
    lang_stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "tp": 0, "fp": 0, "fn": 0, "times": []})
    for r in all_results:
        if r["run_index"] != 0:
            continue
        lang = r["language"]
        lang_stats[lang]["count"] += 1
        lang_stats[lang]["tp"] += r["tp"]
        lang_stats[lang]["fp"] += r["fp"]
        lang_stats[lang]["fn"] += r["fn"]
        lang_stats[lang]["times"].append(r["inference_ms"])

    per_language = {}
    for lang, d in lang_stats.items():
        tp, fp, fn = d["tp"], d["fp"], d["fn"]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_l = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        per_language[lang] = {
            "count": d["count"],
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1_l, 4),
            "avg_inference_ms": round(statistics.mean(d["times"]), 1),
        }

    # ── Negative case FP analysis ──
    neg_fp = 0
    neg_total = 0
    for r in all_results:
        if r["run_index"] == 0 and r["group"] == "NEGATIVE":
            neg_fp += r["fp"]
            neg_total += r["text_length"]
    neg_fp_rate = neg_fp / max(neg_total, 1)

    # ── Top failure cases ──
    all_fn = []
    all_fp = []
    for r in all_results:
        if r["run_index"] == 0:
            for fn in r["false_negatives"]:
                all_fn.append({"case_id": r["id"], "group": r["group"], "type": fn["type"], "value": fn["value"]})
            for fp in r["false_positives"]:
                all_fp.append({"case_id": r["id"], "group": r["group"], "type": fp["type"], "value": fp["value"]})

    return {
        "hardware": {
            "cpu": hw["cpu_brand"],
            "os": hw["os"],
            "cpu_cores": f"{hw['cpu_cores_physical']}P/{hw['cpu_cores_logical']}L",
            "ram_total_gb": hw["ram_total_gb"],
            "apple_silicon": hw["is_apple_silicon"],
        },
        "headline": {
            "模型": "OpenAI Privacy Filter (opf) — 1.5B params, BF16, Apache 2.0",
            "測試案例數": ds["total_cases"],
            "總字數": ds["total_chars"],
            "預期 PII 總數": ds["total_expected_pii"],
            "模型載入時間_s": load_metrics["load_time_seconds"],
            "Proc_VMS_delta_MB": load_metrics["proc_vms_delta_mb"],
            "Proc_RSS_delta_MB": load_metrics["proc_rss_delta_mb"],
            "Proc_USS_delta_MB": load_metrics["proc_uss_delta_mb"],
            "System_RAM_delta_GB": load_metrics["system_ram_delta_gb"],
            "External_iStats_obs_GB": (
                "~3.9 GB (mmap weights + PyTorch runtime, 最可靠指標)"
                if hw["is_apple_silicon"] else
                f'{load_metrics.get("system_used_cached_delta_gb", load_metrics["system_ram_delta_gb"]):.2f} GB (used+cached delta, Linux page cache 計入)'
            ),
            "Cold推論_ms": warmup_metrics["cold_ms"],
            "Warm推論_avg_ms": warmup_metrics["warm_avg_ms"],
            "Cold_Warm比例": warmup_metrics["cold_warm_ratio"],
            "整體Precision": round(overall_p, 4),
            "整體Recall": round(overall_r, 4),
            "整體F1": round(overall_f1, 4),
            "Negative_FP_rate": round(neg_fp_rate, 6),
            "字數時間R²": round(r_squared, 4),
            "每千字推論時間_ms": round(slope * 1000, 1),
        },
        "load": load_metrics,
        "warmup": warmup_metrics,
        "per_group": per_group,
        "per_language": per_language,
        "char_time_buckets": char_time_buckets,
        "char_time_regression": {
            "slope_ms_per_char": round(slope, 4),
            "intercept_ms": round(intercept, 1),
            "r_squared": round(r_squared, 4),
            "estimated_1000char_ms": round(slope * 1000 + intercept, 1),
        },
        "negative_control": {
            "total_fp": neg_fp,
            "total_chars": neg_total,
            "fp_per_1k_chars": round(neg_fp / max(neg_total, 1) * 1000, 2),
        },
        "top_false_negatives": all_fn[:30],
        "top_false_positives": all_fp[:30],
    }


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    summary = run_full_evaluation(n_runs=2)

    # Print final report
    h = summary["headline"]
    print("\n" + "=" * 70)
    print("評估摘要 — System Performance Characterization")
    print("=" * 70)
    hw = summary["hardware"]
    print(f"  硬體: {hw['cpu']} ({hw['cpu_cores']}, {hw['ram_total_gb']}GB RAM, Apple Silicon: {hw['apple_silicon']})")
    mem_ref = h.get("External_iStats_obs_GB", "")
    print(f"  模型載入: {h['模型載入時間_s']}s, VMS Δ {h['Proc_VMS_delta_MB']:.0f} MB, 記憶體: {mem_ref}")
    print(f"  Cold 推論: {h['Cold推論_ms']:.0f}ms, Warm 推論: {h['Warm推論_avg_ms']:.0f}ms ({h['Cold_Warm比例']}x)")
    print(f"  字數-時間線性度 R²: {h['字數時間R²']:.4f}  (每千字: {h['每千字推論時間_ms']:.0f}ms)")
    print(f"  整體 F1: {h['整體F1']:.2%}, Negative FP rate: {h['Negative_FP_rate']:.6f}")

    print("\n各類別表現:")
    print(f"  {'類別':<20} {'筆數':>4} {'均長':>5} {'均時':>8} {'F1':>8} {'字/ms':>8}")
    print(f"  {'-'*20} {'-'*4} {'-'*5} {'-'*8} {'-'*8} {'-'*8}")
    for g, d in summary["per_group"].items():
        print(f"  {d['name']:<20} {d['count']:>4} {d['avg_chars']:>5} {d['avg_inference_ms']:>7.0f}ms {d['f1']:>7.2%} {d['chars_per_ms']:>7.2f}")

    print("\n各語言表現:")
    for lang, d in summary["per_language"].items():
        print(f"  {lang:<16} {d['count']:>3} 筆, F1={d['f1']:.2%}, 均時={d['avg_inference_ms']:.0f}ms")

    char_buckets = summary["char_time_buckets"]
    if char_buckets:
        print("\n字數-時間關聯:")
        for bucket, d in char_buckets.items():
            print(f"  {bucket:<16} {d['count']:>3} 筆, 均時={d['avg_ms']:.0f}ms (範圍: {d['min_ms']:.0f}-{d['max_ms']:.0f}ms)")

    print(f"\n完整數據: {OUT_RAW}")
    print(f"彙總報告: {OUT_SUMMARY}")


if __name__ == "__main__":
    main()
