import os
from pathlib import Path

import httpx
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def get_llm_configuration() -> dict:
    load_dotenv(PROJECT_ROOT / ".env")

    base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model_name = os.getenv("LLM_MODEL", "").strip()

    if not base_url:
        raise RuntimeError("请在 .env 中填写 LLM_BASE_URL")

    if not api_key:
        raise RuntimeError("请在 .env 中填写 LLM_API_KEY")

    if not model_name:
        raise RuntimeError("请在 .env 中填写 LLM_MODEL")

    return {
        "base_url": base_url,
        "api_key": api_key,
        "model_name": model_name,
    }



def call_llm(messages: list[dict]) -> dict:
    if not messages:
        raise ValueError("发送给模型的消息不能为空")

    configuration = get_llm_configuration()

    request_url = configuration["base_url"] + "/chat/completions"

    headers = {
        "Authorization": "Bearer " + configuration["api_key"],
        "Content-Type": "application/json",
    }

    request_body = {
        "model": configuration["model_name"],
        "messages": messages,
        "stream": False,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                request_url,
                headers=headers,
                json=request_body,
            )
    except httpx.TimeoutException as error:
        raise RuntimeError("模型请求超时，请稍后重试") from error
    except httpx.RequestError as error:
        raise RuntimeError("无法连接模型服务，请检查网络和 API 地址") from error

    if response.status_code == 401:
        raise RuntimeError("模型服务认证失败，请检查 API Key")

    if response.status_code == 429:
        raise RuntimeError("模型服务请求受限，请检查额度或稍后重试")

    if not response.is_success:
        raise RuntimeError(
            f"模型调用失败，HTTP 状态码：{response.status_code}"
        )

    try:
        response_data = response.json()
        answer = response_data["choices"][0]["message"]["content"]
        usage = response_data.get("usage", {})
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise RuntimeError("模型服务返回的数据格式异常") from error

    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("模型服务没有返回有效回答")

    return {
        "answer": answer.strip(),
        "usage": usage,
        "model": configuration["model_name"],
    }

