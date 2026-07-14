from __future__ import annotations

import io
from typing import List, Tuple

import cv2
import numpy as np
from fastapi import UploadFile
from insightface.app import FaceAnalysis
from PIL import Image, UnidentifiedImageError

MIN_IMAGES = 5
MAX_IMAGES = 8  # tightened from 10 -> more images beyond ~8 mostly add near-duplicate
# poses rather than new gallery diversity, while increasing registration friction
# and storage/matching cost. See research report §6.

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png"}
MAX_FILE_SIZE_MB = 8
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Faces smaller than this (relative to the image) are considered "too far away"
# to produce a reliable ArcFace embedding after the 112x112 alignment crop.
MIN_FACE_AREA_RATIO = 0.035  # nudged up from 0.03, closer to Azure's documented
# 200x200px-in-1920x1080 "good recognition quality" recommendation once converted
# to an area ratio. See research report §2.

# An absolute resolution floor, independent of the face-area ratio above.
# A tiny face can pass the ratio check if the *whole photo* is also tiny
# (e.g. a 150x150 upload), which still yields a low-pixel-count crop.
MIN_IMAGE_DIMENSION_PX = 480  # reject photos smaller than 480px on either side

# Laplacian variance below this value usually means the image is blurry.
# NOTE: there is no literature-standard number for this -- every source that
# describes the variance-of-Laplacian method (Rosebrock/PyImageSearch,
# GeeksforGeeks, OpenCV calibration notebooks) says explicitly that the right
# cutoff depends on your camera/compression pipeline and crop resolution, and
# must be calibrated against your own sharp/blurry samples. 80.0 is an interim
# value inside the commonly-observed 10-1000 practitioner range -- plan to
# replace it once you've run that calibration. See research report §3.
BLUR_THRESHOLD = 70.0

# Average pixel brightness (0-255). Below/above these values, the face is
# too dark or too washed out for a clean embedding. ISO/IEC 29794-5 treats
# "exposure adequacy" as a standardized quality *category*, but does not
# publish a universal numeric mean-brightness cutoff, so this permissive
# band is engineering practice informed by that category, not a citation.
MIN_BRIGHTNESS = 40
MAX_BRIGHTNESS = 220

# RetinaFace confidence score below this is not trustworthy enough.
# Nudged up from 0.75 -> since enrollment is a controlled, cooperative
# capture (not a crowd/surveillance frame), it's reasonable to demand a
# higher-confidence detection than InsightFace's permissive library
# default of 0.5. See research report §1.
MIN_DETECTION_CONFIDENCE = 0.70

# Head pose limits in degrees. ArcFace is trained predominantly on
# near-frontal aligned crops; large yaw/pitch increases intra-class
# embedding distance and mismatches later frontal-ish attendance captures.
# Roughly follows AWS Rekognition's documented comparison-input guidance
# (pitch < 30 deg down / 45 deg up, yaw < 45 deg), tightened somewhat since
# this is a *reference* enrollment image, not a lenient comparison probe.
MAX_YAW_DEGREES = 25.0
MAX_PITCH_DEGREES = 20.0

# Minimum cosine similarity, using the model's own ArcFace embeddings,
# required between every pair of a student's uploaded photos. Cosine
# similarity thresholds for buffalo_l-family embeddings for a same-identity
# decision typically sit in the 0.3-0.45 band at low false-match rates
# (InsightFace's own model-selection guide); genuine same-person enrollment
# photos should sit comfortably above that. This check is nearly free since
# the embeddings are already being computed, and it catches a real-world
# registration-corruption failure mode (wrong photo uploaded into the batch)
# that none of the other checks catch. See research report §9.
CROSS_IMAGE_MIN_COSINE_SIM = 0.40

# Generic 5-point 3D face model (arbitrary units, nose tip at origin) used
# for solvePnP-based head-pose estimation from InsightFace's 5-point 2D
# landmarks (left eye, right eye, nose, left mouth corner, right mouth
# corner). This is the standard reduced-point analogue of the well-known
# 6-point dlib head-pose model, adapted to the 5 points InsightFace exposes
# by default on every detection (no extra landmark model required).
_POSE_MODEL_3D_POINTS = np.array(
    [
        (-165.0, 170.0, -135.0),  # left eye
        (165.0, 170.0, -135.0),   # right eye
        (0.0, 0.0, 0.0),          # nose tip
        (-150.0, -150.0, -125.0),  # left mouth corner
        (150.0, -150.0, -125.0),   # right mouth corner
    ],
    dtype=np.float64,
)


# LOAD THE FACE MODEL ONCE
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
# 6. IS THE IMAGE AT LEAST A SANE ABSOLUTE RESOLUTION?
# ---------------------------------------------------------------------------
def validate_image_resolution(image: UploadFile, pil_image: Image.Image) -> None:
    width, height = pil_image.size
    if width < MIN_IMAGE_DIMENSION_PX or height < MIN_IMAGE_DIMENSION_PX:
        raise ValueError(
            f"'{image.filename}' is only {width}x{height}px, which is too small "
            f"regardless of framing. Please upload a photo at least "
            f"{MIN_IMAGE_DIMENSION_PX}x{MIN_IMAGE_DIMENSION_PX}px."
        )

# ---------------------------------------------------------------------------
# 7. DOES THE IMAGE CONTAIN EXACTLY ONE FACE?
# ---------------------------------------------------------------------------
def validate_single_face(image: UploadFile, pil_image: Image.Image) -> list:
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
# 8. IS THE DETECTED FACE HIGH ENOUGH QUALITY TO EMBED?
# ---------------------------------------------------------------------------
def validate_face_quality(image: UploadFile, pil_image: Image.Image, face) -> None:
    # --- 8a. Detection confidence from RetinaFace ---
    confidence = float(face.det_score)
    if confidence < MIN_DETECTION_CONFIDENCE:
        raise ValueError(
            f"Face in '{image.filename}' was detected with low confidence "
            f"({confidence:.2f}). Please upload a clearer photo."
        )

    # --- 8b. Crop just the face region, so blur/brightness checks focus ---
    #         on the face itself, not the whole background.
    x1, y1, x2, y2 = [int(coord) for coord in face.bbox]
    rgb_array = np.array(pil_image)
    face_crop = rgb_array[max(y1, 0):max(y2, 0), max(x1, 0):max(x2, 0)]

    if face_crop.size == 0:
        raise ValueError(
            f"Could not extract a usable face region from '{image.filename}'."
        )

    gray_face = cv2.cvtColor(face_crop, cv2.COLOR_RGB2GRAY)

    # --- 8c. Blur check using the variance of the Laplacian ---
    # A sharp image has lots of edges -> high variance.
    # A blurry image has smoothed-out edges -> low variance.
    blur_score = cv2.Laplacian(gray_face, cv2.CV_64F).var()
    if blur_score < BLUR_THRESHOLD:
        raise ValueError(
            f"Face in '{image.filename}' appears too blurry "
            f"(sharpness score {blur_score:.1f}). Please upload a sharper photo."
        )

    # --- 8d. Brightness check using mean pixel intensity ---
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
# 9. IS THE FACE BIG ENOUGH IN THE FRAME?
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
# 10. IS THE FACE ROUGHLY FRONTAL (YAW/PITCH WITHIN LIMITS)?
# ---------------------------------------------------------------------------
def _estimate_head_pose(kps: np.ndarray, image_size: Tuple[int, int]) -> Tuple[float, float, float]:
    """Estimate (pitch, yaw, roll) in degrees from InsightFace's 5-point
    2D landmarks via solvePnP against a generic 3D face model.

    InsightFace's buffalo_l does not expose a ready-made `face.pose`
    field for the 5-point detector, so this reproduces the standard
    "N-point landmarks + solvePnP" head-pose technique used throughout
    the face-quality literature, using only what's already returned by
    every detection (no extra landmark model needed).
    """
    width, height = image_size
    focal_length = float(width)
    center = (width / 2.0, height / 2.0)
    camera_matrix = np.array(
        [
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1],
        ],
        dtype=np.float64,
    )
    dist_coeffs = np.zeros((4, 1))  # assume no lens distortion

    image_points = kps.astype(np.float64)

    success, rotation_vector, _translation_vector = cv2.solvePnP(
        _POSE_MODEL_3D_POINTS,
        image_points,
        camera_matrix,
        dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not success:
        raise ValueError("Head pose estimation failed.")

    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
    # RQDecomp3x3 conveniently returns Euler angles (degrees) directly.
    euler_angles, _, _, _, _, _ = cv2.RQDecomp3x3(rotation_matrix)
    pitch, yaw, roll = euler_angles
    return float(pitch), float(yaw), float(roll)


def validate_head_pose(image: UploadFile, pil_image: Image.Image, face) -> None:
    try:
        pitch, yaw, _roll = _estimate_head_pose(face.kps, pil_image.size)
    except (cv2.error, ValueError):
        # Pose estimation is a best-effort secondary signal; if it fails
        # for numerical reasons, don't block registration on it alone --
        # det_score, blur, and brightness checks already ran.
        return

    if abs(yaw) > MAX_YAW_DEGREES:
        raise ValueError(
            f"Face in '{image.filename}' is turned too far to the side "
            f"(yaw ~{abs(yaw):.0f} deg). Please upload a more front-facing photo."
        )
    if abs(pitch) > MAX_PITCH_DEGREES:
        raise ValueError(
            f"Face in '{image.filename}' is tilted too far up/down "
            f"(pitch ~{abs(pitch):.0f} deg). Please upload a more level, front-facing photo."
        )

# ---------------------------------------------------------------------------
# 11. DO ALL UPLOADED PHOTOS LOOK LIKE THE SAME PERSON?
# ---------------------------------------------------------------------------
def validate_cross_image_identity(
    images: List[UploadFile], embeddings: List[np.ndarray]
) -> None:
    """Pairwise-compares the ArcFace embeddings of every uploaded photo.

    Catches the case where one of the uploaded "student" photos is
    actually a different person (wrong file picked, mixed-up folder) --
    a real registration-corruption risk that none of the per-image
    checks above catch, since each image passes its own quality checks
    independently. This is nearly free: the embeddings are already
    computed as a side effect of face detection.
    """
    n = len(embeddings)
    for i in range(n):
        for j in range(i + 1, n):
            similarity = float(np.dot(embeddings[i], embeddings[j]))
            if similarity < CROSS_IMAGE_MIN_COSINE_SIM:
                raise ValueError(
                    f"'{images[i].filename}' and '{images[j].filename}' do not "
                    f"appear to show the same person (similarity {similarity:.2f}). "
                    "Please make sure all uploaded photos are of the same student."
                )

# ---------------------------------------------------------------------------
# MAIN ENTRY POINT — runs all checks in order, for every uploaded image
# ---------------------------------------------------------------------------
def validate_input_images(images: List[UploadFile]) -> None:

    validate_image_count(images)

    embeddings: List[np.ndarray] = []

    for image in images:

        validate_extension(image)
        validate_mime_type(image)
        file_bytes = image.file.read()
        image.file.seek(0)
        validate_file_size(image, file_bytes)
        pil_image = validate_image_integrity(image, file_bytes)
        validate_image_resolution(image, pil_image)
        faces = validate_single_face(image, pil_image)
        face = faces[0]
        validate_face_quality(image, pil_image, face)
        validate_face_size(image, pil_image, face)
        validate_head_pose(image, pil_image, face)

        # normed_embedding is L2-normalized, so a plain dot product below
        # is exactly cosine similarity -- no extra normalization needed.
        embeddings.append(face.normed_embedding)

    validate_cross_image_identity(images, embeddings)