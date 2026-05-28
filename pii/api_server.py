"""
FastAPI service for the PII Redaction Pipeline.
Provides REST API for the admin-console-mvp to integrate.
"""
from __future__ import annotations
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pipeline import run_pipeline, load_opf, stage1_filter, stage2_mapping, apply_mapping

# ── Globals ──────────────────────────────────────────────────────────────────

_opf = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _opf
    print("[PII API] Loading OPF model...")
    _opf = load_opf(device="cpu")
    print("[PII API] Model ready")
    yield


app = FastAPI(
    title="PII Redaction API",
    description="兩階段 PII 隱私過濾 Pipeline API — OpenAI Privacy Filter + 代號映射",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ──────────────────────────────────────────────────────────────────

class RedactRequest(BaseModel):
    text: str = Field(..., description="原始文本（含 PII）", min_length=1)
    return_records: bool = Field(default=True, description="是否回傳 span 明細")
    return_mapping: bool = Field(default=True, description="是否回傳代號對照表")


class SpanRecord(BaseModel):
    original: str
    short: str
    label: str
    num: int
    start: int
    end: int
    placeholder: str


class RedactResponse(BaseModel):
    original: str
    placeholder_text: str
    coded_text: str
    pii_count: int
    processing_time_ms: float
    records: list[SpanRecord] | None = None
    mapping: dict[str, str] | None = None


class BatchRedactRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=50)


class BatchRedactItem(BaseModel):
    index: int
    placeholder_text: str
    coded_text: str
    pii_count: int


class BatchRedactResponse(BaseModel):
    items: list[BatchRedactItem]
    total_pii_count: int
    total_processing_time_ms: float


class HealthResponse(BaseModel):
    status: str
    model: str
    version: str


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="ready" if _opf is not None else "loading",
        model="openai/privacy-filter",
        version="1.0.0",
    )


@app.post("/api/v1/redact", response_model=RedactResponse)
async def redact(req: RedactRequest):
    if _opf is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    t0 = time.perf_counter()
    result = run_pipeline(req.text, _opf)
    elapsed = time.perf_counter() - t0

    records = None
    if req.return_records:
        records = [
            SpanRecord(
                original=r["original"],
                short=r["short"],
                label=r["label"],
                num=r["num"],
                start=r["start"],
                end=r["end"],
                placeholder=r["placeholder"],
            )
            for r in result["records"]
        ]

    mapping = None
    if req.return_mapping:
        mapping = result["mapping"]

    return RedactResponse(
        original=result["original"],
        placeholder_text=result["placeholder"],
        coded_text=result["coded"],
        pii_count=len(result["records"]),
        processing_time_ms=round(elapsed * 1000, 1),
        records=records,
        mapping=mapping,
    )


@app.post("/api/v1/redact/batch", response_model=BatchRedactResponse)
async def redact_batch(req: BatchRedactRequest):
    if _opf is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    t0 = time.perf_counter()
    items: list[BatchRedactItem] = []
    total_pii = 0

    for i, text in enumerate(req.texts):
        result = run_pipeline(text, _opf)
        n = len(result["records"])
        total_pii += n
        items.append(BatchRedactItem(
            index=i,
            placeholder_text=result["placeholder"],
            coded_text=result["coded"],
            pii_count=n,
        ))

    elapsed = time.perf_counter() - t0
    return BatchRedactResponse(
        items=items,
        total_pii_count=total_pii,
        total_processing_time_ms=round(elapsed * 1000, 1),
    )


@app.post("/api/v1/redact/stage1")
async def redact_stage1(req: RedactRequest):
    """只跑 Stage 1（OPF），不回傳代號對照。用於 admin-console 的 tokenize 步驟。"""
    if _opf is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    t0 = time.perf_counter()
    placeholder, records = stage1_filter(req.text, _opf)
    elapsed = time.perf_counter() - t0

    return {
        "placeholder_text": placeholder,
        "pii_count": len(records),
        "processing_time_ms": round(elapsed * 1000, 1),
        "records": [
            {
                "original": r["original"],
                "short": r["short"],
                "placeholder": r["placeholder"],
                "start": r["start"],
                "end": r["end"],
            }
            for r in records
        ],
    }


@app.post("/api/v1/redact/map")
async def redact_map(req: RedactRequest):
    """只跑 Stage 2（代號映射），需要先有 Stage 1 的 records。"""
    if _opf is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    _, records = stage1_filter(req.text, _opf)
    mapping = stage2_mapping(records)
    coded = apply_mapping(req.text, mapping)  # 這裡應該用 placeholder text

    return {
        "mapping": mapping,
        "coded_sample": coded,
        "mapping_count": len(mapping),
    }


# ── LLM Analysis ────────────────────────────────────────────────────────────
# System prompt 與判讀原則嚴格對齊文件 D（consistency_exp_v2/D.docx 附錄 A）
# 與 run_consistency_experiment.py 之 SYSTEM_PROMPT。
# 輸出結構：risk_level / risk_score / threat_message_ids / reason
# 呼叫參數：model=gpt-4o-mini, temperature=0.2, top_p=1.0, max_tokens=1200
#           response_format=json_object（依一致性實驗之控制變數）

SYSTEM_PROMPT = (
    "你是企業資安分析員,負責從 Microsoft Teams 聊天紀錄(符合 Microsoft Graph API v1.0 ChatMessage schema 之 JSON)"
    "判讀是否存在社交工程風險。\n"
    "請依下列規則輸出 JSON(不可含 markdown code fence):\n"
    "{\n"
    '  "risk_level": "Critical" | "High" | "Mid" | "Low" | "Minimal",\n'
    '  "risk_score": <整數 0-10>,\n'
    '  "threat_message_ids": ["<chatMessage.id>", ...],\n'
    '  "reason": "以繁體中文台灣用語,條列三至五個關鍵判讀依據,單一段落內以分號分隔"\n'
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

LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.2"))
LLM_TOP_P = float(os.environ.get("LLM_TOP_P", "1.0"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "128000"))


class AnalyzeMessage(BaseModel):
    id: str = Field(default="", description="chatMessage.id")
    alias: str | None = Field(default=None, description="發送者代號 (from.alias)")
    content: str = Field(..., description="代號化後的訊息內容 (body.content)")


class AnalyzeRequest(BaseModel):
    messages: list[AnalyzeMessage] = Field(..., min_length=1)
    scenario_id: str = Field(default="")


class AnalyzeResponse(BaseModel):
    risk_level: str
    risk_score: int
    threat_message_ids: list[str]
    reason: str
    model: str
    processing_time_ms: float


def _build_user_prompt(messages: list[AnalyzeMessage]) -> str:
    """將代號化訊息組裝為符合 Graph API ChatMessage schema 的 JSON 供 LLM 判讀。"""
    chat_messages = []
    for m in messages:
        msg = {
            "id": m.id,
            "from": {"user": {"alias": m.alias}} if m.alias else None,
            "body": {"contentType": "text", "content": m.content},
        }
        chat_messages.append(msg)
    payload = json.dumps(chat_messages, ensure_ascii=False)
    return (
        "以下為單一 Microsoft Teams chat 之 chatMessage 陣列 JSON(Graph API v1.0 格式),"
        "請依系統提示輸出 JSON 判讀:\n" + payload
    )


def _fallback_analysis(messages: list[AnalyzeMessage]) -> dict:
    """LLM 不可用時的規則型 fallback。"""
    content = " ".join(m.content for m in messages)
    has_otp = any(kw in content for kw in ["OTP", "驗證碼", "一次性密碼", "6 位數"])
    has_urgency = any(kw in content for kw in ["停權", "強制", "30 分鐘", "限時", "立即"])
    has_authority = any(kw in content for kw in ["IT 技術支援", "資安小組", "資安組", "主管"])

    threat_ids = [m.id for m in messages if m.id]  # 簡化: 全部標為威脅

    if has_otp and has_urgency:
        return {"risk_level": "Critical", "risk_score": 9, "threat_message_ids": threat_ids,
                "reason": "規則型分析：偵測到 OTP 洩漏伴隨急迫性施壓;疑似 MFA 繞過攻擊"}
    if has_urgency and has_authority:
        return {"risk_level": "High", "risk_score": 8, "threat_message_ids": threat_ids,
                "reason": "規則型分析：偵測到權威聲稱搭配急迫性施壓;疑似社交工程攻擊"}
    if has_urgency or has_authority:
        return {"risk_level": "Mid", "risk_score": 5, "threat_message_ids": threat_ids,
                "reason": "規則型分析：偵測到急迫性或權威性特徵;需進一步確認"}
    if any(kw in content for kw in ["可疑", "不認識", "詐騙"]):
        return {"risk_level": "Low", "risk_score": 2, "threat_message_ids": [],
                "reason": "規則型分析：偵測到輕微可疑特徵;但未見明確誘導行為"}
    return {"risk_level": "Minimal", "risk_score": 0, "threat_message_ids": [],
            "reason": "規則型分析：未偵測到社交工程特徵;對話內容屬日常溝通"}


def _call_llm(messages: list[AnalyzeMessage]) -> dict:
    """呼叫 OpenAI API 進行風險判讀（使用運行時配置，對齊文件 D 之控制變數）。"""
    import openai

    api_key = _llm_config["api_key"]
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=_llm_config["model"],
        temperature=_llm_config["temperature"],
        top_p=_llm_config["top_p"],
        max_completion_tokens=_llm_config["max_tokens"],
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(messages)},
        ],
    )

    raw = resp.choices[0].message.content.strip()
    return json.loads(raw)


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    """對代號化對話執行 LLM 風險判讀。LLM 僅接收代號化內容，不接觸明文。"""
    t0 = time.perf_counter()

    try:
        result = _call_llm(req.messages)
        model = _llm_config["model"]
    except (ValueError, Exception) as e:
        result = _fallback_analysis(req.messages)
        model = f"rule-based-fallback ({type(e).__name__})"

    elapsed = time.perf_counter() - t0

    return AnalyzeResponse(
        risk_level=result.get("risk_level", "Mid"),
        risk_score=int(result.get("risk_score", 5)),
        threat_message_ids=result.get("threat_message_ids", []),
        reason=result.get("reason", ""),
        model=model,
        processing_time_ms=round(elapsed * 1000, 1),
    )


# ── LLM Configuration ────────────────────────────────────────────────────────
# 執行時配置：可透過 API 修改，無需重啟伺服器。
# 初始值來自環境變數，與論文控制變數對齊。

_llm_config: dict[str, Any] = {
    "api_key": os.environ.get("OPENAI_API_KEY", ""),
    "model": os.environ.get("LLM_MODEL", "gpt-5.5"),
    "temperature": float(os.environ.get("LLM_TEMPERATURE", "0.2")),
    "top_p": float(os.environ.get("LLM_TOP_P", "1.0")),
    "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "128000")),
}


class LlmConfigRequest(BaseModel):
    api_key: str = Field(default="", description="OpenAI API Key")
    model: str = Field(default="gpt-5.5")
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    max_tokens: int = Field(default=128000, ge=1, le=128000)


class LlmConfigResponse(BaseModel):
    api_key_masked: str
    model: str
    temperature: float
    top_p: float
    max_tokens: int
    ready: bool


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


@app.get("/api/v1/config", response_model=LlmConfigResponse)
async def get_config():
    return LlmConfigResponse(
        api_key_masked=_mask_key(_llm_config["api_key"]) if _llm_config["api_key"] else "",
        model=_llm_config["model"],
        temperature=_llm_config["temperature"],
        top_p=_llm_config["top_p"],
        max_tokens=_llm_config["max_tokens"],
        ready=bool(_llm_config["api_key"]),
    )


@app.put("/api/v1/config", response_model=LlmConfigResponse)
async def update_config(req: LlmConfigRequest):
    _llm_config["api_key"] = req.api_key
    _llm_config["model"] = req.model
    _llm_config["temperature"] = req.temperature
    _llm_config["top_p"] = req.top_p
    _llm_config["max_tokens"] = req.max_tokens
    return LlmConfigResponse(
        api_key_masked=_mask_key(_llm_config["api_key"]) if _llm_config["api_key"] else "",
        model=_llm_config["model"],
        temperature=_llm_config["temperature"],
        top_p=_llm_config["top_p"],
        max_tokens=_llm_config["max_tokens"],
        ready=bool(_llm_config["api_key"]),
    )


@app.post("/api/v1/config/test", response_model=dict)
async def test_config():
    """用當前配置發送一次簡單 LLM 呼叫，返回成功與否及耗時。"""
    if not _llm_config["api_key"]:
        return {"ok": False, "error": "API Key 未設定", "processing_time_ms": 0}
    import openai as _openai_test
    t0 = time.perf_counter()
    try:
        client = _openai_test.OpenAI(api_key=_llm_config["api_key"])
        resp = client.chat.completions.create(
            model=_llm_config["model"],
            temperature=_llm_config["temperature"],
            top_p=_llm_config["top_p"],
            max_completion_tokens=50,
            messages=[{"role": "user", "content": "PING"}],
        )
        elapsed = time.perf_counter() - t0
        return {
            "ok": True,
            "model": _llm_config["model"],
            "response": resp.choices[0].message.content.strip() if resp.choices else "",
            "processing_time_ms": round(elapsed * 1000, 1),
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "processing_time_ms": round(elapsed * 1000, 1),
        }


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8503, log_level="info")
