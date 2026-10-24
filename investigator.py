"""
INVESTIGATOR AGENT — gathers evidence. No LLM, no opinions.

Extracts URLs, domains, UPI IDs and phone numbers from a suspicious message,
then checks each domain against RDAP (live registration date) and a lookalike
brand list.

Terminal 1:   python investigator.py
Copy the agent1q... address it prints into .env as INVESTIGATOR_ADDRESS.
"""

import os

from dotenv import load_dotenv
from uagents import Agent, Context

from forensics import investigate
from models import InvestigationRequest, InvestigationResult

load_dotenv()

agent = Agent(
    name="scamshield-investigator",
    seed=os.getenv("INVESTIGATOR_SEED", "scamshield-investigator-seed-change-me"),
    port=8002,
    endpoint=["http://127.0.0.1:8002/submit"],
)


@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info("=" * 72)
    ctx.logger.info("COPY INTO .env  ->  INVESTIGATOR_ADDRESS=%s" % agent.address)
    ctx.logger.info("=" * 72)


@agent.on_message(InvestigationRequest)
async def handle(ctx: Context, sender: str, msg: InvestigationRequest):
    ctx.logger.info("investigating message (%d chars)" % len(msg.message_text))
    try:
        evidence, indicators = investigate(msg.message_text)
        ctx.logger.info("evidence gathered: %s" % indicators[:160])
        await ctx.send(
            sender,
            InvestigationResult(evidence=evidence, indicators=indicators, ok=True),
        )
    except Exception as err:
        ctx.logger.exception("investigation failed: %s", err)
        # Degrade gracefully — the Judge can still reason from the text alone.
        await ctx.send(
            sender,
            InvestigationResult(
                evidence="Evidence tools unavailable (%s). Verdict based on message content only."
                % type(err).__name__,
                indicators="tool failure: %s" % err,
                ok=False,
            ),
        )


if __name__ == "__main__":
    print("\nINVESTIGATOR_ADDRESS=%s\n" % agent.address)
    agent.run()
