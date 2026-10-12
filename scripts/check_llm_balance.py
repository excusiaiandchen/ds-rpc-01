import os
from pathlib import Path

import httpx
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

api_key = os.getenv("LLM_API_KEY", "").strip()

if not api_key:
    raise RuntimeError(".env文件中的LLM 秘钥空白")

headers = {
    "Authorization": "Bearer " + api_key,
}

with httpx.Client(timeout=20.0) as client:
    response = client.get(
        "https://api.deepseek.com/user/balance",
        headers=headers,
    )

response.raise_for_status()

balance_information = response.json()
print(balance_information)







