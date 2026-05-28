"""
Regex-based PII detector — baseline for comparison with OPF.
Covers common Taiwan/International PII patterns.
"""
from __future__ import annotations
import re
from collections import defaultdict

# ── 正則表示式規則集（台灣 + 國際常見格式）──────────────────────────────────

RULES: list[tuple[str, str, str]] = [
    # (label, regex_pattern, description)
    ("EMAIL", r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b',
     "Email address"),
    ("PHONE", r'(?:\+886[-.\s]?|0)[2-9]\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{3,4}',
     "Taiwan phone (mobile + landline)"),
    ("PHONE", r'\+\d{1,3}[-.\s]?\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}',
     "International phone"),
    ("ACCOUNT", r'\b[A-Z]\d{9}\b',
     "Taiwan ID number (A123456789)"),
    ("ACCOUNT", r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
     "Credit card number (16-digit)"),
    ("ACCOUNT", r'\bEMP-\d{4}-\d{4}\b',
     "Employee ID (EMP-2026-0442)"),
    ("ACCOUNT", r'\b(?:AKIA|ASIA)[A-Z0-9]{16,}\b',
     "AWS Access Key ID"),
    ("ACCOUNT", r'\b\d{3}-\d{2}-\d{4}\b',
     "US SSN pattern"),
    ("URL", r'https?://[^\s<>"{}|\\^`\[\]]+',
     "HTTP(S) URL"),
    ("URL", r'(?:postgresql|mysql|mongodb)://[^\s]+',
     "Database connection string"),
    ("DATE", r'\b\d{4}[-/]\d{2}[-/]\d{2}\b',
     "ISO date (2026-04-29)"),
    ("DATE", r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b',
     "US long date (March 4, 1988)"),
    ("DATE", r'\b\d{1,2}/\d{1,2}\b',
     "Short date (5/8, 09/28)"),
    ("SECRET", r'(?:password|passwd|pwd|secret|token|key)[=:]\s*[^\s\n]+',
     "Credential assignment"),
    ("SECRET", r'\b(?:sk-[A-Za-z0-9]{32,}|whsec_[A-Za-z0-9]{20,}|stg_tk_[A-Za-z0-9]{16,})\b',
     "API key patterns (Stripe/Webhook/Staging)"),
    ("ADDRESS", r'(?:台北|新北|桃園|台中|台南|高雄|基隆|新竹|嘉義|苗栗|彰化|南投|雲林|屏東|宜蘭|花蓮|台東|澎湖|金門|連江)(?:市|縣)[一-鿿\d路段巷弄號樓之]+',
     "Taiwan address (Chinese)"),
]

# Regex patterns that tend to produce false positives — apply only when OPF misses
# These are "high precision, low recall" patterns designed to supplement OPF gaps


def detect_pii_regex(text: str) -> dict[str, list[str]]:
    """
    Run all regex rules on text, return detected PII by type.
    Overlapping matches resolved by longest-match-first per type.
    """
    results: dict[str, list[str]] = defaultdict(list)
    seen_spans: set[tuple[int, int]] = set()

    for ptype, pattern, _desc in RULES:
        for m in re.finditer(pattern, text):
            span = (m.start(), m.end())
            # Skip if this span overlaps with an already-matched span of SAME type
            overlaps = any(
                not (span[1] <= s[0] or span[0] >= s[1])
                for s in seen_spans
            )
            if not overlaps:
                results[ptype].append(m.group())
                seen_spans.add(span)

    return dict(results)


def evaluate_regex_baseline(test_cases: list[dict]) -> dict:
    """
    Run regex baseline across all test cases, compute per-type metrics.
    Uses the same matching logic as eval.py (set-based, case-insensitive for EMAIL).
    """
    from eval import compute_metrics as _cm

    agg: dict[str, dict] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    case_results = []

    for tc in test_cases:
        expected = tc.get("expected", {})
        detected = detect_pii_regex(tc["text"])
        metrics = _cm(expected, detected)
        case_results.append({
            "id": tc["id"],
            "category": tc.get("category", ""),
            "metrics": metrics,
            "detected": detected,
        })
        for ptype, m in metrics["per_type"].items():
            agg[ptype]["tp"] += m["tp"]
            agg[ptype]["fp"] += m["fp"]
            agg[ptype]["fn"] += m["fn"]

    # Aggregate per-type
    per_type = {}
    tp_all = fp_all = fn_all = 0
    for ptype, counts in agg.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        per_type[ptype] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}
        tp_all += tp
        fp_all += fp
        fn_all += fn

    micro_p = tp_all / (tp_all + fp_all) if (tp_all + fp_all) > 0 else 0.0
    micro_r = tp_all / (tp_all + fn_all) if (tp_all + fn_all) > 0 else 0.0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0

    return {
        "per_type": per_type,
        "micro_f1": round(micro_f1, 4),
        "total_tp": tp_all, "total_fp": fp_all, "total_fn": fn_all,
        "cases": case_results,
    }


if __name__ == "__main__":
    from eval_dataset import get_all_tests
    import json
    tests = get_all_tests()
    res = evaluate_regex_baseline(tests)
    print(json.dumps({k: v for k, v in res.items() if k != "cases"}, ensure_ascii=False, indent=2))
