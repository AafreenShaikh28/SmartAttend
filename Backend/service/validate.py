from __future__ import annotations

import io
from typing import List

import cv2
import numpy as np
from fastapi import UploadFile
from insightface.app import FaceAnalysis
from PIL import Image, UnidentifiedImageError

MIN_IMAGES = 5
MAX_IMAGES = 10
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}
MAX_FILE_SIZE_MB = 8
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
# Faces smaller than this (relative to the image) are considered "too far away"
# to produce a reliable ArcFace embedding.
MIN_FACE_AREA_RATIO = 0.03  # face bounding box must cover at least 3% of the image
# Laplacian variance below this value usually means the image is blurry.
BLUR_THRESHOLD = 60.0
# Average pixel brightness (0-255). Below/above these values, the face is
# too dark or too washed out for a clean embedding.
MIN_BRIGHTNESS = 40
MAX_BRIGHTNESS = 220
# RetinaFace confidence score below this is not trustworthy enough.
MIN_DETECTION_CONFIDENCE = 0.75


# LOAD THE FACE MODEL ONCE (
face_app = FaceAnalysis(name="buffalo_l")  # buffalo_l bundles RetinaFace + ArcFace
face_app.prepare(ctx_id=-1, det_size=(640, 640))
# ctx_id=0 -> use GPU 0 if available. Use ctx_id=-1 to force CPU.


# ---------------------------------------------------------------------------
# 1. HOW MANY IMAGES WERE UPLOADED?
# ---------------------------------------------------------------------------
def validate_image_count(images: List[UploadFile]) -> None:
    count = len(images)
    if count < MIN_IMAGES:
        raise ValueError(
            f"Please upload at least {MIN_IMAGES} images (you uploaded {count})."
        )
    if count > MAX_IMAGES:
        raise ValueError(
            f"Please upload no more than {MAX_IMAGES} images (you uploaded {count})."
        )

# ---------------------------------------------------------------------------
# 2. IS THE FILE EXTENSION ALLOWED?
# ---------------------------------------------------------------------------
def validate_extension(image: UploadFile) -> None:
    filename = image.filename or ""
    # os.path.splitext would also work; simple string check is easy to read.
    lower_name = filename.lower()

    if not any(lower_name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise ValueError(
            f"'{filename}' has an unsupported file extension. "
            f"Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

# ---------------------------------------------------------------------------
# 3. IS THE FILE'S DECLARED MIME TYPE ALLOWED?
# ---------------------------------------------------------------------------
def validate_mime_type(image: UploadFile) -> None:
    content_type = image.content_type or ""

    if content_type not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f"'{image.filename}' has an unsupported content type "
            f"('{content_type}'). Only JPEG and PNG images are allowed."
        )

# ---------------------------------------------------------------------------
# 4. IS THE FILE SIZE REASONABLE?
# ---------------------------------------------------------------------------
def validate_file_size(image: UploadFile, file_bytes: bytes) -> None:
    size_in_bytes = len(file_bytes)

    if size_in_bytes == 0:
        raise ValueError(f"'{image.filename}' is empty.")

    if size_in_bytes > MAX_FILE_SIZE_BYTES:
        size_in_mb = size_in_bytes / (1024 * 1024)
        raise ValueError(
            f"'{image.filename}' is too large "
            f"({size_in_mb:.1f}MB). Max allowed size is {MAX_FILE_SIZE_MB}MB."
        )

# ---------------------------------------------------------------------------
# 5. IS THE IMAGE FILE ACTUALLY A VALID, UNCORRUPTED IMAGE?
# ---------------------------------------------------------------------------
def validate_image_integrity(image: UploadFile, file_bytes: bytes) -> Image.Image:
    try:
        pil_image = Image.open(io.BytesIO(file_bytes))
        pil_image.verify()  # quick structural check (doesn't fully decode pixels)

        # verify() closes the file pointer internally, so we must re-open
        # the image if we want to actually use it afterwards.
        pil_image = Image.open(io.BytesIO(file_bytes))
        pil_image.load()  # force full decode now, so any hidden corruption surfaces here
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValueError(
            f"'{image.filename}' is not a valid or is a corrupted image file."
        ) from error

    return pil_image.convert("RGB")

# ---------------------------------------------------------------------------
# 6. DOES THE IMAGE CONTAIN EXACTLY ONE FACE?
# ---------------------------------------------------------------------------
def validate_single_face(image: UploadFile, pil_image: Image.Image) -> "list":
    # InsightFace expects a BGR numpy array (OpenCV convention), so convert.
    rgb_array = np.array(pil_image)
    bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)

    faces = face_app.get(bgr_array)

    if len(faces) == 0:
        raise ValueError(
            f"No face was detected in '{image.filename}'. "
            "Please upload a clear photo showing the student's face."
        )

    if len(faces) > 1:
        raise ValueError(
            f"'{image.filename}' contains {len(faces)} faces. "
            "Please upload a photo with only the student's face visible."
        )

    return faces

# ---------------------------------------------------------------------------
# 7. IS THE DETECTED FACE HIGH ENOUGH QUALITY TO EMBED?
# ---------------------------------------------------------------------------
def validate_face_quality(image: UploadFile, pil_image: Image.Image, face) -> None:
    # --- 7a. Detection confidence from RetinaFace ---
    confidence = float(face.det_score)
    if confidence < MIN_DETECTION_CONFIDENCE:
        raise ValueError(
            f"Face in '{image.filename}' was detected with low confidence "
            f"({confidence:.2f}). Please upload a clearer photo."
        )

    # --- 7b. Crop just the face region, so blur/brightness checks focus ---
    #         on the face itself, not the whole background.
    x1, y1, x2, y2 = [int(coord) for coord in face.bbox]
    rgb_array = np.array(pil_image)
    face_crop = rgb_array[max(y1, 0):max(y2, 0), max(x1, 0):max(x2, 0)]

    if face_crop.size == 0:
        raise ValueError(
            f"Could not extract a usable face region from '{image.filename}'."
        )

    gray_face = cv2.cvtColor(face_crop, cv2.COLOR_RGB2GRAY)

    # --- 7c. Blur check using the variance of the Laplacian ---
    # A sharp image has lots of edges -> high variance.
    # A blurry image has smoothed-out edges -> low variance.
    blur_score = cv2.Laplacian(gray_face, cv2.CV_64F).var()
    if blur_score < BLUR_THRESHOLD:
        raise ValueError(
            f"Face in '{image.filename}' appears too blurry "
            f"(sharpness score {blur_score:.1f}). Please upload a sharper photo."
        )

    # --- 7d. Brightness check using mean pixel intensity ---
    brightness = float(gray_face.mean())
    if brightness < MIN_BRIGHTNESS:
        raise ValueError(
            f"Face in '{image.filename}' is too dark to process clearly. "
            "Please upload a better-lit photo."
        )
    if brightness > MAX_BRIGHTNESS:
        raise ValueError(
            f"Face in '{image.filename}' is too bright/overexposed. "
            "Please upload a photo without strong glare or backlight."
        )

# ---------------------------------------------------------------------------
# 8. IS THE FACE BIG ENOUGH IN THE FRAME?
# ---------------------------------------------------------------------------
def validate_face_size(image: UploadFile, pil_image: Image.Image, face) -> None:
    image_width, image_height = pil_image.size
    image_area = image_width * image_height

    x1, y1, x2, y2 = face.bbox
    face_width = x2 - x1
    face_height = y2 - y1
    face_area = face_width * face_height

    face_area_ratio = face_area / image_area

    if face_area_ratio < MIN_FACE_AREA_RATIO:
        raise ValueError(
            f"Face in '{image.filename}' is too small in the frame. "
            "Please upload a closer photo of the student's face."
        )

# ---------------------------------------------------------------------------
# MAIN ENTRY POINT — runs all checks in order, for every uploaded image
# ---------------------------------------------------------------------------
def validate_input_images(images: List[UploadFile]) -> None:

    validate_image_count(images)
    for image in images:
        
        validate_extension(image)
        validate_mime_type(image)
        file_bytes = image.file.read()
        image.file.seek(0)  
        validate_file_size(image, file_bytes)
        pil_image = validate_image_integrity(image, file_bytes)
        faces = validate_single_face(image, pil_image)
        face = faces[0] 
        validate_face_quality(image, pil_image, face)
        validate_face_size(image, pil_image, face)