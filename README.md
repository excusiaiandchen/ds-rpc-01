# FinSolve：基于 RAG 与 RBAC 的企业知识问答系统

基于 Codebasics RPC-01 starter 的学习与开发项目，当前已跑通单轮文档问答：JWT 身份认证 → 按角色过滤检索范围 → Chroma 向量检索 → 通义千问生成回答 → 返回引用来源。项目持续开发中，并非生产环境安全认证方案。

## 如何启动？

- **1先做前置准备**
- 打开 PowerShell，执行：
- cd 'F:\.donwload20241017\DS-RPC-01\finsolve-rbac'
- .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
- 然后在浏览器打开 http://127.0.0.1:8000/docs
- **2登录**
- 右上角的authorize，并填入账密(这在main.py中是有初始的几位角色的),到这里，已经返回令牌了
- **3确认身份**
- 从/me进入→ Try it out → Execute
- **4提交问题**
- /chat→Try it out
- 其中，source_file可以指定资料来源，原本是string作为占位符，建议删除这行和上面的句号
- 在question处编辑问题，点击execute即可执行
- 下方可以看到回答、引用等详细信息




## 已实现功能

- SQLite 用户存储、Argon2 密码哈希、短期 JWT 登录凭据，支持八个演示账号和六类角色。
- Markdown/CSV 解析、按章节切块、来源与权限元数据；真实语料为 10 个业务文件、109 条文档记录，当前切块配置生成 321 个 chunk。
- multilingual-e5-small 384 维 Embedding 与本地 Chroma 持久化索引；检索前按资料类别过滤，返回时再次检查权限。
- OpenAI 兼容的模型 HTTP 调用，目前使用百炼 qwen3.7-plus；授权证据编号、引用编号检查与资料不足反馈。
- HR 员工 ID 精确查询、部门记录数量与平均工资计算；在读取完整 CSV 前检查 HR 资料权限。

## 本地启动（Windows PowerShell）

以下命令在仓库根目录执行。开发环境使用 Python 3.12；首次下载 Embedding 模型需要联网。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

把生成的随机值填入本地 `.env` 的 `JWT_SECRET`，并填写模型服务的 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。Base URL 使用账号控制台的 OpenAI 兼容地址（以 `/compatible-mode/v1` 结尾）；程序会追加 `/chat/completions`。模型调用需要服务商的有效额度，不能保证免费。

```powershell
.\.venv\Scripts\python.exe -m scripts.init_users_db
.\.venv\Scripts\python.exe -m scripts.seed_users
.\.venv\Scripts\python.exe -m scripts.preview_chunks --role c_level --download-tokenizer
.\.venv\Scripts\python.exe -m scripts.build_index
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

种子脚本在终端逐个提示设置演示账号密码，不发布共享登录密码。已有账号会跳过。账号：Tony、Peter、Sam、Bruce、Sid、Natasha、Employeedemo1、ExecutiveDemo1。

打开 http://127.0.0.1:8000/docs，使用 Authorize 登录后调用 `POST /chat`：

```json
{
  "question": "员工每周可以远程办公几天？需要谁批准？",
  "top_k": 5
}
```

不限定文件时省略 `source_file`，不要保留 Swagger 示例中的 `"string"`。预期回答包含符合条件岗位每周最多两天、经理批准，并引用员工手册。`POST /search` 仅返回检索片段，不生成回答。

HR 接口：`GET /hr/employees/{employee_id}`、`GET /hr/statistics/count`、`GET /hr/statistics/average-salary`。部门筛选参数为 `employee_department`，可填 `Finance`；它是数据条件，不授予 Finance 账号 HR 资料权限。

## 模块分工与验证

| 文件 | 作用 |
|---|---|
| `app/auth.py`、`app/permissions.py` | 登录、JWT 校验与角色权限矩阵 |
| `app/loaders.py`、`app/tokenization.py`、`app/chunking.py` | 读取资料、Token 计数与切块 |
| `app/embeddings.py`、`app/vector_store.py` | 语义向量与本地存储 |
| `scripts/build_index.py`、`app/retrieval.py` | 全量建库与授权检索 |
| `app/llm.py`、`app/rag.py` | 模型调用、证据组织和引用编号检查 |
| `app/hr_queries.py`、`app/main.py` | HR 确定性查询和 HTTP 接口 |

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m scripts.test_llm
```

pytest 仅运行 `tests/` 下的自动化测试，覆盖切块、JWT 和角色资料访问。测试使用临时账号数据库，不修改个人数据库。首次运行 API 测试前需要下载 tokenizer，且需配置 JWT_SECRET。`scripts.test_llm` 是手动联网测试，会消耗模型服务额度。

已手动验证：远程办公问答与真实来源引用；普通员工指定 HR 文件检索为空；HR 查询 FINEMP1000 的假期余额为 22；Finance 部门记录数为 16；无 HR 权限的精确查询和统计返回 403。这些场景不代表完整安全或回答质量评估。

## 当前限制与后续工作

- HR 工具接口已独立实现，尚未通过自然语言路由接入 `/chat`；不能让模型仅凭 top-k 片段计算全量统计。
- 尚未实现多轮会话、聊天前端、审计记录和系统化 RAG 评估。
- 引用编号存在不等于回答每句话都有依据；资料不足判断仍依赖模型，尚未校准检索阈值。
- HR CSV 未说明 salary 的币种/计薪周期，也缺少完整在职/离职状态；记录数不能直接解释为当前在职人数。
- `.env`、SQLite 用户数据库、Chroma 索引和模型缓存不提交 GitHub。请自行初始化账号和索引。

## 项目来源

This is the starter repository for Codebasics's [Resume Project Challenge](https://codebasics.io/challenge/codebasics-gen-ai-data-science-resume-project-challenge) of building a RAG based Internal Chatbot with role based access control. Please fork this repository to get started.

原始 starter 使用 HTTPBasic；当前实现已替换为 SQLite、Argon2 与 JWT。保留原项目来源与挑战说明如下。

Visit the challenge page to learn more: [DS RPC-01](https://codebasics.io/challenge/codebasics-gen-ai-data-science-resume-project-challenge)
![alt text](resources/RPC_01_Thumbnail.jpg)
### Roles Provided
 - **engineering**
 - **finance**
 - **general**
 - **hr**
 - **marketing**


## 数据访问权限

用户登录后，由后端根据账号的角色决定允许访问的资料范围。

| 用户角色 | 通用资料 general | 财务 finance | 市场 marketing | 人事 hr   | 工程 engineering |
|---|------------------|--------------|----------------|-----------|---|
| employee | ✅️允许           | ❌️拒绝       | ❌️拒绝         | ❌️拒绝    | ❌️拒绝 |
| finance | ✅允许             | ✅允许       | ❌️拒绝         | ❌️拒绝    | ❌️拒绝 |
| marketing | ✅允许             | ❌️拒绝         | ✅允许         | ❌️拒绝    | ❌️拒绝 |
| hr | ✅允许             | ❌️拒绝         | ❌️拒绝         | ✅允许    | ❌️拒绝 |
| engineering | ✅允许             | ❌️拒绝         | ❌️拒绝         | ❌️拒绝    | ✅允许 |
| c_level | ✅允许             | ✅允许       | ✅允许         | ✅允许    | ✅允许 |


-简单来说，除了CLEVEL之外，所有职员都可以访问employee对应的general，
-然后每个部门的职员可以访问资料为：general+自身对应部门的资料
实施约定：
- 所有已认证角色都可以访问 general 通用资料。
- 未登录用户不能访问业务资料；未知角色不授予资料访问权限。
- hr_data.csv 中所有员工记录均属于 hr 权限范围，
  不根据员工的 department 字段开放给其他角色。
- employee 暂不提供查询本人 HR 私密记录的功能。
- c_level 可以读取全部业务资料，但不因此获得用户管理权限。
- 角色由后端确定，不能由用户在问题或请求参数中自行指定。
- 回答、引用来源和资料冲突比较，都只能使用用户有权访问的资料。







