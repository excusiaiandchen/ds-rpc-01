import json
from functools import lru_cache

import chromadb

from app.embeddings import embed_question
from app.permissions import get_allowed_departments
from app.tokenization import MODEL_NAME
from app.vector_store import CHROMA_DIR



#打开已经建好的资料集合，为检索准备用户权限条件，但是本函数并不执行搜索，下一个函数才是
@lru_cache(maxsize=1)#缓存函数的返回值，最大值已经被设置成1
def get_chroma_client():#chroma是一种向量存储库
    return chromadb.PersistentClient(path=str(CHROMA_DIR))

def open_active_collection():
    index_path = CHROMA_DIR.parent / "active_index.json"

    try:
        info = json.loads(index_path.read_text(encoding="utf-8"))
        collection_name = info["collection_name"]
        embedding_model = info["embedding_model"]
    except (OSError, ValueError, KeyError) as error:
        raise RuntimeError("索引配置不可用，请先完成建库") from error


    if embedding_model != MODEL_NAME:
        raise RuntimeError("查询模型与索引模型不一致，请重新建库")

    try:
        # 只打开已有集合，避免索引名称错误时创建空集合。
        return get_chroma_client().get_collection(
            name=collection_name,
            embedding_function=None,
        )
    except Exception as error:
        raise RuntimeError("无法打开当前索引，请检查建库结果") from error






#准备尝试检索
def retrieve(
    question: str,
    user: dict,
    top_k: int = 5,
    source_file: str | None = None,
) -> list[dict]:
    question = question.strip()

    if not question:
        raise ValueError("问题不能为空")

    # 根据已认证账号的真实角色获取权限。
    allowed = get_allowed_departments(user["app_role"])#查验角色的权限数据

    if not allowed:
        raise PermissionError("账号没有资料访问权限")

    permission_filter = {
        "access_department": {"$in": allowed}
    }
    where = permission_filter

    # 指定来源时，必须同时满足来源条件和权限条件。
    if source_file is not None:
        source_file = source_file.strip()

        if not source_file:
            raise ValueError("来源文件不能为空")

        where = {
            "$and": [
                permission_filter,
                {"source_file": {"$eq": source_file}},
            ]
        }

    collection = open_active_collection()
    question_vector = embed_question(question)

    result = collection.query(
            query_embeddings=[question_vector.tolist()],
            where=where,
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

    # 本次只查询了一个问题，因此取第一个问题对应的结果。
    chunk_ids = result["ids"][0]
    chunk_contents = result["documents"][0]
    chunk_metadatas = result["metadatas"][0]
    chunk_distances = result["distances"][0]

    matches = []

    for index in range(len(chunk_ids)):
        chunk_id = chunk_ids[index]
        content = chunk_contents[index]
        metadata = chunk_metadatas[index]
        distance = chunk_distances[index]

        # 缺少权限信息时，拒绝整次结果。
        if metadata is None:
            raise PermissionError("检索结果缺少 metadata")

        access_department = metadata.get("access_department")

        if access_department not in allowed:
            raise PermissionError("检索结果权限校验失败")

        # 如果指定了文件，检查结果确实来自该文件。
        if source_file is not None:
            actual_source_file = metadata.get("source_file")

            if actual_source_file != source_file:
                raise RuntimeError("检索结果来源校验失败")

        match = {
            "chunk_id": chunk_id,
            "content": content,
            "distance": float(distance),
            "metadata": metadata,
        }

        matches.append(match)

    return matches








