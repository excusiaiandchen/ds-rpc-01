import sqlite3
from pathlib import Path


# 数据库固定放在项目的 storage 文件夹中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "storage" / "users.db"


def main():
    # 如果 storage 文件夹不存在，就创建它
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 数据库文件不存在时，SQLite 会自动创建
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                app_role TEXT NOT NULL CHECK (
                    app_role IN (
                        'employee',
                        'finance',
                        'marketing',
                        'hr',
                        'engineering',
                        'c_level'
                    )
                ),
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1))
            )
        """)

        columns = connection.execute(
            "PRAGMA table_info(users)"
        ).fetchall()

        user_count = connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

    print(f"数据库位置：{DB_PATH}")
    print(f"用户表字段：{[column[1] for column in columns]}")
    print(f"当前账号数量：{user_count}")


if __name__ == "__main__":
    main()