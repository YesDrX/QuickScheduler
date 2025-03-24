import pytest
from quickScheduler.backend.database import Database
from quickScheduler.backend.models import Base

@pytest.fixture(autouse=True)
def clean_database():
    """Clean up the database before each test.
    
    This fixture runs automatically before each test,
    ensuring a clean database state for proper test isolation.
    """
    db = Database()
    Base.metadata.drop_all(db.engine)
    Base.metadata.create_all(db.engine)