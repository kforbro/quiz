from sqlalchemy import BigInteger, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, unique=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    json: Mapped[str] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=True)

    def __repr__(self) -> str:
        return f"Quiz(id={self.id!r}, name={self.name!r}, user_id={self.user_id!r}, json={self.json!r}, active={self.active!r})"


class Stat(Base):
    __tablename__ = "stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, unique=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    quiz_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    correct_count: Mapped[int] = mapped_column(BigInteger, nullable=True)
    total_questions: Mapped[int] = mapped_column(BigInteger, nullable=True)
