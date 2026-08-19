import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from typing import List
from database.connect import get_db 


from service.generate_embeddings import generate_embeddings
from service.detectFace import detectFace
from service.similarity import similarity_match

router = APIRouter()
@router.post("/attendance")
async def attendance(image:UploadFile = File(...), db: Session = Depends(get_db)):
    # retina face to detect face() -> return array of face images
    faces = detectFace(image)
    if not faces:
        return {"message": "No faces detected in image.", "results": []}

    # service.generate_embeddings() ->already exists def generate_embeddings(images: List[UploadFile]) -> List[np.ndarray]:
    embeddings = generate_embeddings(faces)

    # check cosine similarirty 
    roll_nos = []
    for e in embeddings:
        result = similarity_match(db, e)
        roll_nos.append(result)

    return {
        "message": "Attendance processed.",
        "results": roll_nos, 
    }