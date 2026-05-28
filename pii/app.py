"""
PII Redaction Pipeline Demo
"""
from __future__ import annotations
import atexit
import gc
import streamlit as st
from pipeline import run_pipeline, load_opf, LABEL_MAP
from html import escape
import re as _re

# 確保 streamlit 關閉時釋放 GPU/RAM 模型資源
def _cleanup_model():
    st.cache_resource.clear()
    gc.collect()
atexit.register(_cleanup_model)

st.set_page_config(
    page_title="PII Redaction Pipeline",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS via st.html (no comments, avoids Streamlit 1.57 sanitizer stripping) ──
st.html("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
    --fs: 'DM Sans', Arial, sans-serif;
    --fm: 'DM Mono', 'Courier New', monospace;
    --black: #171717;
    --g100:  #ebebeb;
    --g400:  #808080;
    --g600:  #4d4d4d;
    --develop: #0a72ef;
    --preview: #de1d8d;
    --ship:    #ff5b4f;
}
[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stHeader"],footer {
    display: none !important;
}
.stApp { background: #fff !important; }
.block-container { padding: 0 44px !important; max-width: 100% !important; }
section[data-testid="stMain"] > div:first-child { padding-top: 0 !important; }

.stTextArea textarea {
    font-family: var(--fm) !important;
    font-size: 16px !important;
    line-height: 1.9 !important;
    color: #171717 !important;
    background: #fff !important;
    border: 1.5px solid #d1d5db !important;
    border-radius: 8px !important;
    padding: 16px 18px !important;
    resize: vertical !important;
    box-shadow: none !important;
}
.stTextArea textarea:focus {
    border-color: #0a72ef !important;
    box-shadow: 0 0 0 3px rgba(10,114,239,.1) !important;
    outline: none !important;
}
.stTextArea label { display: none !important; }

.stButton button {
    font-family: var(--fs) !important;
    font-size: 15px !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
    padding: 9px 20px !important;
    border: none !important;
    cursor: pointer !important;
}
.stButton button[kind="primary"] {
    background: #171717 !important;
    color: #fff !important;
}
.stButton button[kind="primary"]:hover { background: #2d2d2d !important; }
.stButton button[kind="secondary"] {
    background: #fff !important;
    color: #171717 !important;
    box-shadow: rgb(235,235,235) 0 0 0 1px !important;
}
.stButton button[kind="secondary"]:hover {
    box-shadow: rgba(0,0,0,0.18) 0 0 0 1px !important;
}

.stSelectbox label {
    font-family: var(--fm) !important;
    font-size: 13px !important;
    letter-spacing: .08em !important;
    text-transform: uppercase !important;
    color: #808080 !important;
    font-weight: 500 !important;
}
.stSelectbox > div > div {
    box-shadow: rgba(0,0,0,0.08) 0 0 0 1px !important;
    border: none !important;
    border-radius: 6px !important;
    background: #fff !important;
    font-family: var(--fs) !important;
    font-size: 16px !important;
    color: #171717 !important;
}

details[data-testid="stExpander"] {
    box-shadow: rgba(0,0,0,0.08) 0 0 0 1px !important;
    border-radius: 8px !important;
    border: none !important;
}
details[data-testid="stExpander"] summary {
    font-family: var(--fs) !important;
    font-size: 16px !important;
    font-weight: 500 !important;
    color: #171717 !important;
    padding: 14px 18px !important;
}
</style>
""")

# ── constants ──────────────────────────────────────────────────────────────────

PII_TAGS = {
    "PERSON":  ("#fff0f0", "#c0392b", "private_person",   "人名（私人個體）",
                "具體真實個人的姓名。公眾人物的公開姓名通常不標記；重點在私人脈絡下的識別。"),
    "ADDRESS": ("#f0fdf4", "#166534", "private_address",  "私人地址",
                "住所、居家或私人活動的實體地址，含街道、門牌、郵遞區號等。"),
    "EMAIL":   ("#eff6ff", "#1d4ed8", "private_email",    "電子郵件",
                "任何 Email 地址，包含個人信箱或含有個人識別資訊的企業信箱。"),
    "PHONE":   ("#f5f3ff", "#6d28d9", "private_phone",    "電話號碼",
                "行動電話、市話、國際碼等各種格式的電話號碼。"),
    "URL":     ("#ecfeff", "#0e7490", "private_url",      "私人 URL",
                "含有個人 token、session ID 或識別資訊的網址；純公開網域通常不標記。"),
    "DATE":    ("#fdf4ff", "#86198f", "private_date",     "私人日期",
                "個人生日、身分證日期、醫療記錄日期等具個資意義的特定日期。"),
    "ACCOUNT": ("#f0fdf4", "#065f46", "account_number",   "帳號 / 識別碼",
                "銀行帳號、信用卡卡號、員工 ID、身分證字號、社會安全碼 (SSN) 等各式帳號。"),
    "SECRET":  ("#fff7ed", "#c2410c", "secret",           "機密資訊",
                "密碼、API key、access token、資料庫連線字串等應保密的憑證或金鑰。"),
}

TEMPLATES = {
    "工程師 Teams 群聊（部署事故）": (
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
    ),
    "跨國業務 Email（中英混雜）": (
        "From: 葉宛青 <wan-ching.yeh@acme-tw.com>\n"
        "To: james.holloway@acme-us.com\n"
        "Subject: Re: Q2 client visit — Jessica Lin 的 profile\n\n"
        "Hi James,\n\n"
        "Per our call 昨天，附上 Jessica 的資料供你 brief 用：\n"
        "Full name: 林映潔 (Jessica Lin)\n"
        "DOB: March 4, 1988\n"
        "Passport: R28847610，expires 2028-11\n"
        "她比較習慣用 jessica.lin.acme@gmail.com 聯絡，\n"
        "office 直線是 +886-2-2709-3300 ext 214。\n\n"
        "她會從 台北市大安區仁愛路四段 300 號 直接搭 Uber 去機場，\n"
        "你那邊 hotel confirmation 記得 cc 她一份。\n\n"
        "Cheers,\n葉宛青"
    ),
    "HR 入職 onboarding 通知": (
        "嗨 Marcus，\n\n"
        "歡迎加入 Synapse！以下是你的入職資訊，\n"
        "麻煩在 5/8 報到前確認一下：\n\n"
        "員工編號：EMP-2026-0442\n"
        "報到地點：新北市板橋區文化路一段 188 號 12F，請找 Michelle 林佩君\n"
        "初始密碼：Synapse@2026!（首次登入後請立即更改）\n"
        "薪轉帳戶請回傳：銀行代碼 + 帳號\n\n"
        "另外 IT 那邊說你的 company email 是 marcus.weber@synapse.io，\n"
        "備援手機請先回填你在履歷上的 +49-151-2034-8876，\n"
        "我們會用那個號碼做 2FA。\n\n"
        "有問題打給我 0933-218-754\n\n"
        "Michelle"
    ),
    "客服對話（保險理賠）": (
        "[Chat transcript — 2026-04-29 14:22]\n\n"
        "客服 Amy: 您好，請問有什麼可以幫您？\n\n"
        "客戶: 我要查理賠進度，上禮拜送出去了\n\n"
        "客服 Amy: 好的，請提供您的保單號碼跟身分證後四碼\n\n"
        "客戶: 保單 LF-2024-887432，身分證 A234567890\n\n"
        "客服 Amy: 謝謝，請問您的聯絡電話跟出生年月日？\n\n"
        "客戶: 0916-334-812，生日 1979/06/03\n\n"
        "客服 Amy: 確認了，您的案件審核中，\n"
        "理賠款會在 5 個工作天匯入您的帳戶 012-345678-001。\n"
        "有問題可以寄信到 claims@fubon-ins.com.tw"
    ),
    "Slack 工程團隊（vendor 整合）": (
        "Nadia Kovač [10:03 AM]\n"
        "hey @daniel can you check the Stripe webhook? 昨晚 payment 一直 fail\n\n"
        "Daniel 吳承翰 [10:05 AM]\n"
        "looking... 你說的是 prod 還是 staging?\n\n"
        "Nadia Kovač [10:06 AM]\n"
        "prod, customer Sophie Müller (sophie.mueller@web.de) 說她 card 被扣了但 order 沒過\n\n"
        "Daniel 吳承翰 [10:08 AM]\n"
        "找到了，webhook secret 過期，先用這個 whsec_EXAMPLE_Kp3mNvQ7rLxT2bWfYcJdZeOs\n"
        "等下我去 dashboard 補一組正式的\n\n"
        "Nadia Kovač [10:09 AM]\n"
        "ok 我先手動 refund Sophie，她的卡號尾碼 4892，方便追\n\n"
        "Daniel 吳承翰 [10:10 AM]\n"
        "記得 incident report 要填 sophie 的 email 跟交易時間 2026-04-28 23:41 UTC"
    ),
    "業務 CRM 備忘（中日混雜）": (
        "客戶拜訪紀錄 2026-04-25\n\n"
        "客戶：田中浩二（Tanaka Koji）\n"
        "職稱：General Manager, Osaka Branch\n"
        "聯絡：tanaka.koji@nippon-trading.co.jp / 090-3344-5566\n"
        "地址：大阪市北区梅田2丁目4-9 ブリーゼタワー 18F\n\n"
        "會議摘要：\n"
        "田中先生 prefer 用 LINE 聯絡，ID 是 tanakakoji_ntc\n"
        "下次 meeting 訂 5月14日，他說可以飛台北，\n"
        "請幫他 book 台北君悅，check-in 5/13，需要 receipt 給公司報銷\n"
        "信用卡他說用公司卡 5412-7534-2210-8831，exp 09/28\n\n"
        "Follow-up by Kevin at kevin.chang@our-company.com"
    ),
    "資安事件回報 Email": (
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
        "目前 IP 38.242.101.77 有異常 API call，已 block。\n\n"
        "需要法務評估是否觸發個資法通報義務。\n\n"
        "IT Security Team"
    ),
    "跨部門會議記錄（口語混搭）": (
        "【會議記錄】產品 x 設計 sync — 2026-04-30\n\n"
        "With: Kevin(PM), 小雯(Design), Ray Huang, Ananya Patel(Eng)\n\n"
        "Action items：\n\n"
        "1. Ray 負責把 onboarding flow 的 wireframe 傳給 Ananya，\n"
        "   deadline 5/3，有問題 email ray.huang@product.io\n\n"
        "2. 小雯說 user research 受訪者資料要保密：\n"
        "   受訪者 A：Jennifer Wu, jen.wu.ux@gmail.com, 0987-654-321\n"
        "   受訪者 B：Michael 謝宗翰, m.hsieh@outlook.com, 住新竹市東區\n\n"
        "3. Ananya 的 staging URL 先不對外，token 是 stg_tk_9fXmP2kRvW4nQ\n\n"
        "下次 sync 5/7 10am，Zoom link 固定，密碼 synapse2026"
    ),
}

# ── highlight helpers ──────────────────────────────────────────────────────────

def _tag_style(short: str) -> str:
    bg, fg = PII_TAGS[short][0], PII_TAGS[short][1]
    return f"background:{bg};color:{fg};border-radius:3px;padding:2px 6px;font-weight:500"

def v_original(text: str, records: list[dict]) -> str:
    parts, last = [], 0
    for r in sorted(records, key=lambda x: x["start"]):
        parts.append(escape(text[last:r["start"]]))
        parts.append(
            f'<mark style="{_tag_style(r["short"])}" title="{r["short"]}">'
            f'{escape(r["original"])}</mark>'
        )
        last = r["end"]
    parts.append(escape(text[last:]))
    return "".join(parts)

def v_placeholder(redacted: str) -> str:
    parts, last = [], 0
    for m in _re.finditer(r'\[([A-Z]+)_(\d+)\]', redacted):
        parts.append(escape(redacted[last:m.start()]))
        parts.append(f'<mark style="{_tag_style(m.group(1))}">{escape(m.group(0))}</mark>')
        last = m.end()
    parts.append(escape(redacted[last:]))
    return "".join(parts)

def v_coded(coded: str) -> str:
    pat = rf'\b({"|".join(LABEL_MAP.values())})_([A-Z])\b'
    parts, last = [], 0
    for m in _re.finditer(pat, coded):
        parts.append(escape(coded[last:m.start()]))
        parts.append(f'<mark style="{_tag_style(m.group(1))}">{escape(m.group(0))}</mark>')
        last = m.end()
    parts.append(escape(coded[last:]))
    return "".join(parts)

# ── session state ──────────────────────────────────────────────────────────────

if "text_area" not in st.session_state:
    st.session_state["text_area"] = list(TEMPLATES.values())[0]
if "result" not in st.session_state:
    st.session_state.result = None

# ── model ──────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="載入 Privacy Filter 模型中，請稍候...")
def get_opf():
    return load_opf(device="cpu")

# ── helpers for inline HTML ────────────────────────────────────────────────────

F  = "'DM Sans', Arial, sans-serif"
FM = "'DM Mono', 'Courier New', monospace"

def card(content: str, pad: str = "20px 24px") -> str:
    return (
        f'<div style="box-shadow:rgba(0,0,0,0.08) 0 0 0 1px,'
        f'rgba(0,0,0,0.04) 0 2px 2px,#fafafa 0 0 0 1px;'
        f'border-radius:8px;padding:{pad};background:#fff">{content}</div>'
    )

def mono_label(text: str) -> str:
    return (
        f'<div style="font-family:{F};font-size:15px;font-weight:600;letter-spacing:.06em;'
        f'text-transform:uppercase;color:#808080;margin-bottom:10px">{text}</div>'
    )

# ══════════════════════════════════════════════════════════════════════════════
# PAGE
# ══════════════════════════════════════════════════════════════════════════════

# ── header ────────────────────────────────────────────────────────────────────
st.html(f"""
<div style="padding:36px 0 28px;border-bottom:1px solid #ebebeb;margin-bottom:0">
  <div style="font-family:{F};font-size:15px;font-weight:600;letter-spacing:.08em;
              text-transform:uppercase;color:#808080;margin-bottom:10px">
    Master Thesis · Privacy Infrastructure · OpenAI Privacy Filter
  </div>
  <div style="font-family:{F};font-size:36px;font-weight:600;
              letter-spacing:-1.5px;color:#171717;line-height:1.1;margin-bottom:12px">
    PII Redaction Pipeline
  </div>
  <div style="font-family:{F};font-size:17px;color:#4d4d4d;line-height:1.7">
    輸入對話 →
    <span style="background:#e8f2ff;color:#0a72ef;border-radius:9999px;
                 padding:3px 12px;font-size:14px;font-weight:500;margin:0 4px">
      原始文本</span>→
    <span style="background:#fce8f4;color:#de1d8d;border-radius:9999px;
                 padding:3px 12px;font-size:14px;font-weight:500;margin:0 4px">
      Privacy Filter 輸出</span>
    ·&nbsp;即時對比 PII 偵測結果
  </div>
</div>
""")

# ── pipeline info cards ────────────────────────────────────────────────────────
i1 = card(f"""
  {mono_label("執行流程")}
  <div style="font-family:{F};font-size:16px;color:#171717;line-height:1.8">
    輸入文本 → <strong>OpenAI Privacy Filter</strong> 本地推論（單次 forward pass）→
    偵測 PII span → 產生
    <code style="background:#f3f4f6;padding:2px 6px;border-radius:3px;font-size:14px">[SHORT_N]</code>
    佔位符取代原始敏感詞
  </div>
""")
i2 = card(f"""
  {mono_label("模型特性")}
  <div style="font-family:{F};font-size:16px;color:#171717;line-height:1.8">
    <strong>Token classifier</strong>，非生成模型，結果<strong>固定不變</strong>（相同輸入每次輸出相同）。
    1.5B total / 50M active params，F1 97%，128K context，Apache 2.0 授權。
  </div>
""")
i3 = card(f"""
  {mono_label("顏色說明")}
  <div style="font-family:{F};font-size:16px;color:#171717;line-height:1.8">
    左右兩欄<strong>同一筆 PII 使用相同顏色</strong>，顏色由類型決定。
    左欄高亮原始詞；右欄高亮對應的
    <code style="background:#f3f4f6;padding:2px 6px;border-radius:3px;font-size:14px">[PERSON_1]</code>
    佔位符，便於逐筆核對偵測結果。
  </div>
""")
st.html(f"""
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;padding:24px 0 20px">
  {i1}{i2}{i3}
</div>
""")

# ── PII types expander ─────────────────────────────────────────────────────────
with st.expander("模型可識別的 PII 類型（8 種）— 點擊展開", expanded=False):
    cells = ""
    for short, (bg, fg, label_key, zh_name, desc) in PII_TAGS.items():
        cells += (
            f'<div style="box-shadow:rgba(0,0,0,0.08) 0 0 0 1px,'
            f'rgba(0,0,0,0.04) 0 2px 2px,#fafafa 0 0 0 1px;'
            f'border-radius:8px;padding:16px 18px;background:#fff">'
            f'<span style="background:{bg};color:{fg};border-radius:9999px;'
            f'padding:3px 12px;font-family:{FM};font-size:13px;font-weight:500">{short}</span>'
            f'<div style="font-family:{F};font-size:15px;font-weight:600;'
            f'color:#171717;margin:10px 0 5px">{zh_name}</div>'
            f'<div style="font-family:{F};font-size:14px;color:#4d4d4d;line-height:1.7">{desc}</div>'
            f'<div style="font-family:{FM};font-size:12px;color:#808080;'
            f'margin-top:8px;letter-spacing:.04em">{label_key}</div>'
            f'</div>'
        )
    st.html(
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);'
        f'gap:12px;padding:8px 0 4px">{cells}</div>'
    )

# ── input section ──────────────────────────────────────────────────────────────
st.html(f'<div style="height:8px"></div>'
        f'{mono_label("對話輸入")}')

# label 單獨一行，下方兩個 widget 無 label，自然對齊
st.html(f'<div style="font-family:{F};font-size:16px;font-weight:600;letter-spacing:.04em;'
        f'text-transform:uppercase;color:#808080;margin-bottom:6px">套用對話範本</div>')
t_col, apply_col = st.columns([5, 1])
with t_col:
    chosen_tpl = st.selectbox(
        "套用對話範本",
        options=list(TEMPLATES.keys()),
        index=0,
        label_visibility="collapsed",
    )
with apply_col:
    if st.button("套用範本", type="secondary", use_container_width=True):
        st.session_state["text_area"] = TEMPLATES[chosen_tpl]
        st.session_state.result = None
        st.rerun()

text_val = st.text_area(
    "input",
    height=200,
    key="text_area",
    label_visibility="collapsed",
)

run_col, _ = st.columns([1, 9])
with run_col:
    run_clicked = st.button("▶  執行過濾", type="primary", use_container_width=True)

st.html("<div style='height:8px;border-bottom:1px solid #ebebeb'></div>")

# ── run pipeline ───────────────────────────────────────────────────────────────
if run_clicked and text_val.strip():
    with st.spinner("執行 Privacy Filter..."):
        try:
            opf = get_opf()
            st.session_state.result = run_pipeline(text_val, opf)
        except Exception as e:
            st.error(f"執行失敗：{e}")
            st.session_state.result = None

# ── stage display ──────────────────────────────────────────────────────────────
result = st.session_state.result

EMPTY_BODY = (
    f'<div style="height:100%;display:flex;flex-direction:column;align-items:center;'
    f'justify-content:center;gap:10px;padding:48px 0">'
    f'<div style="width:28px;height:28px;border-radius:50%;border:1.5px solid #ebebeb"></div>'
    f'<div style="font-family:{FM};font-size:12px;letter-spacing:.1em;'
    f'text-transform:uppercase;color:#c8c8c8">Awaiting input</div>'
    f'</div>'
)

h1 = v_original(result["original"], result["records"]) if result else EMPTY_BODY
h2 = v_placeholder(result["placeholder"])              if result else EMPTY_BODY
h3 = v_coded(result["coded"])                          if result else EMPTY_BODY

CARD_STYLE = (
    f"box-shadow:rgba(0,0,0,0.08) 0 0 0 1px,rgba(0,0,0,0.04) 0 2px 2px,#fafafa 0 0 0 1px;"
    f"border-radius:8px;padding:22px 24px;background:#fff;"
    f"font-family:{FM};font-size:16px;line-height:2.1;"
    f"color:#171717;white-space:pre-wrap;word-break:break-word;"
    f"overflow-y:auto;min-height:380px"
)

def stage_header(badge_bg: str, badge_fg: str, num: str, name: str, tag: str) -> str:
    return (
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'
        f'<span style="background:{badge_bg};color:{badge_fg};border-radius:4px;'
        f'padding:3px 10px;font-family:{FM};font-size:12px;font-weight:500">{num}</span>'
        f'<span style="font-family:{F};font-size:17px;font-weight:600;'
        f'color:#171717;letter-spacing:-.3px">{name}</span>'
        f'<span style="margin-left:auto;font-family:{FM};font-size:12px;color:#808080">{tag}</span>'
        f'</div>'
    )

st.html(f"""
<div style="display:grid;grid-template-columns:1fr 52px 1fr;
            align-items:stretch;gap:0;padding:28px 0">

  <div style="display:flex;flex-direction:column">
    {stage_header("#e8f2ff","#0a72ef","原始文本","輸入","RAW INPUT")}
    <div style="{CARD_STYLE}">{h1}</div>
  </div>

  <div style="display:flex;align-items:flex-start;justify-content:center;
              padding-top:46px;color:#d1d5db;font-size:22px">&#8594;</div>

  <div style="display:flex;flex-direction:column">
    {stage_header("#fce8f4","#de1d8d","Privacy Filter 輸出","偵測結果","REDACTED")}
    <div style="{CARD_STYLE}">{h2}</div>
  </div>

</div>
<div style="border-bottom:1px solid #ebebeb"></div>
""")

# ── mapping table + stats ──────────────────────────────────────────────────────
if result and result["mapping"]:
    records = result["records"]
    mapping = result["mapping"]

    rows = ""
    for i, rec in enumerate(sorted(records, key=lambda x: x["start"]), 1):
        ph = rec["placeholder"]
        bg, fg = PII_TAGS.get(rec["short"], ("#f3f4f6", "#374151", "", "", ""))[:2]
        rows += (
            f'<tr style="border-bottom:1px solid #ebebeb">'
            f'<td style="padding:11px 16px 11px 0;font-family:{F};'
            f'font-size:13px;font-weight:600;color:#808080">#{i}</td>'
            f'<td style="padding:11px 16px 11px 0">'
            f'  <span style="background:{bg};color:{fg};border-radius:9999px;'
            f'  padding:3px 11px;font-family:{F};font-size:13px;'
            f'  font-weight:600">{rec["short"]}</span></td>'
            f'<td style="padding:11px 16px 11px 0;font-family:{F};'
            f'font-size:13px;font-weight:600;color:#666">{rec["label"]}</td>'
            f'<td style="padding:11px 16px 11px 0;font-family:{F};'
            f'font-size:15px;font-weight:600;color:#171717">'
            f'{escape(rec["original"])}</td>'
            f'<td style="padding:11px 0;font-family:{F};font-size:14px;'
            f'font-weight:600;color:#4d4d4d">{ph}</td>'
            f'</tr>'
        )

    th = (
        f'<th style="text-align:left;padding:6px 16px 10px 0;font-family:{F};'
        f'font-size:14px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;'
        f'color:#808080;border-bottom:1px solid #ebebeb">'
    )

    n_pii   = len(records)
    n_types = len({r["short"] for r in records})

    stat_cards = "".join(
        f'<div style="box-shadow:rgba(0,0,0,0.08) 0 0 0 1px,rgba(0,0,0,0.04) 0 2px 2px,'
        f'#fafafa 0 0 0 1px;border-radius:8px;padding:22px 26px;background:#fff">'
        f'<div style="font-size:44px;font-weight:600;letter-spacing:-2px;'
        f'color:#171717;line-height:1;margin-bottom:6px">{v}</div>'
        f'<div style="font-family:{F};font-size:15px;font-weight:600;letter-spacing:.06em;'
        f'text-transform:uppercase;color:#808080">{label}</div></div>'
        for v, label in [
            (n_pii,         "PII Detected"),
            (n_types,       "Types Found"),
            (len(text_val), "Input Chars"),
        ]
    )

    st.html(f"""
<div style="padding:28px 0 0">
  {mono_label("偵測結果明細")}
  <table style="width:100%;border-collapse:collapse">
    <thead><tr>
      {th}#</th>
      {th}Type</th>
      {th}Model Label</th>
      {th}Original Value</th>
      {th}Placeholder</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;padding:28px 0 52px">
  {stat_cards}
</div>
""")
