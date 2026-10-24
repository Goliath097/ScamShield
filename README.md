![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

# 🛡️ ScamShield — a courtroom that tries suspicious messages

Paste any suspicious message. ScamShield investigates the actual links and
payment IDs inside it, argues both sides, and returns a verdict with concrete
next steps — in seconds, inside an ASI:One conversation.

Built for Fetch-A-Thon 3.0 — *ASI:One Agent Challenge: From Intent to Action*.

## The problem

Online fraud in India is enormous and fast: fake job offers, UPI "refund"
links, "digital arrest" calls, fake courier SMS. The victim has seconds to
decide, usually on a phone, often alone. Asking a chatbot gets you "this looks
suspicious" — an opinion with no evidence behind it and no instruction on what
to do next.

**Users:** students, parents, elderly relatives — anyone who forwards a message
asking "is this real?"

## What it actually does

Not a classifier and not a thin LLM wrapper. It runs a real adversarial
workflow over live evidence:

1. **Investigator agent** extracts every URL, domain, UPI ID, phone number and
   amount from the message, then checks each domain against **RDAP** (live
   registration data, no API key) and a lookalike-brand list. A domain
   registered 11 days ago that borrows the name "sbi" is hard evidence.
2. **Prosecution pass** argues the message is a scam, citing that evidence.
3. **Defence pass** argues it may be legitimate — real companies do send OTPs
   and delivery texts. This is what stops the system flagging everything.
4. **Judge** weighs both against the hard evidence and returns a verdict, a
   confidence score, concrete next steps (don't pay, call **1930**, report at
   **cybercrime.gov.in**) and a forwardable warning for the family group.

If RDAP is unreachable, the verdict still lands with lowered confidence and
says so — graceful degradation rather than failure.

## Architecture

```
ASI:One ──ACP──▶ Judge agent ──InvestigationRequest──▶ Investigator agent
                 (prosecution,                          (RDAP domain age,
                  defence,        ◀─InvestigationResult─  lookalike check,
                  verdict)                                URL/UPI/phone extraction)
```

Two agents, split by responsibility: the Investigator gathers facts and holds
no opinions and no LLM; the Judge does all reasoning and never touches the
network directly. New evidence sources (Safe Browsing, UPI reputation,
takedown feeds) plug into the Investigator without touching the verdict logic.

## Agents

| Name | Address | Role |
|---|---|---|
| `fetchathon-starter` (Judge) | `agent1qw7dkdsj6ss054z20el4dm4nzz6zsglxs38f4uxm0v960d0ltvfnj6g0vt9` | ACP front door, adversarial reasoning, verdict |
| `scamshield-investigator` | `agent1q2cjphtv25ecjtqz05zznrpsnsmrsc5zwe54zhwkw5htaeadumwyjv8jn0f` | Evidence gathering, RDAP, extraction |

### Messages

| Model | Fields |
|---|---|
| `InvestigationRequest` | `message_text: str` |
| `InvestigationResult` | `evidence: str`, `indicators: str`, `ok: bool` |

## Try it

> "URGENT: Your SBI account will be blocked today. Complete KYC at
> http://sbi-kyc-update.in or pay ₹499 to verify. Call 9876543210."

> "Congratulations! You are selected for a work-from-home job at Amazon.
> Pay ₹1,500 refundable registration to start."

> "Your Amazon order 402-9913 has shipped. Track at https://amazon.in/orders"
> *(should come back as likely genuine — the defence matters)*

## Run it

Python 3.10–3.13.

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows;  source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

cp .env.example .env                # fill in ASI1_API_KEY and AGENT_SEED

python investigator.py              # terminal 1 — prints INVESTIGATOR_ADDRESS
# paste that address into .env
python agent.py                     # terminal 2 — open the Inspector URL, Connect -> Mailbox
```

Then open the Judge agent on Agentverse and click **Chat with Agent**.

**Verify without any keys or network:**

```bash
python test_local.py                # forensics + agent messaging
python forensics.py "paste a suspicious message here"
```

## Data sources

| Source | Purpose | Key needed |
|---|---|---|
| [RDAP](https://rdap.org) | Live domain registration date | No |
| Lookalike brand list | Detects `sbi-kyc-update.in` vs `sbi.co.in` | No |
| ASI:One (`asi1`) | Prosecution, defence and verdict reasoning | Yes |

## Limitations

RDAP reports **registration data**, not maliciousness, and the system detects
**known patterns** — a novel, well-funded scam using an aged domain can still
pass. ScamShield lowers the cost of checking; it does not replace caution. It
is not legal advice.

## Stack

uAgents 0.25.5 · AgentChatProtocol 0.3.0 · Agentverse Mailbox · ASI:One (`asi1`) · RDAP

## Team

Team ID `fetchathon3.0-1233` — Adrian neil (lead), Nikhil Ravindra
