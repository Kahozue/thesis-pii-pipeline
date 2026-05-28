"""
PII 隱私過濾 Pipeline
Stage 1: OpenAI Privacy Filter (opf)  → 佔位符 [LABEL_N]
Stage 2: 自製代號映射                  → 差異化代號 LABEL_LETTER
"""
from __future__ import annotations
from string import ascii_uppercase
from html import escape
import re
import requests

# opf label → 短代號
LABEL_MAP: dict[str, str] = {
    "private_person":  "PERSON",
    "private_address": "ADDRESS",
    "private_email":   "EMAIL",
    "private_phone":   "PHONE",
    "private_url":     "URL",
    "private_date":    "DATE",
    "account_number":  "ACCOUNT",
    "secret":          "SECRET",
}

LABEL_COLOR: dict[str, str] = {
    "PERSON":  "#FF6B6B",
    "ADDRESS": "#4ECDC4",
    "EMAIL":   "#45B7D1",
    "PHONE":   "#96CEB4",
    "URL":     "#F7DC6F",
    "DATE":    "#C39BD3",
    "ACCOUNT": "#82E0AA",
    "SECRET":  "#FAD7A0",
}


# ─── Stage 1 ──────────────────────────────────────────────────────────────────

def load_opf(device: str = "cpu"):
    """載入 OPF 模型（首次自動下載到 ~/.opf/privacy_filter）。"""
    from opf._api import OPF
    return OPF(device=device, output_mode="typed")


def stage1_filter(text: str, opf_instance) -> tuple[str, list[dict]]:
    """
    執行 Privacy Filter。
    回傳 (placeholder_text, span_records)
    span_records 每筆含：original / label / short / num / start / end / placeholder
    """
    result = opf_instance.redact(text)

    # opf 回傳 RedactionResult；placeholder 格式如 [PRIVATE_PERSON] 或 [PRIVATE_EMAIL]
    counters: dict[str, int] = {}
    records: list[dict] = []

    for span in sorted(result.detected_spans, key=lambda s: s.start):
        label = span.label                          # e.g. "private_person"
        short = LABEL_MAP.get(label, label.upper()) # e.g. "PERSON"
        counters[short] = counters.get(short, 0) + 1
        records.append({
            "original":    span.text,
            "label":       label,
            "short":       short,
            "num":         counters[short],
            "start":       span.start,
            "end":         span.end,
            "placeholder": f"[{short}_{counters[short]}]",
        })

    # 重新構建佔位符文本（用我們自訂的 [SHORT_N] 格式，而非 opf 預設格式）
    redacted = text
    for rec in sorted(records, key=lambda x: x["start"], reverse=True):
        redacted = redacted[:rec["start"]] + rec["placeholder"] + redacted[rec["end"]:]

    return redacted, records


def stage1_api(text: str, hf_token: str = "") -> tuple[str, list[dict]]:
    """
    透過 HuggingFace Inference API 執行 Stage 1。
    需要 HuggingFace token（openai/privacy-filter 為 gated model）。
    """
    url = "https://api-inference.huggingface.co/models/openai/privacy-filter"
    headers = {"Content-Type": "application/json"}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    # HF token-classification endpoint
    resp = requests.post(
        url,
        headers=headers,
        json={"inputs": text, "parameters": {"aggregation_strategy": "simple"}},
        timeout=60,
    )
    resp.raise_for_status()
    raw = resp.json()

    # HF API 有時回傳巢狀 list
    if isinstance(raw, list) and raw and isinstance(raw[0], list):
        raw = raw[0]
    if not isinstance(raw, list):
        raise ValueError(f"Unexpected API response: {raw}")

    # 過濾掉沒有 start/end 的 span
    valid = [s for s in raw if "start" in s and "end" in s]
    counters: dict[str, int] = {}
    records: list[dict] = []
    for span in sorted(valid, key=lambda x: x["start"]):
        label = span.get("entity_group") or span.get("entity", "")
        short = LABEL_MAP.get(label, label.upper())
        counters[short] = counters.get(short, 0) + 1
        records.append({
            "original":    text[span["start"]:span["end"]],
            "label":       label,
            "short":       short,
            "num":         counters[short],
            "start":       span["start"],
            "end":         span["end"],
            "placeholder": f"[{short}_{counters[short]}]",
        })

    redacted = text
    for rec in sorted(records, key=lambda x: x["start"], reverse=True):
        redacted = redacted[:rec["start"]] + rec["placeholder"] + redacted[rec["end"]:]

    return redacted, records


# ─── Stage 2 ──────────────────────────────────────────────────────────────────

def stage2_mapping(records: list[dict]) -> dict[str, str]:
    """
    建立對照表：[SHORT_N] → SHORT_LETTER
    同類型按出現順序分配 A/B/C...
    """
    alpha: dict[str, int] = {}
    mapping: dict[str, str] = {}
    for rec in sorted(records, key=lambda x: x["start"]):
        ph = rec["placeholder"]
        if ph not in mapping:
            short = rec["short"]
            idx = alpha.get(short, 0)
            mapping[ph] = f"{short}_{ascii_uppercase[idx]}"
            alpha[short] = idx + 1
    return mapping


def apply_mapping(redacted: str, mapping: dict[str, str]) -> str:
    """把佔位符文本套用對照表，產生代號版本。"""
    coded = redacted
    for ph, code in sorted(mapping.items(), key=lambda x: -len(x[0])):
        coded = coded.replace(ph, code)
    return coded


# ─── Full pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(text: str, opf_instance) -> dict:
    """
    執行完整 pipeline。
    回傳：
      original    原始文本
      placeholder 中間態（[SHORT_N] 佔位符版）
      coded       最終輸出（SHORT_LETTER 代號版）
      records     span 明細
      mapping     佔位符 → 代號 對照表
    """
    placeholder, records = stage1_filter(text, opf_instance)
    mapping = stage2_mapping(records)
    coded = apply_mapping(placeholder, mapping)
    return {
        "original":    text,
        "placeholder": placeholder,
        "coded":       coded,
        "records":     records,
        "mapping":     mapping,
    }


# ─── HTML 高亮輔助 ─────────────────────────────────────────────────────────────

def _color(short: str) -> str:
    return LABEL_COLOR.get(short, "#D5D8DC")


def highlight_original(text: str, records: list[dict]) -> str:
    parts: list[str] = []
    last = 0
    for rec in sorted(records, key=lambda x: x["start"]):
        parts.append(escape(text[last:rec["start"]]))
        c = _color(rec["short"])
        parts.append(
            f'<mark style="background:{c};padding:1px 5px;border-radius:3px;'
            f'font-weight:600" title="{rec["short"]}">{escape(rec["original"])}</mark>'
        )
        last = rec["end"]
    parts.append(escape(text[last:]))
    return "".join(parts)


def highlight_placeholder(redacted: str) -> str:
    def repl(m: re.Match) -> str:
        short = m.group(1)
        c = _color(short)
        return (
            f'<mark style="background:{c};padding:1px 5px;border-radius:3px;'
            f'font-weight:600">{escape(m.group(0))}</mark>'
        )
    return re.sub(r'\[([A-Z]+)_(\d+)\]', repl, escape(redacted))


def highlight_coded(coded: str) -> str:
    labels = "|".join(LABEL_MAP.values())
    pattern = rf'\b({labels})_([A-Z])\b'

    def repl(m: re.Match) -> str:
        c = _color(m.group(1))
        return (
            f'<mark style="background:{c};padding:1px 5px;border-radius:3px;'
            f'font-weight:600">{escape(m.group(0))}</mark>'
        )
    return re.sub(pattern, repl, escape(coded))
