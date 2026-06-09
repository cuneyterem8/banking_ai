import sys

from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from app.db.session import create_db_and_tables, engine
from app.services.seeding import seed_all


def main() -> None:
    try:
        create_db_and_tables()
        with Session(engine) as session:
            seed_all(session)
        print("Seeded use cases plus Fraud Detection, Credit Risk, Document OCR, Support Chatbot, Liquidity Forecast, AML Monitoring, KYC/KYB, Email Automation, Market Intelligence, and Workflow Orchestration raw datasets.")
    except OperationalError as exc:
        print("Database seed failed because PostgreSQL is not reachable.")
        print("Check DATABASE_URL in .env and make sure the local PostgreSQL service is running.")
        print(f"Original error: {exc.orig}")
        sys.exit(1)


if __name__ == "__main__":
    main()
