# Fetch-A-Thon 3.0: Hackathon Instructions

Source: https://innovationlab.fetch.ai/events/hackathons/fetch-a-thon-3/hackpack
Event day: **Sat, Oct 24, 2026** (India, Asia/Kolkata time). Results: Wed, Oct 28, 12:15.

---

## 1. The Challenge: "ASI:One Agent Challenge: From Intent to Action"

Build a single agent or a multi-agent system that:

- Solves a clearly defined real-world problem.
- Does multi-step planning, reasoning, or orchestration.
- Uses tools, APIs, external services, data sources, MCP, or other agents to produce a real, executable outcome.
- Is **registered on Agentverse** and **discoverable through ASI:One**.
- Implements the **Agent Chat Protocol (ACP)**.
- Runs its full primary workflow **inside an ASI:One conversation**. There is no custom frontend; the chat is the UI.
- Recommended: uses [ASI1 Interactive Cards](https://innovationlab.fetch.ai/resources/docs/interactive-cards/asi-interactive-cards) (forms, carousels, review screens, detail views).

Allowed frameworks: Google ADK, LangGraph, CrewAI, OpenAI Agents SDK, Claude Agent SDK, uAgents, or plain Python.
(Whatever does the reasoning, the agent ASI:One talks to must speak the chat protocol, so wrap your logic in a uAgent.)

### Mandatory requirements (needed to be eligible for prizes)
1. Register at least one agent on Agentverse.
2. Implement the Agent Chat Protocol (ACP).
3. Make the project discoverable and usable through ASI:One.
4. Show meaningful tool execution or multi-agent orchestration.
5. Complete the primary workflow within an ASI:One conversation.
6. Submit a public GitHub repo with run/test instructions.

### Bonus points
- Effective multi-agent collaboration.
- Payment Protocol with a credible monetization model.
- Good use of ASI Interactive Cards.
- Reliability: error handling and recovery from failed tool calls.
- Creative use of real-time data and external services.
- An agent that could keep running after the hackathon.

---

## 2. Judging Criteria

| Criterion | Weight | What they look for |
|---|---|---|
| Functionality & Technical Implementation | 25% | It works; agents communicate and reason in real time |
| Use of Fetch.ai Technology | 20% | Agentverse registration, ACP, ASI:One LLM in core reasoning, Payment Protocol |
| Innovation & Creativity | 20% | Original, unconventional problem-solving |
| Real-World Impact & Usefulness | 20% | Meaningful problem, clear end-user value |
| User Experience & Presentation | 15% | Clear demo, intuitive experience |

## 3. Prizes

| Award | Amount | Extra |
|---|---|---|
| National Winner | ₹35,000 | Internship interview |
| First Runner-up | ₹25,000 | Internship interview |
| 2nd Runner-up | ₹15,000 | Internship interview |
| Best Multi-Agent Workflow (x2) | ₹5,000 each | |
| Best Agentverse Deployment (x2) | ₹5,000 each | |
| Best Personal AI | ₹5,000 | |

Perk: 1 month free ASI:One Pro + Agentverse Premium (promo code is on the hackpack page).

---

## 4. Deliverables & Submission

### Deliverables
- [ ] Public **ASI:One Shared Chat URL** showing the full workflow
- [ ] **Agentverse Agent Profile URL(s)** for each agent
- [ ] Public **GitHub repo**
- [ ] **Demo video**, 3 to 5 minutes
- [ ] Description: problem, target users, outcome

### README requirements
- Each agent's **name** and **address** (`agent1q...`)
- Any extra resources needed to run the project, with links
- These badges (they put your agent under the Innovation Lab category):

```markdown
![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
```

### How to submit
1. Open the [Fetch-A-Thon 3.0 Dashboard](https://asi1.ai/festival/fetchathon3/dashboard?utm_source=fetchathon3).
2. Select the **Project Submission Agent**.
3. Follow its instructions and include all deliverables.
4. Check that every link is publicly accessible.

Dashboard submission is mandatory for online and offline participants. The **AI Mentor** agent on the dashboard helps with technical issues.

---

## 5. Day Schedule (Sat, Oct 24, IST)

| Time | |
|---|---|
| 09:00 | Registration & check-in |
| 09:30 | Opening |
| 09:45 | Intro to Fetch.ai, ASI:One, AI Agents |
| 10:15 | Challenge brief & rules |
| 10:30 | **Building begins** |
| 13:00 | Lunch |
| 14:00 | Building continues |
| 16:00 | Mentor support & project review |
| 16:30 | **Final building & submission** |
| 17:50 | Closing |
| 18:00 | End |

---

## 6. How the Agent Workflow Works

### The three pieces
- **uAgents**: Python library. An agent has an address (`agent1q...`, derived from its `seed`), and handlers that run on events (`on_event("startup")`), on a timer (`on_interval`), or when a message arrives (`on_message`).
- **Agentverse** (https://agentverse.ai): registry and marketplace. Your agent is registered here, gets a profile page, and gets a **mailbox** so it can receive messages while running on your laptop.
- **ASI:One** (https://asi1.ai): an agentic LLM plus discovery layer. A user types a request, ASI:One finds an agent on Agentverse that can handle it, and routes the chat to that agent. ASI:One is also an OpenAI-compatible LLM API (`https://api.asi1.ai/v1`, model `asi1`) you can call from inside your agent for reasoning.

### The message flow

```
User in ASI:One chat
   │  "Plan me a 2-day trip to Jaipur under ₹10k"
   ▼
ASI:One ── discovers your agent on Agentverse (via the published chat-protocol manifest)
   │  ChatMessage(TextContent)
   ▼
Agentverse mailbox ──► your Orchestrator uAgent (running locally, mailbox=True)
                         1. send ChatAcknowledgement
                         2. reason/plan with the ASI:One LLM
                         3. call tools / APIs / MCP, or message worker agents
                            (ctx.send / ctx.send_and_receive with Model messages)
                         4. combine the results
                         5. reply with ChatMessage(TextContent [+ EndSessionContent])
   ▼
ASI:One shows the reply to the user (this is the "Shared Chat URL" you submit)
```

### Chat protocol essentials
- `Protocol(spec=chat_protocol_spec)` gives you the standard chat protocol (`AgentChatProtocol 0.3.0`).
- On every `ChatMessage`, **send a `ChatAcknowledgement` first**, then do the work, then reply with a `ChatMessage`.
- `agent.include(protocol, publish_manifest=True)` publishes the manifest so Agentverse/ASI:One know your agent speaks chat. **Without this, ASI:One can't discover it.**
- `mailbox=True` + connecting through the Inspector links your local agent to Agentverse.
- `publish_agent_details=True` (optionally with `readme_path="README.md"`) publishes the profile.

### Multi-agent pattern (for the "Best Multi-Agent Workflow" prize)
- **Orchestrator agent**: the only one that speaks the chat protocol to ASI:One. It plans and delegates.
- **Worker agents**: each does one job (search, pricing, booking, summarizing). They talk to the orchestrator through custom `Model` messages.
- Use `ctx.send(addr, Msg)` for fire-and-forget messages, and `ctx.send_and_receive(addr, Msg, response_type=Reply)` for request/response. It returns `(reply, status)`; check `isinstance(reply, Reply)` before using it.
- `Bureau()` runs several agents in one process (handy for local dev).

---

## 7. Setup

Python **3.10 to 3.13** (not 3.14+).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install "uagents==0.25.5" openai python-dotenv
python -c "from uagents_core.contrib.protocols.chat import chat_protocol_spec; print(chat_protocol_spec.name, chat_protocol_spec.version)"
# expect: AgentChatProtocol 0.3.0
```

`.env`:
```
ASI1_API_KEY=your-asi1-api-key        # https://asi1.ai/dashboard/api-keys
AI_AGENT_ADDRESS=PASTE_YOUR_ASI_AGENT_ADDRESS
```

### Reference: ASI:One-compatible chat agent (`agent.py`, from the docs)

```python
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

load_dotenv()

subject_matter = "the sun"

asi1_api_key = os.getenv("ASI1_API_KEY")
if not asi1_api_key:
    raise RuntimeError("ASI1_API_KEY is not set.")

client = OpenAI(base_url="https://api.asi1.ai/v1", api_key=asi1_api_key)

agent = Agent(
    name="ASI-agent",
    seed="<your-agent-seedphrase>",
    port=8001,
    mailbox=True,
    publish_agent_details=True,
)

protocol = Protocol(spec=chat_protocol_spec)


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))

    text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    response = "I am afraid something went wrong and I am unable to answer your question at the moment"
    try:
        r = client.chat.completions.create(
            model="asi1",
            messages=[
                {"role": "system", "content": f"You are a helpful assistant who only answers questions about {subject_matter}. If the user asks about any other topics, politely say you do not know about them."},
                {"role": "user", "content": text},
            ],
            max_tokens=2048,
        )
        response = str(r.choices[0].message.content)
    except Exception as err:
        ctx.logger.exception("Error querying model: %s", err)

    await ctx.send(
        sender,
        ChatMessage(content=[
            TextContent(type="text", text=response),
            EndSessionContent(type="end-session"),
        ]),
    )


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


agent.include(protocol, publish_manifest=True)

if __name__ == "__main__":
    agent.run()
```

### Reference: agent-to-agent messaging (from the docs)

```python
from uagents import Agent, Bureau, Context, Model

class Message(Model):
    text: str

alice = Agent(name="alice")
bob = Agent(name="bob")

@alice.on_interval(period=2.0)
async def send_message(ctx: Context):
    await ctx.send(bob.address, Message(text=f"Hello {bob.name}, I'm {alice.name}."))

@bob.on_message(model=Message)
async def message_handler(ctx: Context, sender: str, msg: Message):
    ctx.logger.info(f"Received message from {sender}: {msg.text}")

bureau = Bureau()
bureau.add(alice)
bureau.add(bob)

if __name__ == "__main__":
    bureau.run()
```

### Register on Agentverse & test in ASI:One
1. Create an ASI:One account, generate an API key, and put it in `.env`.
2. Sign up on Agentverse.
3. Run `python agent.py` and leave it running. Copy the `agent1q...` address from the log.
4. Open the **Agent Inspector URL** printed in the terminal, click **Connect**, then **Mailbox**, then **Finish**.
5. Wait for the logs confirming mailbox registration and manifest publication.
6. In the Inspector, open **Agent Profile**. On Agentverse, edit the name, handle, and description, then click **Chat with Agent**.
7. You land in ASI:One chat. Send an in-scope question and check the terminal for: incoming message, then ASI:One API call, then outgoing reply.
8. A 401 error means a bad or missing API key.

### Gotchas
- The seed determines the address. Use your own unique seed and keep it stable.
- Port must match the endpoint port, and each agent needs a unique port.
- The agent must **stay running** to stay reachable. Stopping it marks it inactive.
- Chrome v142+ and Brave may block the local Inspector. Allow "local network access".
- Both sides of a custom message must define the **identical `Model`**.
- Agentverse *hosted* agents only allow some packages. Use a mailbox (local) agent for anything else.
- `handle_messages_concurrently=True` is risky with shared `ctx.storage` writes.

---

## 8. Important Links

- [Register / Dashboard](https://asi1.ai/festival/fetchathon3/dashboard?utm_source=fetchathon3)
- [Create an agent with uAgents](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation)
- [Connect a local agent to Agentverse (Mailbox)](https://innovationlab.fetch.ai/resources/docs/agent-creation/uagent-creation#mailbox-agents)
- [Communication between two uAgents](https://innovationlab.fetch.ai/resources/docs/agent-communication/uagent-uagent-communication)
- [ASI:One-compatible uAgents (chat protocol)](https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/asi-compatible-uagents)
- [ASI:One API quickstart](https://innovationlab.fetch.ai/resources/docs/asione/asi-one-quickstart)
- [Integrate ASI:One LLM with your uAgent](https://innovationlab.fetch.ai/resources/docs/asione/asi-one-overview)
- [ASI1 Interactive Cards](https://innovationlab.fetch.ai/resources/docs/interactive-cards/asi-interactive-cards)
- [MCP Integration](https://innovationlab.fetch.ai/resources/docs/mcp-integration/what-is-mcp)
- [Image Generation Agent example](https://innovationlab.fetch.ai/resources/docs/examples/chat-protocol/image-generation-agent)
- [Fetch-skills CLI installer](https://innovationlab.fetch.ai/resources/docs/fetch-skills/overview)
- [Innovation Lab examples (GitHub)](https://github.com/fetchai/innovation-lab-examples)
- [Past hackathon projects](https://innovationlab.fetch.ai/projects)
- [Fetch.ai Medium](https://medium.com/fetch-ai/latest)
- Agentverse MCP server (deploy agents from Claude): full `https://mcp.agentverse.ai/sse`, lite `https://mcp-lite.agentverse.ai/mcp`

---

## 9. Andrej Karpathy Coding Guidelines (follow these while building)

Behavioral guidelines to reduce common LLM coding mistakes, derived from [Andrej Karpathy's observations](https://x.com/karpathy/status/2015883857489522876) on LLM coding pitfalls.
**Tradeoff:** these bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them; don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative.**
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it; don't delete it.
- Remove imports/variables/functions that YOUR changes made unused; leave pre-existing dead code unless asked.

The test: every changed line should trace directly to the request.

### 4. Goal-Driven Execution
**Define success criteria. Loop until verified.**
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

### Applied to this hackathon
1. Get the reference `agent.py` responding in ASI:One **first** → verify: a Shared Chat URL works.
2. Add one real tool/API call → verify: the reply contains live data.
3. Add worker agents only if the workflow needs them → verify: the orchestrator logs each worker reply.
4. Add bonus features (Interactive Cards, Payment Protocol) last.
5. Leave 30+ min before 16:30 for README badges, agent addresses, the demo video, and dashboard submission.
