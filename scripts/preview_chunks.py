"""本地开发检查工具，不是用户接口；--role 用于模拟不同权限范围。"""
import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path

from app.chunking import chunk_documents
from app.loaders import load_authorized_documents
from app.permissions import ROLE_ACCESS
from app.tokenization import MODEL_NAME, get_tokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description="按权限读取资料并生成可检查的 chunks")
    parser.add_argument("--role", choices=sorted(ROLE_ACCESS), default="employee")
    parser.add_argument("--target-tokens", type=int, default=300)
    parser.add_argument("--overlap-tokens", type=int, default=40)
    parser.add_argument("--download-tokenizer", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"资料根目录：{PROJECT_ROOT / 'resources' / 'challenge_data'}", flush=True)
    print(f"模拟角色：{args.role} | tokenizer：{MODEL_NAME}", flush=True)
    tokenizer = get_tokenizer(allow_download=args.download_tokenizer)
    documents = load_authorized_documents(args.role)
    chunks = chunk_documents(documents, tokenizer, args.target_tokens, args.overlap_tokens)

    lengths_by_source = defaultdict(list)
    for chunk in chunks:
        lengths_by_source[chunk["metadata"]["source_file"]].append(chunk["token_count"])

    for source, lengths in lengths_by_source.items():
        print(f"{source}：{len(lengths)} 块，token 范围 {min(lengths)}–{max(lengths)}")

    output_path = PROJECT_ROOT / "storage" / "previews" / f"chunks_{args.role}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "role": args.role,
        "model": MODEL_NAME,
        "target_tokens": args.target_tokens,
        "overlap_tokens": args.overlap_tokens,
        "overlap_policy": "同章节超长普通文本保留重叠；表格重复表头；不跨章节或员工重叠",
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"共 {len(documents)} 条文档记录 → {len(chunks)} 个 chunks")
    print(f"完整结果：{output_path}")


if __name__ == "__main__":
    main()
