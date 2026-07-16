import bcrypt
import psycopg


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_demo_users():
    conn = psycopg.connect(
        "postgresql://rental:rental@localhost:5432/rental_housing"
    )
    cur = conn.cursor()

    tenant_pw = hash_password("demo123456")
    landlord_pw = hash_password("demo123456")

    try:
        cur.execute(
            """
            INSERT INTO users (username, password_hash, email, role, status, email_verified, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (username) DO NOTHING
            RETURNING id, username, role
            """,
            ("tenant_demo", tenant_pw, "tenant@demo.com", "tenant", "active", True),
        )
        tenant = cur.fetchone()
        if tenant:
            print(f"租客账号创建成功: id={tenant[0]}, username={tenant[1]}, role={tenant[2]}")
        else:
            print("租客账号已存在，跳过")

        cur.execute(
            """
            INSERT INTO users (username, password_hash, email, role, status, email_verified, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (username) DO NOTHING
            RETURNING id, username, role
            """,
            ("landlord_demo", landlord_pw, "landlord@demo.com", "landlord", "active", True),
        )
        landlord = cur.fetchone()
        if landlord:
            print(f"房东账号创建成功: id={landlord[0]}, username={landlord[1]}, role={landlord[2]}")
        else:
            print("房东账号已存在，跳过")

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"创建用户失败: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    create_demo_users()
