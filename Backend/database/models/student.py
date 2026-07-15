from sqlalchemy import String
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from database.connect import Base


class Student(Base):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    roll_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    branch: Mapped[str] = mapped_column(String(100))
    semester: Mapped[int]

    embeddings = relationship(
        "FaceEmbedding",
        back_populates="student",
        cascade="all, delete-orphan"
    )
#     ef register_user(
#     name: str,
#     roll_no: str,
#     branch: str,
#     semester: int,
#     images: List[UploadFile]
# ):