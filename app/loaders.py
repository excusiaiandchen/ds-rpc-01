from pathlib import Path

from app.permissions import get_allowed_departments
import csv
import hashlib
import re

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "resources" / "challenge_data"

def list_authorized_files(app_role: str) -> list[dict]:
    # 根据后端确定的角色，获取允许访问的资料类别
    allowed_departments = get_allowed_departments(app_role)
    files = []

    for department in allowed_departments:
        folder = DATA_DIR / department

        if not folder.is_dir():
            raise FileNotFoundError(f"资料目录不存在：{folder}")

        # 当前资料直接存放在各类别文件夹中
        for path in sorted(folder.iterdir()):
            if path.is_symlink() or not path.is_file():
                continue

            if path.suffix.lower() not in {".md", ".csv"}:
                continue

            files.append({
                "source_file": path.relative_to(DATA_DIR).as_posix(),
                "access_department": department,
            })

    return files

def make_document(
    content: str,
    source_file: str,
    department: str,
    source_type: str,
    record_key: str,
    title: str,
    headings: list[str],
) -> dict:
    # 来源标识稳定；内容变化时，文档记录 ID 随之变化
    source_id = hashlib.sha256(
        source_file.encode("utf-8")
    ).hexdigest()

    document_id = hashlib.sha256(
        f"{source_file}\n{record_key}\n{content}".encode("utf-8")
    ).hexdigest()

    return {
        "document_id": document_id,
        "content": content,
        "title": title,
        "headings": headings,
        "metadata": {
            "source_id": source_id,
            "source_file": source_file,
            "access_department": department,
            "source_type": source_type,
            "record_key": record_key,
            "dataset_version": "challenge-v1",
        },
    }


def load_authorized_documents(app_role: str) -> list[dict]:
    documents = []

    # 复用现有权限过滤，只读取当前角色允许的文件
    for item in list_authorized_files(app_role):
        source_file = item["source_file"]
        department = item["access_department"]
        path = DATA_DIR / source_file

        if path.suffix.lower() == ".md":
            content = path.read_text(encoding="utf-8-sig")

            # 提取标题用于预览，正文保持原样，供后续按章节切块
            headings = re.findall(
                r"^#{1,6}[ \t]+(.+)$",
                content,
                flags=re.MULTILINE,
            )
            title = headings[0] if headings else path.stem

            documents.append(make_document(
                content=content,
                source_file=source_file,
                department=department,
                source_type="markdown",
                record_key="document",
                title=title,
                headings=headings,
            ))

        elif path.suffix.lower() == ".csv":
            # 当前项目唯一的 CSV 是 HR 员工表，不能误标为其他权限
            if department != "hr":
                raise ValueError(f"尚未支持此 CSV 的解析：{source_file}")

            with path.open(encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                seen_ids = set()

                for row in reader:
                    employee_id = row.get("employee_id", "").strip()

                    if not employee_id or employee_id in seen_ids:
                        raise ValueError("HR 表存在空员工编号或重复员工编号")

                    seen_ids.add(employee_id)

                    # 明确区分员工职位、所属部门与应用权限
                    labels = {
                        "role": "job_title",
                        "department": "employee_department",
                    }
                    content = "\n".join(
                        f"{labels.get(key, key)}: {value}"
                        for key, value in row.items()
                    )

                    document = make_document(
                        content=content,
                        source_file=source_file,
                        department="hr",
                        source_type="csv",
                        record_key=employee_id,
                        title=f"Employee {employee_id}",
                        headings=[],
                    )
                    document["metadata"]["employee_id"] = employee_id
                    documents.append(document)

    return documents












