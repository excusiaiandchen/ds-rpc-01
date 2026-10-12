from fastapi import HTTPException

#在这里保存权限矩阵，具体可见readme.md
ROLE_ACCESS = {
    "employee": {"general"},
    "finance": {"general", "finance"},
    "marketing": {"general", "marketing"},
    "hr": {"general", "hr"},
    "engineering": {"general", "engineering"},
    "c_level": {"general", "finance", "marketing", "hr", "engineering"},
}


def get_allowed_departments(app_role: str) -> list[str]:
    # 未知角色不授予访问权限
    if app_role not in ROLE_ACCESS:
        raise HTTPException(status_code=403, detail="账号角色无效")

    return sorted(ROLE_ACCESS[app_role])