import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.security import hash_password, verify_password
import psycopg


def main():
    conn = psycopg.connect(
        "postgresql://rental:rental@localhost:5432/rental_housing"
    )
    cur = conn.cursor()

    cur.execute("SELECT id, username, password_hash, role FROM users WHERE username IN ('tenant_demo', 'landlord_demo')")
    rows = cur.fetchall()

    print("数据库中的用户:")
    for row in rows:
        print(f"  id={row[0]}, username={row[1]}, role={row[3]}")
        print(f"  password_hash (前50字): {row[2][:50] if row[2] else 'None'}...")

        # 用 passlib 验证
        if row[2]:
            result = verify_password("demo123456", row[2])
            print(f"  passlib 验证 demo123456: {result}")
        print()

    # 如果验证失败，就用 passlib 重新生成密码并更新
    for row in rows:
        if row[2]:
            result = verify_password("demo123456", row[2])
            if not result:
                print(f"用户 {row[1]} 密码验证失败，正在重置...")
                new_hash = hash_password("demo123456")
                cur.execute(
                    "UPDATE users SET password_hash = %s WHERE id = %s",
                    (new_hash, row[0]),
                )
                print(f"  新密码哈希 (前50字): {new_hash[:50]}...")

    conn.commit()
    cur.close()
    conn.close()
    print("\n完成！")


if __name__ == "__main__":
    main()
