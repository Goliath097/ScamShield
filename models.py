"""Shared message types between the Judge and the Investigator.

Both agents import this file. uAgents builds a schema digest from the field
names and types — if the two sides disagree by even one character, messages are
silently dropped with no error. Never edit this on one side only.
"""

from uagents import Model


class InvestigationRequest(Model):
    message_text: str


class InvestigationResult(Model):
    evidence: str       # human-readable evidence block, shown in the verdict
    indicators: str     # compact machine-ish summary for the reasoning passes
    ok: bool = True
