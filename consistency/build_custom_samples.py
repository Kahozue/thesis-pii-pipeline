"""建立 3 組自製 Graph API Schema 合規樣本,補足測試池至 6 組。"""
import json
import os
from pathlib import Path

BASE = Path(__file__).parent


def msg(mid, reply_to, dt, sender_id, sender_name, importance, content, content_type="text", mentions=None):
    return {
        "id": mid,
        "replyToId": reply_to,
        "etag": mid,
        "messageType": "message",
        "createdDateTime": dt,
        "lastModifiedDateTime": dt,
        "lastEditedDateTime": None,
        "deletedDateTime": None,
        "subject": None,
        "summary": None,
        "chatId": None,
        "importance": importance,
        "locale": "zh-tw",
        "webUrl": None,
        "channelIdentity": None,
        "policyViolation": None,
        "eventDetail": None,
        "from": {
            "application": None,
            "device": None,
            "user": {
                "@odata.type": "#microsoft.graph.teamworkUserIdentity",
                "id": sender_id,
                "displayName": sender_name,
                "userIdentityType": "aadUser",
                "tenantId": "9a8b7c6d-5e4f-3a2b-1c0d-9e8f7a6b5c4d",
            },
        },
        "body": {"contentType": content_type, "content": content},
        "attachments": [],
        "mentions": mentions or [],
        "reactions": [],
        "messageHistory": [],
    }


def wrap(chat_id, messages):
    for m in messages:
        m["chatId"] = chat_id
    return {"chatId": chat_id, "messages": messages}


# ---------------- Scenario D: 假 HR 薪資系統釣魚 (credential phishing) ----------------
D_CHAT = "19:d1f2a3b4-5c6d-7e8f-9012-aabbccddeeff_u1u2u3u4-0000-4000-8000-000000000001@unq.gbl.spaces"
D_HR = "d0000001-aaaa-4aaa-8aaa-000000000001"
D_USER = "d0000002-aaaa-4aaa-8aaa-000000000002"
d_msgs = [
    msg("d0000000-0000-4000-8000-000000000001", None, "2026-04-17T09:02:11+08:00", D_HR,
        "吳怡君(人資/Payroll)", "high",
        "您好,因應集團薪資系統升級,請於今日 17:00 前至 https://payroll-login.corp-hr-portal.com 重新驗證帳號,逾期將影響本月薪資入帳。"),
    msg("d0000000-0000-4000-8000-000000000002", "d0000000-0000-4000-8000-000000000001", "2026-04-17T09:10:52+08:00", D_USER,
        "陳柏翰", "normal",
        "怡君姐好,我剛看了公告平台沒有看到相關通知,這個連結看起來不是我們公司的網域,麻煩幫我確認一下。"),
    msg("d0000000-0000-4000-8000-000000000003", "d0000000-0000-4000-8000-000000000002", "2026-04-17T09:12:05+08:00", D_HR,
        "吳怡君(人資/Payroll)", "high",
        "這次是委外廠商負責的介面,時間很趕,集團今天下午就要做資料同步,請您先用公司帳號登入驗證,否則薪資系統會把您列為『未驗證員工』,下個月薪水會先凍結。"),
    msg("d0000000-0000-4000-8000-000000000004", "d0000000-0000-4000-8000-000000000003", "2026-04-17T09:15:22+08:00", D_USER,
        "陳柏翰", "normal",
        "了解,但我還是想先打電話跟 IT 確認,可以給我您的分機嗎?"),
    msg("d0000000-0000-4000-8000-000000000005", "d0000000-0000-4000-8000-000000000004", "2026-04-17T09:16:40+08:00", D_HR,
        "吳怡君(人資/Payroll)", "urgent",
        "我現在在外面會議,分機沒人接,麻煩您直接用公司 AD 帳號跟密碼登入那個連結就好,五分鐘的事。"),
    msg("d0000000-0000-4000-8000-000000000006", "d0000000-0000-4000-8000-000000000005", "2026-04-17T09:19:02+08:00", D_USER,
        "陳柏翰", "normal",
        "好的,我還是想先跟我主管確認過再處理,謝謝。"),
]
D = wrap(D_CHAT, d_msgs)


# ---------------- Scenario E: 供應商發票變更(BEC 中風險) ----------------
E_CHAT = "19:e5d4c3b2-1a09-4877-9f6e-112233445566_v1v2v3v4-0000-4000-8000-000000000002@unq.gbl.spaces"
E_VENDOR = "e0000001-bbbb-4bbb-8bbb-000000000001"
E_FIN = "e0000002-bbbb-4bbb-8bbb-000000000002"
e_msgs = [
    msg("e0000000-0000-4000-8000-000000000001", None, "2026-04-16T14:20:03+08:00", E_VENDOR,
        "Maria Lee / Evertek Supplies", "normal",
        "Hi Jessica, attached is the updated invoice EV-2026-0331 for the Q1 shipment. Total USD 48,500.",
        content_type="html"),
    msg("e0000000-0000-4000-8000-000000000002", "e0000000-0000-4000-8000-000000000001", "2026-04-16T14:45:17+08:00", E_FIN,
        "黃珮穎(應付帳款)", "normal",
        "Hi Maria, 收到,我這邊確認 PO 編號後安排月底付款。"),
    msg("e0000000-0000-4000-8000-000000000003", "e0000000-0000-4000-8000-000000000002", "2026-04-16T16:02:48+08:00", E_VENDOR,
        "Maria Lee / Evertek Supplies", "high",
        "One more note — our bank has changed. Please remit to the new account on the invoice (HSBC HK, A/C 812-xxxx-5566). The old Taiwan account will bounce from Apr 18."),
    msg("e0000000-0000-4000-8000-000000000004", "e0000000-0000-4000-8000-000000000003", "2026-04-16T16:11:30+08:00", E_FIN,
        "黃珮穎(應付帳款)", "normal",
        "Maria 您好,變更收款銀行需要貴司蓋章的正式變更函並重新走供應商主檔變更流程,我這邊沒辦法只看 email 就改匯款帳戶。"),
    msg("e0000000-0000-4000-8000-000000000005", "e0000000-0000-4000-8000-000000000004", "2026-04-16T16:14:05+08:00", E_VENDOR,
        "Maria Lee / Evertek Supplies", "urgent",
        "I understand but our CFO needs this invoice paid tomorrow to release next batch. Can you do it this once and we submit the paperwork next week?"),
    msg("e0000000-0000-4000-8000-000000000006", "e0000000-0000-4000-8000-000000000005", "2026-04-16T16:18:44+08:00", E_FIN,
        "黃珮穎(應付帳款)", "normal",
        "抱歉無法,我會把這個請求同步給我們採購窗口張經理,請您等待正式回覆。"),
]
E = wrap(E_CHAT, e_msgs)


# ---------------- Scenario F: 同事臨時幫忙(正常低風險 / 邊界案例) ----------------
F_CHAT = "19:f9e8d7c6-5b4a-4320-9f1e-778899aabbcc_w1w2w3w4-0000-4000-8000-000000000003@unq.gbl.spaces"
F_A = "f0000001-cccc-4ccc-8ccc-000000000001"
F_B = "f0000002-cccc-4ccc-8ccc-000000000002"
f_msgs = [
    msg("f0000000-0000-4000-8000-000000000001", None, "2026-04-18T10:05:12+08:00", F_A,
        "王建宏", "normal",
        "建宏這邊,等等我要出門跟客戶開會,會議室的電視 HDMI 線好像被借走了,你那邊辦公桌抽屜有多的嗎?"),
    msg("f0000000-0000-4000-8000-000000000002", "f0000000-0000-4000-8000-000000000001", "2026-04-18T10:06:33+08:00", F_B,
        "林孟臻", "normal",
        "我剛看了一下,我這有一條 1.5 公尺的,你直接到我位置拿沒關係,我到 11 點都在。"),
    msg("f0000000-0000-4000-8000-000000000003", "f0000000-0000-4000-8000-000000000002", "2026-04-18T10:08:11+08:00", F_A,
        "王建宏", "normal",
        "太好了謝謝!另外 Q2 那份簡報我昨天給你的版本,你如果有空麻煩看一下第 7 頁的數字對不對,我等下會議會用到。"),
    msg("f0000000-0000-4000-8000-000000000004", "f0000000-0000-4000-8000-000000000003", "2026-04-18T10:12:44+08:00", F_B,
        "林孟臻", "normal",
        "我剛翻了一下,第 7 頁的 YoY 5.2% 跟我上週 BI dashboard 拉的一致,沒問題,就按這個報。"),
    msg("f0000000-0000-4000-8000-000000000005", "f0000000-0000-4000-8000-000000000004", "2026-04-18T10:14:02+08:00", F_A,
        "王建宏", "normal",
        "收到感謝,我走過去拿線了。"),
]
F = wrap(F_CHAT, f_msgs)


bundle = {
    "generatedAt": "2026-04-20T00:00:00+08:00",
    "source": "self-made, Graph API ChatMessage v1.0 compliant",
    "scenarios": {"D": D, "E": E, "F": F},
}

(BASE / "custom_samples.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
print("Wrote", BASE / "custom_samples.json")
