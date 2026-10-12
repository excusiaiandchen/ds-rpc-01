from app.embeddings import embed_documents
from app.vector_store import CHROMA_DIR, get_collection, save_chunks


def main():
    # 这是练习数据，单独存入演示集合。
    chunks = [
        {
            "chunk_id": "demo_remote_work",
            "content": "符合条件的员工每周最多可以远程办公两天。",
            "metadata": {
                "source_file": "demo",
                "access_department": "general",
            },
        },
        {
            "chunk_id": "demo_vendor_cost",
            "content": "财务报告记录了本季度的供应商支出。",
            "metadata": {
                "source_file": "demo",
                "access_department": "finance",
            },
        },
    ]

    texts = [chunk["content"] for chunk in chunks]
    vectors = embed_documents(texts)

    collection = get_collection("demo_e5_v1")
    save_chunks(collection, chunks, vectors)

    print("Storage directory:", CHROMA_DIR)
    print("Saved records:", collection.count())

    result = collection.get(
        ids=["demo_remote_work"],
        include=["documents", "metadatas"],
    )
    print("Read back:", result)


if __name__ == "__main__":
    main()