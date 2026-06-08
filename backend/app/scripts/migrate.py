import sys

from sqlalchemy.exc import OperationalError

from app.db.session import create_db_and_tables


def main() -> None:
    try:
        create_db_and_tables()
        print("Database tables are ready.")
    except OperationalError as exc:
        print("Database migration failed because PostgreSQL is not reachable.")
        print("Check DATABASE_URL in .env and make sure the local PostgreSQL service is running.")
        print(f"Original error: {exc.orig}")
        sys.exit(1)


if __name__ == "__main__":
    main()
