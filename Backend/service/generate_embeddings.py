from __future__ import annotations
import io
from typing import List
import cv2
import numpy as np
from fastapi import UploadFile
from PIL import Image

from service.validate import face_app


def generate_embeddings(images: List[UploadFile]) -> List[np.ndarray]:
    embeddings: List[np.ndarray] = []

    for image in images:
        # Read the image bytes and reset the file pointer, in case
        # something later in the pipeline (e.g. saving the original image)
        # needs to read this same file again.
        file_bytes = image.file.read()
        image.file.seek(0)

        # Decode into a PIL image, then into the BGR numpy array InsightFace expects.
        pil_image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        rgb_array = np.array(pil_image)
        bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)

        # Run RetinaFace + ArcFace. Since validation already guaranteed
        # exactly one face, we can safely take the first (only) result.
        faces = face_app.get(bgr_array)
        face = faces[0]

        # `.normed_embedding` is a 512-dim, L2-normalized vector — ready for
        # cosine-similarity comparison later via pgvector.
        embedding = face.normed_embedding
        embeddings.append(embedding)

    return embeddings
