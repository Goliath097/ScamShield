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
    name="fetchathon-starter",
    seed=os.environ["AGENT_SEED"],
    port=8001,
    mailbox=True,
    publish_agent_details=True,
    readme_path="README.md",
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
            "You are the PROSECUTION in a fraud assessment. Argue that this message IS a "
            "scam. Cite the specific evidence given. Reference known Indian scam patterns "
            "(fake KYC, digital arrest, courier fee, fake job offer, UPI refund) only where "
            "the pattern actually matches. Be concrete, max 120 words. If the evidence is "
            "genuinely weak, say your case is weak — do not invent evidence.",
            "MESSAGE:\n%s\n\nEVIDENCE:\n%s\n\nINDICATORS: %s"
            % (suspect, msg.evidence, msg.indicators),
            max_tokens=400,
        )

        defence = ask_asi(
            "You are the DEFENCE in a fraud assessment. Argue that this message may be "
            "LEGITIMATE. Real companies do send OTPs, delivery updates and KYC reminders. "
            "Point out what is normal and what the evidence does NOT prove. Be honest — if "
            "the message is indefensible, say so plainly. Max 120 words.",
            "MESSAGE:\n%s\n\nEVIDENCE:\n%s\n\nINDICATORS: %s"
            % (suspect, msg.evidence, msg.indicators),
            max_tokens=400,
        )

        verdict = ask_asi(
            "You are the JUDGE. Weigh the prosecution and defence against the hard evidence "
            "and deliver a verdict. Format EXACTLY:\n\n"
            "VERDICT: <SCAM | LIKELY SCAM | UNCLEAR | LIKELY GENUINE>\n"
            "CONFIDENCE: <0-100>%\n"
            "WHY: <2-3 short lines citing the strongest evidence>\n"
            "DO THIS NOW:\n- <3-4 concrete steps>\n"
            "FORWARD THIS: <one short WhatsApp-ready warning for family, only if SCAM or LIKELY SCAM>\n\n"
            "Hard evidence (domain age, lookalike domains) outweighs tone. If evidence was "
            "unavailable, lower your confidence and say so. For any scam verdict always "
            "include: do not pay or share OTP; call cybercrime helpline 1930; report at "
            "cybercrime.gov.in.",
            "MESSAGE:\n%s\n\nEVIDENCE:\n%s\n\nPROSECUTION:\n%s\n\nDEFENCE:\n%s"
            % (suspect, msg.evidence, prosecution, defence),
            max_tokens=700,
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
