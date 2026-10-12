from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.tokenization import MODEL_NAME, MODEL_CACHE, MODEL_MAX_TOKENS


@lru_cache(maxsize=1)
def get_embedding_model():
    # 同一个进程内复用模型，避免每次向量化都重新加载。
    model = SentenceTransformer(
        MODEL_NAME,
        cache_folder=str(MODEL_CACHE),
        device="cpu",
    )
    model.max_seq_length = MODEL_MAX_TOKENS
    return model


def encode_texts(texts: list[str], prefix: str):
    if not texts:
        raise ValueError("需要至少提供一段文本")

    model = get_embedding_model()
    model_inputs = [prefix + text for text in texts]

    # 超长时明确报错，避免模型悄悄截掉后面的内容。
    for text in model_inputs:
        token_ids = model.tokenizer(
            text,
            add_special_tokens=True,
            truncation=False,
        )["input_ids"]

        if len(token_ids) > model.max_seq_length:
            raise ValueError(
                f"文本有 {len(token_ids)} 个 token，"
                f"超过上限 {model.max_seq_length}"
            )

    return model.encode(
        model_inputs,
        batch_size=16,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
    )


def embed_documents(chunk_texts: list[str]):
    return encode_texts(chunk_texts, prefix="passage: ")


def embed_question(question: str):
    if not question.strip():
        raise ValueError("问题不能为空")

    vectors = encode_texts([question], prefix="query: ")
    return vectors[0]