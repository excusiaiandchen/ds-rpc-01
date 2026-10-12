import json
import logging
from collections import Counter
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

from app.chunking import chunk_documents
from app.embeddings import embed_documents
from app.loaders import (
    DATA_DIR,
    list_authorized_files,
    load_authorized_documents,
)
from app.tokenization import MODEL_NAME
from app.vector_store import CHROMA_DIR, get_collection, save_chunks


ACTIVE_INDEX_PATH = CHROMA_DIR.parent / "active_index.json"

EXPECTED_FILE_COUNTS = {
    "engineering": 1,
    "finance": 2,
    "general": 1,
    "hr": 1,
    "marketing": 5,
}


def main():
    started_at = perf_counter()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # 本地建库需要处理全部资料；用户查询时仍按账号权限过滤。
    files = list_authorized_files("c_level")
    file_counts = Counter(
        item["access_department"] for item in files
    )

    if dict(file_counts) != EXPECTED_FILE_COUNTS:
        raise ValueError(f"业务文件数量不符合预期：{dict(file_counts)}")

    print("Data directory:", DATA_DIR)
    print("Input files:", len(files))
    print("Embedding model:", MODEL_NAME)

    documents = load_authorized_documents("c_level")
    chunks = chunk_documents(documents)

    if not chunks:
        raise ValueError("没有生成任何 chunk")

    chunk_ids = [chunk["chunk_id"] for chunk in chunks]

    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("出现重复 chunk ID")

    chunk_counts = Counter(
        chunk["metadata"]["access_department"] for chunk in chunks
    )

    for department, count in sorted(chunk_counts.items()):
        print(f"{department}: {count} chunks")

    # 每次完整建库使用新集合，避免旧资料和新资料混在一起。
    collection_name = "finsolve_e5_" + uuid4().hex
    collection = get_collection(collection_name)

    batch_size = 32

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        texts = [chunk["content"] for chunk in batch]

        vectors = embed_documents(texts)
        save_chunks(collection, batch, vectors)

        saved_count = min(start + batch_size, len(chunks))
        print(f"Saved: {saved_count}/{len(chunks)}")

    # 检查记录数量、ID，以及保存后的权限和来源。
    stored = collection.get(include=["metadatas"])
    expected_metadata = {
        chunk["chunk_id"]: chunk["metadata"]
        for chunk in chunks
    }

    if collection.count() != len(chunks):
        raise RuntimeError("入库后的记录数量不正确")

    if set(stored["ids"]) != set(chunk_ids):
        raise RuntimeError("入库后的 chunk ID 不正确")

    for chunk_id, metadata in zip(
        stored["ids"], stored["metadatas"]
    ):
        if metadata != expected_metadata[chunk_id]:
            raise RuntimeError("入库后的 metadata 不正确")

    # 全部保存并校验成功后，才切换当前使用的索引。
    manifest = {
        "collection_name": collection_name,
        "embedding_model": MODEL_NAME,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version": "challenge-v1",
        "file_count": len(files),
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "chunks_by_department": dict(chunk_counts),
    }

    temporary_path = ACTIVE_INDEX_PATH.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(ACTIVE_INDEX_PATH)

    print("\nBuild complete")
    print("Collection:", collection_name)
    print("Stored chunks:", collection.count())
    print("Active index:", ACTIVE_INDEX_PATH)
    print(f"Elapsed seconds: {perf_counter() - started_at:.1f}")


if __name__ == "__main__":
    main()