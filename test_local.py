"""
Offline check — no ASI:One key, no Agentverse, no network.
Proves the Judge and Investigator can exchange messages, and that the
forensics layer flags a known-bad message.

    python test_local.py     ->  expect PASS twice
"""

import os

from uagents import Agent, Bureau, Context

from forensics import extract, lookalike_check
from models import InvestigationRequest, InvestigationResult

SAMPLE = (
    "URGENT: Your SBI account will be blocked today. Complete KYC at "
    "http://sbi-kyc-update.in or pay Rs 499 to scamguy@okaxis. Call 9876543210."
)

# --- 1. forensics, no network -------------------------------------------------
found = extract(SAMPLE)
assert "sbi-kyc-update.in" in found["domains"], found["domains"]
assert "scamguy@okaxis" in found["upi_ids"], found["upi_ids"]
assert "9876543210" in found["phones"], found["phones"]
assert lookalike_check("sbi-kyc-update.in") is not None
assert lookalike_check("sbi.co.in") is None
print("PASS 1/2 — forensics flags the fake SBI domain and clears the real one")

# --- 2. agent-to-agent messaging ---------------------------------------------
judge = Agent(name="judge-test", seed="scamshield-judge-test-only", port=8010)
investigator = Agent(name="inv-test", seed="scamshield-inv-test-only", port=8011)


@investigator.on_message(InvestigationRequest)
async def inv_handle(ctx: Context, sender: str, msg: InvestigationRequest):
    await ctx.send(
        sender,
        InvestigationResult(evidence="stub evidence", indicators="stub", ok=True),
    )


@judge.on_event("startup")
async def judge_send(ctx: Context):
    await ctx.send(investigator.address, InvestigationRequest(message_text=SAMPLE))


@judge.on_message(InvestigationResult)
async def judge_recv(ctx: Context, sender: str, msg: InvestigationResult):
    ctx.logger.info("PASS 2/2 — agents exchanged messages: %s" % msg.evidence)
    os._exit(0)


if __name__ == "__main__":
    bureau = Bureau(port=8012)
    bureau.add(investigator)
    bureau.add(judge)
    bureau.run()
