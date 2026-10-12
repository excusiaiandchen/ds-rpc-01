# Step 9：切块与 token 长度检查

## 运行

在 `finsolve-rbac` 根目录运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.preview_chunks --role employee
```

终端先打印资料根目录，再逐个打印文件路径、权限，最后打印每个文件的块数及 token 范围。
完整结果保存到 `storage/previews/chunks_employee.json`，可以直接用 PyCharm 打开。
`--role c_level` 可检查全部资料。此参数是本地开发工具的模拟角色，不是网络用户的权限入口。
导出的全量 JSON 含 HR 记录，仅供本地检查，不能作为不受保护的静态文件发布。

首次在另一台机器运行时，可加 `--download-tokenizer` 下载 tokenizer 到 `storage/model_cache`。
本步骤只需要 tokenizer，不下载 Embedding 模型权重，也不调用收费模型。

## 三个核心设计

1. **按章节拆分**：识别 `#` 层级标题、横线式标题；把父章节路径放进每块正文。代码块中的 `#` 不作为标题。
2. **按真实 token 数控长**：使用 `intfloat/multilingual-e5-small` 的 tokenizer。目标 300 token，包含 `passage: `、章节路径和特殊 token；短章节不硬凑长。最终块不得超过 512 token。
3. **每块继承权限和来源**：复制原文 metadata；权限缺失或未知时拒绝处理。片段 ID 由处理版本、文档 ID、位置和内容生成，相同输入可重复得到相同 ID。

## 边界处理

- 同章节超长普通正文在分段时尽量保留约 40 token 重叠；不跨章节、文件或员工记录做重叠。
- 长表格按完整行拆分，各块重复表头。单行太长时明确报错，不拆断字段。
- 完整代码块允许超过 300 的目标值，但不能超过 512；超长时明确报错。
- HR 每位员工保持一个完整块；`employee_department=Finance` 不会改变 `access_department=hr`。
- 保留原文的金额、时间和目标/实际表述，不自动修正业务事实。
- 此解析器面向本项目的 Markdown 格式，并非完整 CommonMark 解析器。引入其他结构的资料时需补充测试。

## 浏览器查看

启动后端并在 `/docs` 中授权，执行 `GET /chunks/preview`。
`offset` 控制起始位置，`limit` 控制一次展示数量（1–10）。接口只使用 JWT 对应账号的数据库角色。

这是调试预览接口，每次重新处理当前角色允许的资料。正式聊天会改为查询已建立的向量索引。
后续向量化必须使用同一模型及 `passage: ` 前缀，避免切块测量与实际输入不一致。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_chunking.py tests/test_chunks_api.py -q
```

测试使用临时账号数据库，不修改真实用户账号。
覆盖章节上下文、正文重叠、表格表头、HR 完整性、稳定 ID、权限缺失、超长拒绝、六角色访问范围，以及无令牌/伪造/过期/禁用账号拒绝。

2026-09-23 本地验证：17 项测试通过；依赖库有 2 条弃用提示。
当前资料以默认参数得到 321 个块，其中 HR 100 个，普通员工可见 56 个。
实际长度范围为 30–294 token；它们不是 321 个文件，而是 10 个业务文件派生的片段。

后续 Step 10：加载 Embedding 模型，将这些块转换成向量并写入 Chroma；当前尚未建立向量索引。
