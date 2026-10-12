"""核心行为测试；字符 tokenizer 让边界测试不依赖联网下载。"""
import importlib
import importlib.util

import pytest


class CharacterTokenizer:
    def __call__(self, text, add_special_tokens=True, return_offsets_mapping=False,
                 truncation=False, verbose=True):
        result = {"input_ids": list(range(len(text) + (2 if add_special_tokens else 0)))}
        if return_offsets_mapping:
            result["offset_mapping"] = [(i, i + 1) for i in range(len(text))]
        return result


@pytest.fixture
def chunking():
    assert importlib.util.find_spec("app.chunking") is not None, "切块模块尚未实现"
    return importlib.import_module("app.chunking")


def document(content, department="general", source_type="markdown", key="document"):
    from app.loaders import make_document
    return make_document(content, f"{department}/sample.md", department,
                         source_type, key, "Document", [])


def test_heading_context_and_fenced_code(chunking):
    text = "# Year 2024\n## Q4\nTarget 220000; actual 180000.\n```python\n# not a heading\nprint(1)\n```\n## Q1\nOther."
    sections = chunking.split_markdown_sections(text)
    assert len(sections) == 2
    assert sections[0]["section"] == "Year 2024 / Q4"
    assert "# not a heading" in sections[0]["body"]
    assert "actual 180000" in sections[0]["body"]


def test_underlined_headings_keep_finance_section_context(chunking):
    sections = chunking.split_markdown_sections(
        "# Finance 2024\n\nSummary:\n-------\nIncome.\n\nCosts:\n-------\nVendor $30M."
    )
    assert [s["section"] for s in sections] == ["Finance 2024 / Summary:", "Finance 2024 / Costs:"]
    assert sections[1]["body"] == "Vendor $30M."


def test_long_prose_has_overlap_no_loss_and_bounded_length(chunking):
    body = "".join(chr(0x4e00 + i) for i in range(500))
    chunks = chunking.chunk_documents([document("# Policy\n" + body)],
        tokenizer=CharacterTokenizer(), target_tokens=120, overlap_tokens=15)
    bodies = [c["content"].split("\n\n", 1)[1] for c in chunks]
    assert len(chunks) > 1
    assert all(c["token_count"] <= 120 for c in chunks)
    assert all(char in "".join(bodies) for char in body)
    for left, right in zip(bodies, bodies[1:]):
        assert left[-15:] == right[:15]


def test_table_rows_keep_headers_and_currency(chunking):
    header = "| Item | Amount |\n|---|---|"
    rows = [f"| Hotel{i} | ₹{3000+i}/night |" for i in range(12)]
    chunks = chunking.chunk_documents([document("# Expenses\n" + header + "\n" + "\n".join(rows))],
        tokenizer=CharacterTokenizer(), target_tokens=150, overlap_tokens=15)
    assert len(chunks) > 1
    for chunk in chunks:
        assert header in chunk["content"]
        assert chunk["token_count"] <= 150
    for row in rows:
        assert sum(row in c["content"] for c in chunks) == 1


def test_hr_is_whole_and_does_not_inherit_employee_department(chunking):
    text = "employee_id: FINEMP1000\nemployee_department: Finance\nleave_balance: 22"
    doc = document(text, "hr", "csv", "FINEMP1000")
    chunks = chunking.chunk_documents([doc], tokenizer=CharacterTokenizer(), target_tokens=60, overlap_tokens=10)
    assert len(chunks) == 1
    assert text in chunks[0]["content"]
    assert chunks[0]["metadata"]["access_department"] == "hr"


def test_metadata_and_ids_are_preserved_and_repeatable(chunking):
    docs = [document("# Policy\nA."), document("# Design\nB.", "engineering")]
    first = chunking.chunk_documents(docs, tokenizer=CharacterTokenizer())
    second = chunking.chunk_documents(docs, tokenizer=CharacterTokenizer())
    assert first == second
    assert len({c["chunk_id"] for c in first}) == 2
    assert first[0]["metadata"]["access_department"] == "general"
    assert first[1]["metadata"]["access_department"] == "engineering"
    assert first[1]["metadata"]["source_file"] == "engineering/sample.md"


def test_missing_acl_is_rejected(chunking):
    doc = document("Hello")
    del doc["metadata"]["access_department"]
    with pytest.raises(ValueError, match="权限"):
        chunking.chunk_documents([doc], tokenizer=CharacterTokenizer())


def test_oversized_hr_fails_instead_of_truncating(chunking):
    with pytest.raises(ValueError, match="512"):
        chunking.chunk_documents([document("x" * 600, "hr", "csv", "ID1")],
                                 tokenizer=CharacterTokenizer())


def test_oversized_table_row_fails_instead_of_breaking_fields(chunking):
    with pytest.raises(ValueError, match="表格"):
        chunking.chunk_documents([document("# T\n| Name | Value |\n|---|---|\n| A | " + "x" * 600 + " |")],
                                 tokenizer=CharacterTokenizer())
