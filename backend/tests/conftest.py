import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.db.models import UseCase
from app.use_cases.fraud_detection.raw_data import USE_CASE_SLUG
from app.use_cases.registry import get_use_case


@pytest.fixture(name="session")
def session_fixture() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        item = get_use_case(USE_CASE_SLUG)
        session.add(
            UseCase(
                slug=item.slug,
                title=item.title,
                category=item.category,
                description=item.description,
                adapter_type=item.adapter_type,
                model_family=item.model_family,
                status=item.status,
                implementation_order=item.implementation_order,
            )
        )
        session.commit()
        yield session
