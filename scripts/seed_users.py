import sqlite3
from getpass import getpass
from pathlib import Path

from pwdlib import PasswordHash


# 定位项目根目录和数据库文件
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "storage" / "users.db"

# 演示账号及其角色，密码在运行时输入
DEMO_USERS = [
    ("Tony", "engineering"),
    ("Peter", "engineering"),
    ("Sam", "finance"),
    ("Bruce", "marketing"),
    ("Sid", "marketing"),
    ("Natasha", "hr"),
    ("Employeedemo1", "employee"),
    ("ExecutiveDemo1", "c_level"),
]

password_hasher = PasswordHash.recommended()  # 使用 Argon2 处理密码

#批量创建账号
#取出预设的用户名和角色。
# 让你为每个账号设置密码。
# 将密码转换为哈希，存入数据库。
# 已存在的账号直接跳过
def main():
    # 只读写已有数据库，避免路径错误时创建空数据库
    database_uri = DB_PATH.resolve().as_uri() + "?mode=rw"
    connection = sqlite3.connect(database_uri, uri=True)

    try:
        for username, app_role in DEMO_USERS:
            # 检查账号是否存在，避免重复创建
            existing = connection.execute(
                "SELECT user_id FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if existing:
                print(f"跳过已有账号：{username}")
                continue

            # 隐藏密码输入，要求非空且两次一致
            while True:
                password = getpass(f"为 {username} 设置密码：")
                confirmation = getpass("再次输入密码：")

                if not password:
                    print("密码不能为空。")
                elif password != confirmation:
                    print("两次密码不一致，请重新输入。")
                else:
                    break

            # 数据库存储密码哈希，不存储原始密码
            password_hash = password_hasher.hash(password)

            # 成功时提交，异常时回滚本次写入
            with connection:
                connection.execute(
                    """
                    INSERT INTO users
                        (username, password_hash, app_role, is_active)
                    VALUES (?, ?, ?, 1)
                    """,
                    (username, password_hash, app_role),  # 对应三个 ? 占位符
                )

            print(f"已创建：{username}，角色：{app_role}")

        # 查询账号总数；fetchone()[0] 取出查询结果中的数值
        count = connection.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        print(f"\n数据库中的账号总数：{count}")

    finally:
        connection.close()  # 无论成功或失败，都关闭连接


if __name__ == "__main__":
    main()