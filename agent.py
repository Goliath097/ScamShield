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

asi1_api_key = os.getenv("ASI1_API_KEY")
if not asi1_api_key or asi1_api_key.startswith("your-"):
    raise RuntimeError(
        "ASI1_API_KEY is not set. Create a key at https://asi1.ai/dashboard/api-keys "
        "and paste it into .env"
    )

client = OpenAI(base_url="https://api.asi1.ai/v1", api_key=asi1_api_key)

agent = Agent(
    name="fetchathon-starter",
    seed=os.environ["AGENT_SEED"],
    port=8001,
    mailbox=True,
    publish_agent_details=True,
    readme_path="README.md",
)

protocol = Protocol(spec=chat_protocol_spec)


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))

    text = "".join(item.text for item in msg.content if isinstance(item, TextContent))
    ctx.logger.info(f"Message from {sender}: {text}")

    response = "Sorry, something went wrong and I can't answer right now."
    try:
        r = client.chat.completions.create(
            model="asi1",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": text},
            ],
            max_tokens=2048,
        )
        response = str(r.choices[0].message.content)
    except Exception as err:
        ctx.logger.exception("Error querying ASI:One: %s", err)

    await ctx.send(
        sender,
        ChatMessage(
            content=[
                TextContent(type="text", text=response),
                EndSessionContent(type="end-session"),
            ]
        ),
    )


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
    agent.run()
