"""使用临时账号数据库验证 JWT、权限和真实语料；不修改用户数据库。"""
import sqlite3
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app
from app.permissions import ROLE_ACCESS


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "users.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE users (user_id INTEGER, username TEXT, password_hash TEXT, app_role TEXT, is_active INTEGER)")
        test_hash = auth.password_hasher.hash("local-test-password")
        for index, role in enumerate(ROLE_ACCESS, start=1):
            connection.execute("INSERT INTO users VALUES (?, ?, ?, ?, 1)", (index, role, test_hash, role))
        connection.execute("INSERT INTO users VALUES (99, 'disabled', ?, 'employee', 0)", (test_hash,))
    monkeypatch.setattr(auth, "DB_PATH", path)
    monkeypatch.setattr(auth, "JWT_SECRET", "local-test-signing-key-that-is-not-used-by-the-app")
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("role", list(ROLE_ACCESS))
def test_real_chunks_follow_authenticated_role(client, role):
    login = client.post("/auth/token", data={"username": role, "password": "local-test-password"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    offset = 0
    all_chunks = []
    while True:
        # 伪装的查询参数不得覆盖服务器中的角色。
        response = client.get("/chunks/preview", params={"offset": offset, "limit": 10, "app_role": "c_level"}, headers=headers)
        assert response.status_code == 200
        body = response.json()
        all_chunks.extend(body["samples"])
        if len(all_chunks) >= body["chunk_count"]:
            break
        offset += 10
    assert all_chunks
    for chunk in all_chunks:
        assert chunk["metadata"]["access_department"] in ROLE_ACCESS[role]
        assert chunk["token_count"] <= 512
    if role in {"hr", "c_level"}:
        hr_chunks = [c for c in all_chunks if c["metadata"]["access_department"] == "hr"]
        assert len(hr_chunks) == 100
        assert len({c["metadata"]["employee_id"] for c in hr_chunks}) == 100
    assert client.get("/chunks/preview", params={"limit": 11}, headers=headers).status_code == 422


def test_missing_forged_expired_and_disabled_tokens_are_rejected(client):
    assert client.get("/chunks/preview").status_code == 401
    now = datetime.now(timezone.utc)
    cases = [
        ("1", now + timedelta(minutes=5), "wrong-key-which-is-at-least-thirty-two-characters"),
        ("1", now - timedelta(minutes=5), auth.JWT_SECRET),
        ("99", now + timedelta(minutes=5), auth.JWT_SECRET),
    ]
    for subject, expires, secret in cases:
        token = jwt.encode({"sub": subject, "exp": expires}, secret, algorithm=auth.JWT_ALGORITHM)
        result = client.get("/chunks/preview", headers={"Authorization": "Bearer " + token})
        assert result.status_code == 401


def test_wrong_password_and_disabled_login_are_rejected(client):
    for username, password in [("employee", "wrong"), ("disabled", "local-test-password")]:
        assert client.post("/auth/token", data={"username": username, "password": password}).status_code == 401
