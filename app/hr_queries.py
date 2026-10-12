import csv

from app.loaders import DATA_DIR
from app.permissions import get_allowed_departments
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

#该函数完成了：1先确认是否具有hr权限    2若有，则返回响应的数据
def read_authorized_hr_records(user: dict) -> list[dict]:
    # 在读取文件之前，检查当前账号的权限。
    allowed_departments = get_allowed_departments(user["app_role"])

    if "hr" not in allowed_departments:
        raise PermissionError("当前账号没有 HR 资料访问权限")

    file_path = DATA_DIR / "hr" / "hr_data.csv"

    records = []

    #如果权限正确，那么就是返回整个HR的CSV文件
    with file_path.open(
            mode="r",
            encoding="utf-8-sig",
            newline="",
    )as file:
        reader = csv.DictReader(file)

        for row in reader:
            records.append(dict(row))

    return records







def get_employee(employee_id: str, user: dict) -> dict:
    employee_id = employee_id.strip()

    if not employee_id:
        raise ValueError("员工 ID 不能为空")

        # 复用前面的函数：先检查权限，再读取完整数据。
    records = read_authorized_hr_records(user)

    matched_records = []#用于临时的记录数据

    for record in records:
        if record["employee_id"] == employee_id:
            matched_records.append(record)

    if len(matched_records) == 0:
        print("无匹配数据！")
        return {
            "found": False,
            "employee_id": employee_id,
            "record": None,
            "source_file": "hr/hr_data.csv",
        }

    if len(matched_records) > 1:
        raise RuntimeError("员工 ID 重复/搜索到多个员工！无法确定唯一记录")

    return {
        "found": True,
        "employee_id": employee_id,
        "record": matched_records[0],
        "source_file": "hr/hr_data.csv",
    }




def count_records(
    user: dict,
    employee_department: str | None = None,
) -> dict:

    records = read_authorized_hr_records(user)#如果权限正确，那么就是返回整个HR的CSV文件

    if employee_department is not None:
        employee_department = employee_department.strip()

        if not employee_department:
            raise ValueError("员工部门不能为空")

    matched_count = 0

    for record in records:
        if employee_department is None:
            matched_count += 1
        elif record["department"].casefold() == employee_department.casefold():
            matched_count += 1

    return {
        "record_count": matched_count,
        "filters": {
            "employee_department": employee_department,
        },
        "total_record_count": len(records),
        "calculation": "统计完整 CSV 中符合筛选条件的记录数量",
        "source_file": "hr/hr_data.csv",
    }


def average_salary(
    user: dict,
    employee_department: str | None = None,
) -> dict:
    records = read_authorized_hr_records(user)

    if employee_department is not None:
        employee_department = employee_department.strip()

        if not employee_department:
            raise ValueError("员工部门不能为空")

    total_salary = Decimal("0")
    matched_count = 0

    for record in records:
        if employee_department is not None:
            actual_department = record["department"].casefold()
            requested_department = employee_department.casefold()

            if actual_department != requested_department:
                continue

        try:
            salary = Decimal(record["salary"])
        except (InvalidOperation, KeyError, TypeError) as error:
            raise RuntimeError("HR 数据中的工资字段无效") from error

        if not salary.is_finite() or salary < 0:
            raise RuntimeError("HR 数据中的工资字段无效")

        total_salary += salary
        matched_count += 1

    average_value = None

    if matched_count > 0:
        average_value = (
            total_salary / Decimal(matched_count)
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        average_value = str(average_value)

    return {
        "average_salary": average_value,
        "record_count": matched_count,
        "filters": {
            "employee_department": employee_department,
        },
        "calculation": "符合条件的 salary 总和除以记录数量，保留两位小数",
        "source_file": "hr/hr_data.csv",
        "note": "原始数据未说明工资币种和计薪周期",
    }









