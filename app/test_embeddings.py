from app.embeddings import embed_documents, embed_question

documents = [
    "符合条件的员工每周最多可以远程办公两天。",
    "财务报告记录了本季度的供应商支出。",
]
question = "我能在家上班吗？"

# 检查中文是否被正确读入：“我”的 Unicode 编号是 25105。
print("First character code:", ord(question[0]))
assert ord(question[0]) == 25105, "Chinese input is corrupted"

document_vectors = embed_documents(documents)
question_vector = embed_question(question)

print("Document vectors:", document_vectors.shape)
print("Question vector:", question_vector.shape)

# 已归一化的向量，通过点积计算余弦相似度。
scores = document_vectors @ question_vector

for index, score in enumerate(scores, start=1):
    print(f"Document {index}: {score:.4f}")