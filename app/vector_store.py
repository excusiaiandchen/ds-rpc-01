from pathlib import Path

import chromadb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHROMA_DIR = PROJECT_ROOT / "storage" / "chroma"


def get_collection(collection_name: str):
    # 数据自动保存到硬盘，下次启动仍能读取。
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    return client.get_or_create_collection(
        name=collection_name,
        embedding_function=None,
    )


def save_chunks(collection, chunks: list[dict], vectors):
    if len(chunks) != len(vectors):
        raise ValueError("chunk 数量与向量数量不一致")

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        ids.append(chunk["chunk_id"])
        documents.append(chunk["content"])
        metadatas.append(chunk["metadata"])

    # 相同 ID 更新，新的 ID 插入。
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=vectors.tolist(),
    )
