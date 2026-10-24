"""Connect the running agent to an Agentverse mailbox without the browser Inspector.

Does what the Inspector's "Connect -> Mailbox" button does: POST your Agentverse
API key to the agent's local /connect endpoint. Run it while agent.py is running.
"""

import json
import os
import sys
import urllib.request

from dotenv import load_dotenv

load_dotenv()

token = os.getenv("AGENTVERSE_API_KEY")
if not token or token.startswith("your-"):
    sys.exit("Set AGENTVERSE_API_KEY in .env (Agentverse -> profile -> API Keys)")

port = sys.argv[1] if len(sys.argv) > 1 else "8001"
req = urllib.request.Request(
    f"http://127.0.0.1:{port}/connect",
    data=json.dumps({"user_token": token, "agent_type": "mailbox"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(resp.read().decode())
except urllib.error.URLError as err:
    sys.exit(f"Could not reach the agent on port {port}. Is agent.py running? ({err})")
