# Fetch-A-Thon 3.0 Project

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

A chat agent that answers questions using the ASI:One LLM. Talk to it from ASI:One.

## Agents

| Name | Address |
|---|---|
| fetchathon-starter | `agent1qw7dkdsj6ss054z20el4dm4nzz6zsglxs38f4uxm0v960d0ltvfnj6g0vt9` |

## Run

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in ASI1_API_KEY and AGENT_SEED
python agent.py
```

Requires Python 3.10 to 3.13 and an ASI:One API key from https://asi1.ai/dashboard/api-keys.
