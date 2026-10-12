import json
from collections import Counter

import chromadb

from app.embeddings import embed_question
from app.permissions import get_allowed_departments
from app.tokenization import MODEL_NAME
from app.vector_store import CHROMA_DIR


def main():
    # 读取当前索引名称，打开已经存在的集合。
    index_path = CHROMA_DIR.parent / "active_index.json"
    info = json.loads(index_path.read_text(encoding="utf-8"))

    if info["embedding_model"] != MODEL_NAME:
        raise ValueError("查询模型与建库模型不一致")

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_collection(
        name=info["collection_name"],
        embedding_function=None,
    )

    saved_count = collection.count()
    print("Expected chunks:", info["chunk_count"])
    print("Persisted chunks:", saved_count)

    if saved_count != info["chunk_count"]:
        raise RuntimeError("保存数量与建库记录不一致")

    # 检查五类资料是否都保存了。
    stored = collection.get(include=["metadatas"])
    counts = Counter(
        metadata["access_department"]
        for metadata in stored["metadatas"]
    )
    print("Chunks by department:", dict(counts))

    if dict(counts) != info["chunks_by_department"]:
        raise RuntimeError("各类别保存数量不一致")

    # 本地模拟普通员工。正式接口将从登录账号获取角色。
    role = "employee"
    allowed_departments = get_allowed_departments(role)

    question = input("\n请输入问题：").strip()
    question_vector = embed_question(question)

    # 核心：在允许访问的资料范围内搜索最相关的三个片段。
    result = collection.query(
        query_embeddings=[question_vector.tolist()],
        where={
            "access_department": {
                "$in": allowed_departments
            }
        },
        n_results=5,
        include=["documents", "metadatas", "distances"],
    )

    rows = zip(
        result["documents"][0],
        result["metadatas"][0],
        result["distances"][0],
    )

    for index, (content, metadata, distance) in enumerate(rows, 1):
        if metadata["access_department"] not in allowed_departments:
            raise RuntimeError("检索结果出现未授权资料")

        print(f"\n========== Result {index} ==========")
        print("Source:", metadata["source_file"])
        print("Section:", metadata["section"])
        print("Permission:", metadata["access_department"])
        print(f"Distance: {distance:.4f}")
        print(content)


if __name__ == "__main__":
    main()