"""切块与后续向量化统一使用 E5 的 tokenizer 和输入前缀。"""
from functools import lru_cache
from pathlib import Path

from transformers import AutoTokenizer


MODEL_NAME = "intfloat/multilingual-e5-small"
MODEL_MAX_TOKENS = 512
PASSAGE_PREFIX = "passage: "
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_CACHE = PROJECT_ROOT / "storage" / "model_cache"


@lru_cache(maxsize=2)
def get_tokenizer(allow_download: bool = False):
    # 浏览器请求只用本地缓存，下载由本地脚本显式触发。
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            cache_dir=str(MODEL_CACHE),
            use_fast=True,
            local_files_only=not allow_download,
        )
    except OSError as error:
        raise RuntimeError(
            "无法加载 E5 tokenizer。请在项目根目录运行："
            "python -m scripts.preview_chunks --download-tokenizer"
        ) from error

    if not tokenizer.is_fast:
        raise RuntimeError("切块需要 fast tokenizer 的字符位置映射")

    return tokenizer


def count_passage_tokens(tokenizer, content: str) -> int:
    # 包含模型前缀、章节标题及特殊 token；始终关闭静默截断。
    encoded = tokenizer(
        PASSAGE_PREFIX + content,
        add_special_tokens=True,
        truncation=False,
        verbose=False,
    )
    return len(encoded["input_ids"])
