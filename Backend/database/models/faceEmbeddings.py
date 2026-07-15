from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from database.connect import Base

class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id")
    )
    image_path: Mapped[str] = mapped_column(String(255))
    embedding: Mapped[list[float]] = mapped_column( Vector(512))
    student = relationship(
        "Student",
        back_populates="embeddings"
    )