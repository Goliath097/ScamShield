"""
ASI:One Interactive Cards for ScamShield. Pure functions, no network.

Every card is a ChatMessage with a short TextContent (shown above the card, and
on its own if ASI:One ever rejects the card) plus a MetadataContent holding the
card payload. Spec: innovationlab.fetch.ai/resources/docs/interactive-cards

Button presses come back as a chat message carrying the button's `selection`,
either as a JSON string or as prose that contains its identifiers. Every
identifier is prefixed `ss_` / `ex_` so `parse_action` can find it either way.
"""

import json
import re
from urllib.parse import quote

from uagents_core.contrib.protocols.chat import MetadataContent

VERDICTS = {
    # verdict: (badge label, badge variant, headline)
    "SCAM": ("Scam", "warning", "Don't click. Don't pay."),
    "LIKELY SCAM": ("Likely scam", "warning", "Very likely a scam. Don't act on it."),
    "UNCLEAR": ("Unclear", "info", "We couldn't confirm this. Verify it with the sender first."),
    "LIKELY GENUINE": ("Looks genuine", "success", "This looks genuine."),
}
SCAM_VERDICTS = {"SCAM", "LIKELY SCAM"}

EXAMPLES = {
    "ex_kyc": (
        "Fake bank KYC alert",
        "URGENT: Your SBI account will be blocked today. Complete KYC at "
        "http://sbi-kyc-update.in or pay Rs 499 to verify. Call 9876543210.",
    ),
    "ex_job": (
        "Work-from-home job offer",
        "Congratulations! You are selected for a work-from-home job at Amazon. Earn "
        "daily 3000. Pay Rs 1,500 refundable registration fee to hr.amazonjobs@ybl",
    ),
    "ex_amazon": (
        "Amazon delivery update",
        "Your Amazon order 402-9913 has shipped and will arrive Tuesday. Track it at "
        "https://amazon.in/orders",
    ),
}

REPORT_TEXT = (
    "**How to report a scam**\n\n"
    "1. **Lost money?** Call **1930** right away. The first few hours matter most "
    "for freezing the payment.\n"
    "2. Report it online at **cybercrime.gov.in**.\n"
    "3. Call your bank to block your card or UPI if you shared any details.\n"
    "4. Report the SMS or call on **Chakshu** at sancharsaathi.gov.in.\n\n"
    "Don't reply to the sender, and don't delete the message yet. Police may need it."
)

GREETING_RE = re.compile(
    r"^\W*(hi+|hello|hey+|namaste|help|start|menu|what can you do|who are you)\b", re.I
)


def clip(text, max_words: int) -> str:
    words = str(text or "").split()
    return " ".join(words[:max_words]) + ("…" if len(words) > max_words else "")


_MD_RE = re.compile(r"\*\*|__|`|^#+\s*|^\s*(?:[-*•]|\d+[.)])\s+")
_RUPEE_RE = re.compile(r"\b(?:Rs\.?|INR)\s?(?=\d)", re.I)


def plain(text, max_words: int, end_stop: bool = False) -> str:
    """Model output -> clean card copy: no markdown, ₹ for amounts, sentence case."""
    s = _MD_RE.sub("", " ".join(str(text or "").split()))
    s = _RUPEE_RE.sub("₹", s).strip().strip('"\u201c\u201d').strip()
    s = clip(s, max_words)
    if not s:
        return ""
    s = s[0].upper() + s[1:]
    s = s.rstrip(".")
    return s + "." if end_stop and not s.endswith(("…", "?", "!")) else s


def as_list(value) -> list:
    if isinstance(value, str):
        return [value]
    return list(value) if isinstance(value, (list, tuple)) else []


def is_greeting(text: str) -> bool:
    return len(text) < 15 or (len(text.split()) <= 8 and bool(GREETING_RE.match(text)))


def _meta(kind: str, payload: dict) -> MetadataContent:
    return MetadataContent(
        metadata={
            "card_protocol_version": "1",
            "requires_card_interaction": "true",
            "card_kind": kind,
            "card_payload": json.dumps(payload),
            "preferred_drawer_width_px": "480",
        }
    )


def _text(value: str, style: str = "body") -> dict:
    return {"type": "text", "value": value, "style": style}


def _heading(value: str) -> dict:
    return {"type": "heading", "value": value, "level": 3}


def _button(label: str, action: str, primary: bool = False) -> dict:
    return {
        "type": "button",
        "label": label,
        "primary": primary,
        "action": {"selection": {"scamshield_action": action}},
    }


def welcome_card():
    """First contact and 'Check another message': a paste box plus one-tap examples."""
    payload = {
        "root": {
            "type": "section",
            "title": "Is this message a scam?",
            "subtitle": "Paste it below. I'll check its links and payment details, "
            "then tell you what to do.",
            "children": [
                {
                    "type": "input",
                    "name": "suspect_message",
                    "kind": "text",
                    "label": "Suspicious message",
                    "placeholder": "Paste the SMS, WhatsApp message, email or link",
                    "required": True,
                },
                _button("Check this message", "ss_check", primary=True),
                {"type": "divider"},
                _heading("Already lost money or shared details?"),
                _text("Get the emergency steps and ready-to-send complaint emails.", "muted"),
                _button("I've been scammed: help me now", "ss_emergency"),
                {"type": "divider"},
                _heading("Or try an example"),
                {
                    "type": "list",
                    "items": [
                        {
                            "children": [
                                _text(title, "emphasis"),
                                _text(clip(sample, 12), "muted"),
                            ],
                            "action": {
                                "selection": {"scamshield_action": "ss_example", "example": key}
                            },
                        }
                        for key, (title, sample) in EXAMPLES.items()
                    ],
                },
            ],
        }
    }
    narration = (
        "**ScamShield** checks suspicious messages. Paste one, or pick an example."
    )
    return narration, _meta("custom", payload)


def checking_text() -> str:
    return "Checking the links and payment details, then weighing both sides…"


def normalise(v: dict) -> dict:
    """Coerce the Judge's JSON into safe, length-capped fields."""
    verdict = re.sub(r"[_\s]+", " ", str(v.get("verdict", "UNCLEAR"))).upper().strip()
    if verdict not in VERDICTS:
        verdict = "UNCLEAR"
    digits = re.search(r"\d+", str(v.get("confidence", "")))
    confidence = max(0, min(100, int(digits.group()))) if digits else 50
    evidence = [plain(e, 16) for e in as_list(v.get("evidence"))[:3]]
    actions = [plain(a, 12) for a in as_list(v.get("actions"))[:3]]
    return {
        "verdict": verdict,
        "confidence": confidence,
        "summary": plain(v.get("summary"), 16),
        "evidence": [e for e in evidence if e],
        "actions": [a for a in actions if a],
        "forward": plain(v.get("forward"), 35, end_stop=True) if verdict in SCAM_VERDICTS else "",
    }


def verdict_card(v: dict, prosecution: str, defence: str, tools_ok: bool):
    v = normalise(v)
    label, variant, headline = VERDICTS[v["verdict"]]

    children = [
        {
            "type": "group",
            "direction": "row",
            "gap": 8,
            "children": [
                {"type": "badge", "label": label, "variant": variant},
                {"type": "badge", "label": "%d%% confidence" % v["confidence"], "variant": "info"},
            ],
        },
    ]
    if v["evidence"]:
        children += [
            {"type": "divider"},
            _heading("What we found"),
            {"type": "list", "items": [{"children": [_text(e)]} for e in v["evidence"]]},
        ]
    if v["actions"]:
        children += [
            _heading("Do this now"),
            {
                "type": "list",
                "items": [
                    {"children": [_text("%d. %s" % (i, a), "emphasis")]}
                    for i, a in enumerate(v["actions"], 1)
                ],
            },
        ]
    children += [
        {"type": "divider"},
        _heading("Both sides"),
        _text("Why it could be a scam: " + plain(prosecution, 28, end_stop=True)),
        _text("Why it could be genuine: " + plain(defence, 28, end_stop=True)),
    ]
    if v["forward"]:
        children += [_heading("Warn your family"), _text(v["forward"])]
    if v["verdict"] in SCAM_VERDICTS:
        children.append(_text("Lost money? Call 1930 or report at cybercrime.gov.in.", "muted"))
    elif v["verdict"] == "LIKELY GENUINE":
        children.append(_text("Even so, never share an OTP or PIN.", "muted"))
    if not tools_ok:
        children.append(_text("Some checks were unavailable, so confidence is lower.", "muted"))

    buttons = [_button("Check another message", "ss_new", primary=True)]
    if v["verdict"] in SCAM_VERDICTS:
        buttons.append(_button("I already paid or shared details", "ss_emergency"))
    if v["verdict"] != "LIKELY GENUINE":
        buttons.append(_button("How to report it", "ss_report"))
    buttons.append(_button("Show full evidence", "ss_evidence"))
    children += [
        {"type": "divider"},
        {"type": "group", "direction": "row", "gap": 8, "children": buttons},
    ]

    payload = {
        "root": {
            "type": "section",
            "title": headline,
            "subtitle": v["summary"],
            "children": children,
        }
    }

    narration = "**%s** · %d%% confidence" % (label, v["confidence"])
    if v["summary"]:
        narration += ". %s." % v["summary"]
    if v["verdict"] in SCAM_VERDICTS:
        narration += " Lost money? Call **1930**."
    return narration, _meta("custom", payload)


_LABELS = [
    (re.compile(r"^LOOKALIKE:\s*", re.I), "Lookalike: "),
    (re.compile(r"^NEWLY REGISTERED\s*[—-]\s*", re.I), "Newly registered: "),
    (re.compile(r"UNRECOGNISED handle", re.I), "unrecognised handle"),
]


# --------------------------------------------------------------------------
# Emergency: the user has already been scammed.
# --------------------------------------------------------------------------

CALL_1930 = "[Call 1930](tel:1930)"

INCIDENTS = {
    # key: (form label, short description used in the drafts)
    "inc_paid": ("I sent money (UPI, card or bank transfer)", "money was taken by fraud"),
    "inc_otp": ("I shared an OTP, PIN or password", "I shared my OTP/PIN with a fraudster"),
    "inc_link": ("I clicked a link or installed an app", "I opened a fraudulent link/app"),
    "inc_threat": ("Someone is threatening me (fake police, \"digital arrest\")", "I am being threatened by impersonators"),
    "inc_hacked": ("My WhatsApp, email or social account was hacked", "my account was taken over"),
}

STEPS = {
    "inc_paid": [
        "Call **1930** now. Give them the amount, the transaction ID (UTR) and the time. Acting in the first hour gives the best chance of freezing the money.",
        "Call your bank's official helpline. Ask them to block the card or UPI and raise a fraud dispute.",
        "File a complaint at **cybercrime.gov.in** within 24 hours, under *Financial fraud*.",
        "Send the bank the email below. Under RBI rules, reporting within 3 working days limits your liability.",
    ],
    "inc_otp": [
        "Call your bank's official helpline **now** to block your card, UPI and net banking.",
        "Change your UPI PIN and passwords from a phone the scammer has not touched.",
        "Check your statement. If any money has gone, call **1930** immediately.",
        "Send the bank the email below so there is a written record.",
    ],
    "inc_link": [
        "Turn on flight mode, then uninstall any app you installed (especially screen-sharing apps like AnyDesk).",
        "From another device, change your banking, email and UPI passwords.",
        "Call your bank's helpline and ask them to watch for or block unusual transactions.",
        "If any money has gone, call **1930** and file at **cybercrime.gov.in**.",
    ],
    "inc_threat": [
        "Hang up and don't pay. Police, CBI and courts never arrest anyone over a video call or ask for money to \"clear your name\".",
        "Don't share screenshots of your ID, bank details or OTPs with them.",
        "Report the number on **Chakshu** at sancharsaathi.gov.in, and file at **cybercrime.gov.in**.",
        "If you have already paid, call **1930** now.",
    ],
    "inc_hacked": [
        "Use the app's official \"forgot password\" or account recovery, then turn on two-step verification.",
        "Warn your contacts not to send money or codes to messages from your account (text below).",
        "Log out of all other devices from the app's security settings.",
        "If the hacker asked anyone for money, report it at **cybercrime.gov.in** or call **1930**.",
    ],
}


def emergency_card():
    """Critical steps first (no form needed), then an optional form for tailored drafts."""
    payload = {
        "root": {
            "type": "section",
            "title": "Act now. Every minute counts.",
            "subtitle": "If money has left your account, calling 1930 in the first hour "
            "gives the best chance of freezing it.",
            "children": [
                _text("1. Call 1930, the National Cyber Crime Helpline (24×7).", "emphasis"),
                _text("2. Call your bank's official helpline to block your card and UPI.", "emphasis"),
                _text("3. File a complaint at cybercrime.gov.in.", "emphasis"),
                {"type": "divider"},
                _heading("Get your plan and ready-to-send emails"),
                {
                    "type": "input",
                    "name": "incident",
                    "kind": "select",
                    "label": "What happened?",
                    "required": True,
                    "options": [{"value": k, "label": label} for k, (label, _) in INCIDENTS.items()],
                },
                {"type": "input", "name": "victim_name", "kind": "text", "label": "Your name", "placeholder": "As on your bank account"},
                {"type": "input", "name": "bank", "kind": "text", "label": "Bank or payment app", "placeholder": "e.g. SBI, HDFC, PhonePe"},
                {"type": "input", "name": "amount", "kind": "text", "label": "Amount lost (₹), if any", "placeholder": "e.g. 4,999"},
                {"type": "input", "name": "when", "kind": "text", "label": "When did it happen?", "placeholder": "e.g. today, 2:15 pm"},
                {"type": "input", "name": "txn_ref", "kind": "text", "label": "Transaction ID or UTR, if any", "placeholder": "From your bank SMS or UPI app"},
                _text("Never type your card number, PIN, OTP or password here.", "muted"),
                _button("Get my plan and email drafts", "ss_plan", primary=True),
            ],
        }
    }
    narration = (
        "**Already scammed? %s now**, the National Cyber Crime Helpline (24×7). "
        "Then use the card below for your plan and complaint emails." % CALL_1930
    )
    return narration, _meta("custom", payload)


def _field(data: dict, key: str, placeholder: str) -> str:
    value = " ".join(str(data.get(key) or "").split())[:80]
    return value or placeholder


def plan_text(data: dict, scam_message: str = "") -> str:
    """Tailored steps plus drafts. Templates, not the LLM: instant and the wording is fixed."""
    incident = data.get("incident") if data.get("incident") in INCIDENTS else "inc_paid"
    label, short = INCIDENTS[incident]
    name = _field(data, "victim_name", "[Your name]")
    bank = _field(data, "bank", "[Bank name]")
    amount = _field(data, "amount", "[amount]").lstrip("₹").strip()
    when = _field(data, "when", "[date and time]")
    txn = _field(data, "txn_ref", "[transaction ID / UTR]")
    scam = " ".join(scam_message.split())[:400]

    out = ["**Your emergency plan**", "_%s_" % label, ""]
    out += ["%d. %s" % (i, step) for i, step in enumerate(STEPS[incident], 1)]
    out += ["", "%s · [cybercrime.gov.in](https://cybercrime.gov.in)" % CALL_1930]

    if incident in ("inc_paid", "inc_otp", "inc_link"):
        subject = "Urgent: fraud on my account, please block and investigate"
        body = (
            "Dear %s Customer Care,\n\n"
            "I am reporting an unauthorised/fraudulent transaction on my account. %s.\n\n"
            "Account holder: %s\n"
            "Account/card (last 4 digits): [XXXX]\n"
            "Amount: Rs %s\n"
            "Date and time: %s\n"
            "Transaction ID / UTR: %s\n\n"
            "Please immediately:\n"
            "1. Block my card, UPI and net banking to prevent further loss.\n"
            "2. Raise a fraud dispute and attempt to recall or freeze the amount.\n"
            "3. Mark the beneficiary account as fraudulent.\n\n"
            "I am reporting this within 3 working days, as per RBI guidelines on customer "
            "liability for unauthorised electronic transactions. I have also reported it "
            "to the National Cyber Crime Helpline (1930).\n\n"
            "Please confirm receipt and share a complaint reference number.\n\n"
            "Regards,\n%s"
            % (bank, short[0].upper() + short[1:], name, amount, when, txn, name)
        )
        mailto = "mailto:?subject=%s&body=%s" % (quote(subject), quote(body))
        out += [
            "",
            "**Email to your bank**",
            "Send it to your bank's official fraud or customer-care address. "
            "[Open it in your email app](%s), or copy it:" % mailto,
            "",
            "> **Subject:** %s" % subject,
            ">",
        ] + ["> " + line + "  " if line else ">" for line in body.splitlines()]

    money_case = incident in ("inc_paid", "inc_otp", "inc_link") or data.get("amount")
    request = {
        "inc_hacked": "Please help me recover my account and investigate its misuse.",
        "inc_threat": "Please take action against the people impersonating officials.",
    }.get(incident, "Please freeze the beneficiary account and investigate the fraud.")
    complaint = ["Incident: %s." % (short[0].upper() + short[1:]), "Date and time: %s" % when]
    if money_case:
        complaint += [
            "Amount lost: Rs %s" % amount,
            "Transaction ID / UTR: %s" % txn,
            "Bank or payment app: %s" % bank,
        ]
    if scam:
        complaint.append('Fraudulent message received: "%s"' % scam.rstrip("."))
    complaint.append("Request: %s" % request)
    out += [
        "",
        "**Complaint text for cybercrime.gov.in**",
        "Paste this into the incident description when you file:",
        "",
    ] + ["> " + line + "  " for line in complaint]

    if incident == "inc_hacked":
        out += [
            "",
            "**Message to send your contacts**",
            "> My account was hacked. If you get a message from me asking for money, "
            "an OTP or a code, ignore it and don't pay. I'm recovering the account. %s" % name,
        ]

    out += ["", "_Keep screenshots of the messages, call logs and payment receipts. Don't delete anything yet._"]
    return "\n".join(out)


EMERGENCY_RE = re.compile(
    r"\b(i|i've|ive|i have|i was|i got|my|mera|mujhe)\b.{0,40}\b("
    r"scammed|hacked|cheated|duped|defrauded|lost money|lost rs|lost ₹|"
    r"(paid|sent|transferred).{0,20}(scam|fraud|wrong)|"
    r"shared (my )?(otp|pin|password|cvv)|fraud happened)",
    re.I,
)


def is_emergency(text: str) -> bool:
    """First-person 'it already happened' messages, not pasted scam texts."""
    return len(text) < 300 and "http" not in text.lower() and bool(EMERGENCY_RE.search(text))


def evidence_text(raw_evidence: str) -> str:
    """The Investigator's raw findings as clean nested markdown (no accidental code blocks)."""
    out = []
    for line in raw_evidence.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "EVIDENCE GATHERED":
            continue
        for pattern, label in _LABELS:
            stripped = pattern.sub(label, stripped)
        stripped = _RUPEE_RE.sub("₹", stripped)
        indent = len(line) - len(line.lstrip())
        if stripped.startswith("•"):
            out.append("- " + stripped.lstrip("• "))
        elif indent >= 4:
            out.append("  - " + stripped)
        elif stripped.endswith(":"):
            out.append("\n**%s**" % stripped.rstrip(":"))
        elif ": " in stripped:
            label, value = stripped.split(": ", 1)
            out.append("\n**%s:** %s" % (label, value))
        else:
            out.append("\n" + stripped)
    if not out:
        return "Nothing has been checked yet. Paste a suspicious message and I'll investigate it."
    return "**Full evidence from the Investigator agent**\n" + "\n".join(out)


_JSON_RE = re.compile(r"\{.*\}", re.S)
_PASTED_RE = re.compile(r"suspect_message[\"']?\s*[:=]\s*[\"\u201c](.+?)[\"\u201d]", re.S)
_ID_RE = re.compile(r"\b(ss_[a-z]+|ex_[a-z]+|inc_[a-z]+)\b")


def parse_action(text: str):
    """Return (action, data) for a card interaction, or (None, {}) for a normal message."""
    m = _JSON_RE.search(text)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict) and str(data.get("scamshield_action", "")).startswith("ss_"):
                return data["scamshield_action"], data
        except ValueError:
            pass
    ids = _ID_RE.findall(text)
    actions = [i for i in ids if i.startswith("ss_")]
    if actions:
        data = {}
        examples = [i for i in ids if i in EXAMPLES]
        if examples:
            data["example"] = examples[0]
        incidents = [i for i in ids if i in INCIDENTS]
        if incidents:
            data["incident"] = incidents[0]
        pasted = _PASTED_RE.search(text)
        if pasted:
            data["suspect_message"] = pasted.group(1)
        return actions[0], data
    return None, {}
