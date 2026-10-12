from pathlib import Path

import pandas as pd


# 根据本脚本的位置找到项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "resources" / "challenge_data"

if not DATA_DIR.is_dir():
    raise FileNotFoundError(f"找不到资料目录：{DATA_DIR}")


# 一、检查业务文件
print("\n===== 业务文件清单 =====")

files = sorted(
    path for path in DATA_DIR.rglob("*")
    if path.is_file()
)

for path in files:
    print(path.relative_to(DATA_DIR))

markdown_files = [p for p in files if p.suffix.lower() == ".md"]
csv_files = [p for p in files if p.suffix.lower() == ".csv"]

print(f"\nMarkdown 文件数量：{len(markdown_files)}")
print(f"CSV 文件数量：{len(csv_files)}")


# 二、读取 Markdown，确认编码正常
print("\n===== Markdown 文件检查 =====")

for path in markdown_files:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    headings = [
        line.strip() for line in lines
        if line.startswith("#")
    ]

    print(f"\n文件：{path.relative_to(DATA_DIR)}")
    print(f"大小：{path.stat().st_size} 字节")
    print(f"行数：{len(lines)}")
    print(f"前 3 个标题：{headings[:3]}")


# 三、读取 HR 表格
print("\n===== HR 表格检查 =====")

df = pd.read_csv(
    DATA_DIR / "hr" / "hr_data.csv",
    dtype={"employee_id": str, "manager_id": str},
)

print(f"行数：{df.shape[0]}")
print(f"列数：{df.shape[1]}")
print(f"字段名称：{df.columns.tolist()}")
print(f"唯一员工 ID 数量：{df['employee_id'].nunique()}")
print(f"重复员工 ID 数量：{df['employee_id'].duplicated().sum()}")
print(f"重复姓名数量：{df['full_name'].duplicated().sum()}")
print(f"重复邮箱数量：{df['email'].duplicated().sum()}")

print("\n每列缺失值数量：")
print(df.isna().sum())

print("\n各部门的员工记录数量：")
print(df["department"].value_counts())