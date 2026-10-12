"""先按章节拆分，再按 E5 token 长度处理超长章节。"""
import hashlib
import logging
import re

from app.permissions import ROLE_ACCESS
from app.tokenization import MODEL_MAX_TOKENS, MODEL_NAME, count_passage_tokens, get_tokenizer


logger = logging.getLogger(__name__)
CHUNKING_VERSION = "sections-e5-v1"
KNOWN_DEPARTMENTS = set().union(*ROLE_ACCESS.values())


def split_markdown_sections(content: str) -> list[dict]:
    sections = []
    heading_stack = []
    body_lines = []
    fence_marker = None

    def save_section():
        body = "\n".join(body_lines).strip()
        if not body or re.fullmatch(r"[\s*_-]+", body):
            return

        titles = [title for level, title in heading_stack]
        sections.append({"section": " / ".join(titles) or "正文", "body": body})

    for line in content.splitlines():
        stripped = line.strip()
        fence = re.match(r"^(`{3,}|~{3,})", stripped)

        # 代码块里的 # 不是章节标题。
        if fence:
            marker = fence.group(1)
            if fence_marker is None:
                fence_marker = marker
            elif (marker[0] == fence_marker[0] and len(marker) >= len(fence_marker)
                  and stripped == marker):
                fence_marker = None
            body_lines.append(line)
            continue

        heading = None
        if fence_marker is None:
            heading = re.match(r"^ {0,3}(#{1,6})[ \t]+(.+)$", line)

        # 财务汇总使用“标题下一行写 ----”的 Markdown 标题格式。
        underline = re.fullmatch(r" {0,3}(=+|-+)[ \t]*", line)
        if fence_marker is None and underline and body_lines and body_lines[-1].strip():
            title = body_lines.pop().strip()
            save_section()
            body_lines = []
            level = 1 if underline.group(1).startswith("=") else 2
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            continue

        if heading is None:
            body_lines.append(line)
            continue

        save_section()
        body_lines = []
        level = len(heading.group(1))
        title = heading.group(2).strip()
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        heading_stack.append((level, title))

    save_section()
    return sections


def split_structural_blocks(body: str) -> list[tuple[str, str]]:
    """表格、代码块单独保留，其余正文保留段落换行。"""
    lines = body.splitlines()
    blocks = []
    text_lines = []
    index = 0

    def flush_text():
        text = "\n".join(text_lines).strip()
        if text:
            blocks.append(("text", text))
        text_lines.clear()

    while index < len(lines):
        stripped = lines[index].strip()
        fence = re.match(r"^(`{3,}|~{3,})", stripped)

        if fence:
            flush_text()
            marker = fence.group(1)
            code_lines = [lines[index]]
            index += 1
            while index < len(lines):
                line = lines[index]
                code_lines.append(line)
                index += 1
                closing = line.strip()
                if re.fullmatch(re.escape(marker[0]) + "{" + str(len(marker)) + ",}", closing):
                    break
            blocks.append(("code", "\n".join(code_lines)))
            continue

        if stripped.startswith("|"):
            flush_text()
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            blocks.append(("table", "\n".join(table_lines)))
            continue

        text_lines.append(lines[index])
        index += 1

    flush_text()
    return blocks


class SectionSplitter:
    def __init__(self, tokenizer, target_tokens: int, overlap_tokens: int):
        if not 0 <= overlap_tokens < target_tokens <= MODEL_MAX_TOKENS:
            raise ValueError("要求 0 <= overlap < target <= 512")
        self.tokenizer = tokenizer
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens

    def count(self, section: str, body: str) -> int:
        return count_passage_tokens(self.tokenizer, section + "\n\n" + body)

    def offsets(self, body: str):
        encoded = self.tokenizer(
            body, add_special_tokens=False, return_offsets_mapping=True,
            truncation=False, verbose=False,
        )
        return [(start, end) for start, end in encoded["offset_mapping"] if end > start]

    def split_text(self, section: str, body: str) -> list[str]:
        parts = []
        remaining = body

        while self.count(section, remaining) > self.target_tokens:
            offsets = self.offsets(remaining)
            # 先预留标题和前缀的空间，再测量实际拼接结果。
            budget = self.target_tokens - self.count(section, "") - 2
            end_token = min(budget, len(offsets))
            if end_token <= self.overlap_tokens:
                raise ValueError(f"章节标题过长，无法保留正文与重叠：{section}")

            cut = offsets[end_token - 1][1]
            while self.count(section, remaining[:cut]) > self.target_tokens:
                end_token -= 1
                if end_token <= self.overlap_tokens:
                    raise ValueError(f"无法在目标 token 数内切分：{section}")
                cut = offsets[end_token - 1][1]

            # 如果附近有段落边界，优先在那里结束。
            paragraph_end = remaining.rfind("\n\n", cut // 2, cut)
            if paragraph_end > 0:
                candidate = remaining[:paragraph_end]
                if len(self.offsets(candidate)) > self.overlap_tokens:
                    cut = paragraph_end

            part = remaining[:cut]
            parts.append(part.strip())

            if self.overlap_tokens:
                part_offsets = self.offsets(part)
                next_start = part_offsets[-self.overlap_tokens][0]
            else:
                next_start = cut

            if next_start <= 0:
                raise ValueError(f"重叠长度导致切块无法前进：{section}")
            remaining = remaining[next_start:]

        if remaining.strip():
            parts.append(remaining.strip())
        return parts

    def split_table(self, section: str, table: str) -> list[str]:
        lines = table.splitlines()
        if len(lines) < 2 or not re.fullmatch(r"[\s|:\-]+", lines[1]):
            raise ValueError(f"无法识别表格表头，需人工检查：{section}")

        header = lines[:2]
        rows = lines[2:]
        parts = []
        current_rows = []

        for row in rows:
            one_row = "\n".join(header + [row])
            if self.count(section, one_row) > self.target_tokens:
                raise ValueError(f"单行表格超过目标长度，不自动拆断字段：{section}")

            candidate = "\n".join(header + current_rows + [row])
            if current_rows and self.count(section, candidate) > self.target_tokens:
                parts.append("\n".join(header + current_rows))
                current_rows = []
            current_rows.append(row)

        if current_rows:
            parts.append("\n".join(header + current_rows))
        return parts

    def split(self, section: str, body: str) -> list[str]:
        if self.count(section, body) <= self.target_tokens:
            return [body]

        parts = []
        for kind, block in split_structural_blocks(body):
            if self.count(section, block) <= self.target_tokens:
                parts.append(block)
            elif kind == "table":
                parts.extend(self.split_table(section, block))
            elif kind == "code":
                # 保留完整代码/架构图，允许超过目标值，但不能超过模型上限。
                if self.count(section, block) > MODEL_MAX_TOKENS:
                    raise ValueError(f"完整代码块超过 512 token，需要单独处理：{section}")
                parts.append(block)
            else:
                parts.extend(self.split_text(section, block))
        return parts


def chunk_documents(documents: list[dict], tokenizer=None,
                    target_tokens: int = 300, overlap_tokens: int = 40) -> list[dict]:
    if tokenizer is None:
        tokenizer = get_tokenizer()
    splitter = SectionSplitter(tokenizer, target_tokens, overlap_tokens)
    chunks = []
    last_source = None

    for document in documents:
        metadata = document["metadata"]
        department = metadata.get("access_department")
        if department not in KNOWN_DEPARTMENTS:
            raise ValueError("文档缺少有效权限标签，禁止切块")

        source = metadata["source_file"]
        if source != last_source:
            logger.info("正在切块：%s | 权限：%s", source, department)
            last_source = source

        source_type = metadata["source_type"]
        if source_type == "markdown":
            sections = split_markdown_sections(document["content"])
        elif source_type == "csv":
            if department != "hr":
                raise ValueError("HR 员工记录必须保留 hr 权限")
            sections = [{"section": document["title"], "body": document["content"]}]
        else:
            raise ValueError(f"不支持的文档类型：{source_type}")

        for section_index, section in enumerate(sections):
            title = section["section"]
            if source_type == "csv":
                bodies = [section["body"]]
            else:
                bodies = splitter.split(title, section["body"])

            for part_index, body in enumerate(bodies):
                content = title + "\n\n" + body
                token_count = count_passage_tokens(tokenizer, content)
                if token_count > MODEL_MAX_TOKENS:
                    raise ValueError(f"{source} / {title} 超过 512 token，禁止静默截断")

                identity = (
                    f"{CHUNKING_VERSION}|{document['document_id']}|"
                    f"{section_index}|{part_index}|{content}"
                )
                chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    "document_id": document["document_id"],
                    "section": title,
                    "section_index": section_index,
                    "part_index": part_index,
                    "token_count": token_count,
                    "tokenizer_model": MODEL_NAME,
                    "chunking_version": CHUNKING_VERSION,
                })
                chunks.append({"chunk_id": chunk_id, "content": content,
                               "token_count": token_count, "metadata": chunk_metadata})

    return chunks
