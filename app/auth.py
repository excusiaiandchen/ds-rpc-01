import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError

from app.permissions import get_allowed_departments
from pydantic import BaseModel
from pwdlib import PasswordHash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "storage" / "users.db"

# 从项目根目录加载配置
load_dotenv(PROJECT_ROOT / ".env")

JWT_SECRET = os.getenv("JWT_SECRET", "")
TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_ALGORITHM = "HS256"

if len(JWT_SECRET) < 32:
    raise RuntimeError("请在 .env 中设置随机生成的 JWT_SECRET，长度至少 32 个字符")

if TOKEN_MINUTES <= 0:
    raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES 必须大于 0")

password_hasher = PasswordHash.recommended()

# 不存在的账号也做一次哈希验证，减少明显的响应时间差异
DUMMY_HASH = password_hasher.hash("dummy-password-not-for-login")

router = APIRouter(prefix="/auth", tags=["身份认证"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


def find_user(username: str):
    database_uri = DB_PATH.resolve().as_uri() + "?mode=ro"

    # 每次查询建立独立的只读连接，使用完自动关闭
    with closing(sqlite3.connect(database_uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row

        return connection.execute(
            """
            SELECT user_id, username, password_hash, app_role, is_active
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()


@router.post("/token", response_model=TokenResponse)
def login_for_token(
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
):
    user = find_user(form.username)

    # 使用用户输入的密码验证数据库里的 Argon2 哈希
    stored_hash = user["password_hash"] if user is not None else DUMMY_HASH
    password_valid = password_hasher.verify(form.password, stored_hash)

    if user is None or not password_valid or user["is_active"] != 1:
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误，或账号已禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 令牌只包含用户编号和到期时间，不放密码或密码哈希
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)
    payload = {
        "sub": str(user["user_id"]),#这里提供用户编号
        "exp": expires_at,#设定过期时间
    }

    access_token = jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )

# 从请求的 Authorization: Bearer ... 中获取令牌
# tokenUrl 告诉接口文档应通过哪个接口获取令牌
# 从请求的 Authorization: Bearer ... 中获取令牌
# tokenUrl 告诉接口文档应通过哪个接口获取令牌
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_error = HTTPException(
        status_code=401,
        detail="登录凭据无效或已过期，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 验证签名和有效期，并要求令牌包含用户编号及到期时间
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )

        user_id = payload["sub"]

        if not isinstance(user_id, str) or not user_id:
            raise credentials_error

    except InvalidTokenError:
        raise credentials_error

    # 每次读取数据库中的当前状态和角色
    database_uri = DB_PATH.resolve().as_uri() + "?mode=ro"

    with closing(sqlite3.connect(database_uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row

        user = connection.execute(
            """
            SELECT user_id, username, app_role, is_active
            FROM users
            WHERE CAST(user_id AS TEXT) = ?
            """,
            (user_id,),
        ).fetchone()

    if user is None or user["is_active"] != 1:
        raise credentials_error

    allowed_departments = get_allowed_departments(user["app_role"])

    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "app_role": user["app_role"],
        "allowed_departments": allowed_departments,
    }











