import io
import cv2
import numpy as np
from typing import List
from fastapi import UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile
from retinaface import RetinaFace

# Fraction of the detected face box added as margin on each side,
# so InsightFace's own detector has enough context to re-detect it.
PADDING_RATIO = 0.4


def _pad_box(x1, y1, x2, y2, img_w, img_h, ratio=PADDING_RATIO):
    w, h = x2 - x1, y2 - y1
    pad_w, pad_h = int(w * ratio), int(h * ratio)
    return (
        max(0, x1 - pad_w),
        max(0, y1 - pad_h),
        min(img_w, x2 + pad_w),
        min(img_h, y2 + pad_h),
    )


def detectFace(image: UploadFile) -> List[UploadFile]:
    # Decode uploaded classroom image into an OpenCV array
    contents = image.file.read()
    npimg = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)  # BGR
    img_h, img_w = img.shape[:2]

    # Only detect bounding boxes here — do NOT use RetinaFace's own
    # align=True crop, since that produces a tight, pre-rotated face
    # with too little context for InsightFace's detector to re-find
    # a face in generate_embeddings(). Padding + letting InsightFace
    # do its own alignment downstream is more reliable end-to-end.
    detections = RetinaFace.detect_faces(img_path=img)

    face_uploads: List[UploadFile] = []
    if not isinstance(detections, dict):
        return face_uploads  # no faces found

    for i, (_, face_data) in enumerate(detections.items()):
        x1, y1, x2, y2 = face_data["facial_area"]
        x1, y1, x2, y2 = _pad_box(x1, y1, x2, y2, img_w, img_h)

        face_crop = img[y1:y2, x1:x2]
        if face_crop.size == 0:
            continue

        success, buffer = cv2.imencode(".jpg", face_crop)
        if not success:
            continue

        file_obj = io.BytesIO(buffer.tobytes())
        upload = StarletteUploadFile(
            filename=f"face_{i}.jpg",
            file=file_obj,
        )
        face_uploads.append(upload)

    return face_uploads