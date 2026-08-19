from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.registration import router as registration_router
from routes.attendance import router as attendance_router

from database.connect import Base
from database.connect import engine

from database.models import student,faceEmbeddings

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.include_router(registration_router)
app.include_router(attendance_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

