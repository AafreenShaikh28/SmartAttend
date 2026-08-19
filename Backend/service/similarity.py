# services/faceMatch.py
import numpy as np
from typing import Optional
from sqlalchemy.orm import Session

from database.models.student import Student
from database.models.faceEmbeddings import FaceEmbedding

SIMILARITY_THRESHOLD = 0.60  # cosine similarity cutoff


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32).flatten()
    b = np.asarray(b, dtype=np.float32).flatten()

    if a.shape != b.shape or a.size == 0:
        return -1.0  # malformed/mismatched embedding, never matches

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return -1.0

    return float(np.dot(a, b) / (norm_a * norm_b))


def similarity_match(db: Session, embedding: np.ndarray) -> str:
    """
    Compares one face embedding against all registered students'
    stored embeddings. Returns the matched roll_no, or "unknown".
    """
    query_vec = np.asarray(embedding, dtype=np.float32).flatten()
    if query_vec.size == 0:
        return "unknown"

    records = (
        db.query(FaceEmbedding, Student)
        .join(Student, FaceEmbedding.student_id == Student.id)
        .all()
    )

    if not records:
        return "unknown"

    best_score = -1.0
    best_roll_no: Optional[str] = None

    for face_embedding, student in records:
        stored_vec = face_embedding.embedding
        if stored_vec is None:
            continue  # missing embedding

        score = _cosine_similarity(query_vec, stored_vec)

        if score > best_score:
            best_score = score
            best_roll_no = student.roll_no

    if best_roll_no is not None and best_score >= SIMILARITY_THRESHOLD:
        return best_roll_no

    return "unknown"