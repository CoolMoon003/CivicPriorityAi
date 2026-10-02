from sqlalchemy import Column, Integer, String

from backend.app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    role = Column(String, nullable=False, default="CITIZEN")
    phone = Column(String, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)