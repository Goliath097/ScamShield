"""
SCAMSHIELD — JUDGE AGENT (the one ASI:One talks to).

Keeps the original seed, so the Agentverse address and registration survive.

For each suspicious message:
  1. acknowledge (ACP)
  2. send the text to the Investigator agent  <- the multi-agent hop
  3. Investigator returns real evidence (RDAP domain age, lookalikes, UPI, etc.)
  4. PROSECUTION pass: argue it IS a scam, citing the evidence
  5. DEFENCE pass: argue it is legitimate
  6. VERDICT pass: weigh both, give confidence + concrete next steps
  7. reply over ACP

Terminal 2:   python agent.py
"""

import asyncio
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from openai import OpenAI
from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)

from models import InvestigationRequest, InvestigationResult

load_dotenv()

asi1_api_key = os.getenv("ASI1_API_KEY")
if not asi1_api_key or asi1_api_key.startswith("your-"):
    raise RuntimeError(
        "ASI1_API_KEY is not set. Create a key at https://asi1.ai/dashboard/api-keys "
        "and paste it into .env"
    )

INVESTIGATOR_ADDRESS = os.getenv("INVESTIGATOR_ADDRESS", "")
if not INVESTIGATOR_ADDRESS.startswith("agent"):
    raise RuntimeError(
        "INVESTIGATOR_ADDRESS is not set. Run `python investigator.py` first and "
        "paste the agent1q... address it prints into .env"
    )

client = OpenAI(base_url="https://api.asi1.ai/v1", api_key=asi1_api_key)

# Same name and seed as before -> same address -> registration is preserved.
agent = Agent(
    name="ScamShield",
    seed=os.environ["AGENT_SEED"],
    port=8001,
    mailbox=True,
    publish_agent_details=True,
)

protocol = Protocol(spec=chat_protocol_spec)

HELP_TEXT = (
    "🛡️ **ScamShield**\n"
    "Paste a suspicious SMS, WhatsApp message, email or link. "
    "I'll check it and tell you if it's a scam, and what to do."
)

BADGES = {"SCAM": "🔴", "LIKELY SCAM": "🟠", "UNCLEAR": "🟡", "LIKELY GENUINE": "🟢"}
SCAM_VERDICTS = {"SCAM", "LIKELY SCAM"}
MENTION_RE = re.compile(r"^(?:@\S+\s*)+")  # ASI:One prefixes "@agent1q..." to messages


def clip(text, max_words: int) -> str:
    words = str(text or "").split()
    return " ".join(words[:max_words]) + ("…" if len(words) > max_words else "")


def ask_asi(system: str, user: str, max_tokens: int = 900) -> str:
    r = client.chat.completions.create(
        model="asi1",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
    )
    return str(r.choices[0].message.content or "").strip()


def assess(suspect: str, evidence: str, indicators: str, tools_ok: bool) -> str:
    """Prosecution and defence in parallel, then a structured verdict rendered as a short card."""
    case = "MESSAGE:\n%s\n\nEVIDENCE:\n%s\n\nINDICATORS: %s" % (suspect, evidence, indicators)
    with ThreadPoolExecutor(max_workers=2) as pool:
        prosecution = pool.submit(
            ask_asi,
            "You are the PROSECUTION. In ONE sentence of max 20 words, argue this message "
            "IS a scam using the single strongest piece of evidence. No preamble. If the "
            "evidence is weak, say so.",
            case,
            120,
        )
        defence = pool.submit(
            ask_asi,
            "You are the DEFENCE. In ONE sentence of max 20 words, argue this message may be "
            "LEGITIMATE, or say plainly that it is indefensible. No preamble.",
            case,
            120,
        )
        prosecution, defence = prosecution.result(), defence.result()

    raw = ask_asi(
        "You are the JUDGE. Weigh prosecution vs defence against the hard evidence. "
        "Return ONLY this JSON object, no other text:\n"
        '{"verdict": "SCAM" | "LIKELY SCAM" | "UNCLEAR" | "LIKELY GENUINE", '
        '"confidence": <0-100>, '
        '"summary": "<what this message is, max 10 words>", '
        '"evidence": ["<up to 3 facts taken only from EVIDENCE/MESSAGE, max 10 words each>"], '
        '"actions": ["<exactly 3 imperative steps for the user, max 8 words each>"], '
        '"forward": "<WhatsApp-ready family warning, max 25 words; empty unless SCAM or LIKELY SCAM>"}\n'
        "Rules: hard evidence (lookalike or newly registered domains, payment demands) "
        "outweighs tone. If evidence tools were unavailable, lower confidence. Plain "
        "words a parent understands; no jargon.",
        "%s\n\nPROSECUTION: %s\nDEFENCE: %s" % (case, prosecution, defence),
        400,
    )
    try:
        v = json.loads(raw[raw.index("{") : raw.rindex("}") + 1])
    except ValueError:
        v = {"summary": clip(raw, 40)}
    return render(v, prosecution, defence, tools_ok, evidence)


def render(v: dict, prosecution: str, defence: str, tools_ok: bool, raw_evidence: str = "") -> str:
    verdict = str(v.get("verdict", "UNCLEAR")).upper().strip()
    if verdict not in BADGES:
        verdict = "UNCLEAR"
    try:
        confidence = max(0, min(100, int(v.get("confidence", 50))))
    except (TypeError, ValueError):
        confidence = 50

    lines = ["%s **%s** · %d%% confident" % (BADGES[verdict], verdict, confidence)]
    if v.get("summary"):
        lines.append(clip(v["summary"], 14))

    evidence = [clip(e, 12) for e in (v.get("evidence") or [])[:3] if e]
    if evidence:
        lines += ["", "**Evidence**"] + ["• %s" % e for e in evidence]

        actions = [clip(a, 10) for a in (v.get("actions") or [])[:3] if a]
    if actions:
        lines += ["", "**Do now**"] + ["%d. %s" % (i, a) for i, a in enumerate(actions, 1)]

    facts = [
        l.strip()
        for l in raw_evidence.splitlines()
        if any(k in l for k in ("LOOKALIKE", "Registered:", "NEWLY REGISTERED", "UNRECOGNISED"))
    ]
    if facts:
        lines += ["", "**Verified checks**"] + ["`%s`" % f for f in facts[:4]]

    lines += [
        "",
        "⚖️ _Prosecution:_ %s" % clip(prosecution, 22),
        "⚖️ _Defence:_ %s" % clip(defence, 22),
    ]
    if verdict in SCAM_VERDICTS:
        if v.get("forward"):
            lines += ["", "📤 **Forward to family**", "> %s" % clip(v["forward"], 30)]
        lines += ["", "📞 Lost money? Call **1930** · cybercrime.gov.in"]
    elif verdict == "LIKELY GENUINE":
        lines += ["", "🔒 Even so, never share an OTP or PIN."]

    if not tools_ok:
        lines += ["", "⚠️ _Some checks were unavailable, so confidence is lower._"]
    return "\n".join(lines)


async def reply(ctx: Context, to: str, body: str):
    await ctx.send(
        to,
        ChatMessage(
            content=[
                TextContent(type="text", text=body),
                EndSessionContent(type="end-session"),
            ]
        ),
    )


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    # ACP: acknowledge everything.
    await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))

    text = "".join(i.text for i in msg.content if isinstance(i, TextContent)).strip()
    text = MENTION_RE.sub("", text).strip()
    ctx.logger.info("message to check (%d chars)" % len(text))

    if len(text) < 15:
        await reply(ctx, sender, HELP_TEXT)
        return

    # Hosted/mailbox agents may handle messages independently — keep state in storage.
    ctx.storage.set("requester", sender)
    ctx.storage.set("suspect_text", text)

    # Hand off to the Investigator. The verdict is written when it replies.
    await ctx.send(INVESTIGATOR_ADDRESS, InvestigationRequest(message_text=text))


@agent.on_message(InvestigationResult)
async def on_evidence(ctx: Context, sender: str, msg: InvestigationResult):
    requester = ctx.storage.get("requester")
    suspect = ctx.storage.get("suspect_text") or ""
    if not requester:
        return

    ctx.logger.info("evidence in — running prosecution and defence")

    try:
        body = await asyncio.to_thread(assess, suspect, msg.evidence, msg.indicators, msg.ok)
    except Exception as err:
        ctx.logger.exception("ASI:One failed: %s", err)
        body = (
            "🟡 **Couldn't finish the check**\n"
            "Until you can verify it: don't click links, don't pay, don't share an OTP.\n\n"
            "📞 Lost money? Call **1930** · cybercrime.gov.in"
        )

    await reply(ctx, requester, body)


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    import socket

    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", 8001)) == 0:
            raise SystemExit(
                "Port 8001 is already in use: the agent is probably already running in "
                "another terminal. Stop it there (Ctrl+C) or run: lsof -iTCP:8001 -sTCP:LISTEN"
            )

    print("\nJUDGE ADDRESS = %s\n" % agent.address)
    agent.run()
