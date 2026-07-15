from sqlalchemy.orm import Session
from database.models.student import Student
from database.models.faceEmbeddings import FaceEmbedding

def create_student(
    db: Session,
    name: str,
    roll_no: str,
    branch: str,
    semester: int,
) -> Student:
    db_student = Student(
        name=name,
        roll_no=roll_no,
        branch=branch,
        semester=semester,
    )
    db.add(db_student)
    db.flush()  
    return db_student

def create_embedding(
    db: Session,
    student_id: int,
    image_path: str,
    embedding: list[float],
) -> FaceEmbedding:
    db_embedding = FaceEmbedding(
        student_id=student_id,
        image_path=image_path,
        embedding=embedding,
    )
    db.add(db_embedding)
    db.flush()
    return db_embedding