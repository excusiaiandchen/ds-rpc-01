from app.llm import call_llm


def main():
    messages = [
        {
            "role": "user",
            "content": "你好，世界！",
        }
    ]

    result = call_llm(messages)

    print("使用模型：", result["model"])
    print("模型回答：", result["answer"])
    print("Token 用量：", result["usage"])


if __name__ == "__main__":
    main()