import os
import argparse
import getpass
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
import mysql.connector

load_dotenv(override=True)


def get_mysql():
    return mysql.connector.connect(
        host=os.environ.get("MYSQL_HOST", "localhost"),
        user=os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=os.environ.get("MYSQL_DB", "govverify"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
    )


def seed_admin(email, name, password, reset_password=False):
    conn = get_mysql()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing = cursor.fetchone()

        if existing:
            updates = ["role = 'admin'"]
            params = []
            if reset_password:
                updates.append("password_hash = %s")
                params.append(generate_password_hash(password))
            params.append(email)
            cursor.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE email = %s",
                tuple(params),
            )
            conn.commit()
            return "updated"

        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'admin')",
            (name, email, password_hash),
        )
        conn.commit()
        return "created"
    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Seed or elevate an admin user")
    parser.add_argument('--email', required=True, help='Admin email')
    parser.add_argument('--name', default='Admin', help='Admin display name')
    parser.add_argument('--password', help='Admin password (omit to be prompted)')
    parser.add_argument('--reset-password', action='store_true', help='Reset password if user exists')
    args = parser.parse_args()

    password = args.password or getpass.getpass('Admin password: ')
    if not password:
        raise SystemExit('Password is required.')

    result = seed_admin(args.email, args.name, password, reset_password=args.reset_password)
    if result == 'created':
        print('Admin user created.')
    else:
        print('Admin user updated to admin role.' + (' Password reset.' if args.reset_password else ''))


if __name__ == '__main__':
    main()
