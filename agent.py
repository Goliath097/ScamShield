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

import os

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
    "ScamShield here. Paste any suspicious message — a job offer, a UPI refund "
    "link, a courier SMS, a 'KYC expiring' alert — and I'll investigate the "
    "links and payment IDs in it, argue both sides, and give you a verdict with "
    "what to do next."
)


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
        prosecution = ask_asi(
            "You are the PROSECUTION. Argue this message IS a scam in max 50 words. "
            "Cite only the strongest 2 pieces of evidence given. No preamble, no "
            "restating the message. If evidence is weak, say so in one line.",
            "MESSAGE:\n%s\n\nEVIDENCE:\n%s\n\nINDICATORS: %s"
            % (suspect, msg.evidence, msg.indicators),
            max_tokens=300,
        )

        defence = ask_asi(
            "You are the DEFENCE. Argue this message may be LEGITIMATE in max 50 words. "
            "Real companies do send OTPs, delivery updates and KYC reminders. State what "
            "the evidence does NOT prove. If indefensible, say so in one line and stop.",
            "MESSAGE:\n%s\n\nEVIDENCE:\n%s\n\nINDICATORS: %s"
            % (suspect, msg.evidence, msg.indicators),
            max_tokens=300,
        )

        verdict = ask_asi(
            "You are the JUDGE. Output EXACTLY this, nothing else:\n\n"
            "VERDICT: <SCAM | LIKELY SCAM | UNCLEAR | LIKELY GENUINE>\n"
            "CONFIDENCE: <0-100>%\n"
            "WHY: <2 bullet points, max 15 words each>\n"
            "DO THIS NOW:\n<3 bullets, max 10 words each>\n"
            "FORWARD THIS: <one sentence, only if SCAM or LIKELY SCAM>\n\n"
            "Hard evidence outweighs tone. If evidence was unavailable, lower confidence. "
            "For scam verdicts always include: don't pay or share OTP; call 1930.",
            "MESSAGE:\n%s\n\nEVIDENCE:\n%s\n\nPROSECUTION:\n%s\n\nDEFENCE:\n%s"
            % (suspect, msg.evidence, prosecution, defence),
            max_tokens=400,
        )
    except Exception as err:
        ctx.logger.exception("ASI:One failed: %s", err)
        await reply(
            ctx,
            requester,
            "I gathered the evidence but my reasoning service failed.\n\n%s\n\n"
            "Treat any request for money or OTP as unsafe until verified. "
            "Cyber helpline: 1930." % msg.evidence,
        )
        return

    note = "" if msg.ok else "\n\n_Note: some evidence tools were unavailable; verdict is based on what could be checked._"

    await reply(
        ctx,
        requester,
        "🛡️ **SCAMSHIELD VERDICT**\n\n"
        "%s\n\n"
        "---\n**EVIDENCE**\n```\n%s\n```\n"
        "---\n**PROSECUTION**\n%s\n\n"
        "**DEFENCE**\n%s%s"
        % (verdict, msg.evidence, prosecution, defence, note),
    )


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    print("\nJUDGE ADDRESS = %s\n" % agent.address)
    agent.run()
