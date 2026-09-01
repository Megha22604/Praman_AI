import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL)


if __name__ == "__main__":
    try:
        conn = get_connection()

        cursor = conn.cursor()
        cursor.execute("SELECT version();")

        version = cursor.fetchone()[0]

        print("✅ Database connection successful!")
        print(version)

        cursor.close()
        conn.close()

    except Exception as e:
        print("❌ Database connection failed!")
        print(e)