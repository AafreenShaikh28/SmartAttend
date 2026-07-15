import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from typing import List

from database.connect import get_db 
from service.validate import validate_input_images
from service.generate_embeddings import generate_embeddings
from CRUD.registration import create_student, create_embedding

router = APIRouter()

UPLOAD_DIR = "storage/student_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/students/register")
async def register_student(
    name: str = Form(...),
    roll_no: str = Form(...),
    branch: str = Form(...),
    semester: int = Form(...),
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    # VALIDATE
    try:
        validate_input_images(images)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    # GENERATE EMBEDDINGS
    embeddings = generate_embeddings(images)

    # STORE IN DATABASE
    try:
        db_student = create_student(
            db=db,
            name=name,
            roll_no=roll_no,
            branch=branch,
            semester=semester,
        )

        for image, embedding in zip(images, embeddings):
            file_extension = os.path.splitext(image.filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{file_extension}"
            image_path = os.path.join(UPLOAD_DIR, unique_filename)

            with open(image_path, "wb") as f:
                f.write(image.file.read())

            create_embedding(
                db=db,
                student_id=db_student.id,
                image_path=image_path,
                embedding=embedding.tolist()
            )
        db.commit()

    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register student: {error}",
        )

    return {
        "message": "Student registered successfully.",
        "student_id": db_student.id,
        "images_saved": len(images),
    }