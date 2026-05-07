import os

# DeepFace uses legacy tf.keras paths with TensorFlow 2.16+.
# Setting this before importing DeepFace makes TensorFlow use the tf-keras package.
os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")

import base64
import binascii
import re
from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename

DATA_URL_RE = re.compile(r"^data:image/(?P<ext>png|jpg|jpeg);base64$", re.IGNORECASE)


class FaceAuthError(Exception):
    """Raised when face enrollment or verification fails."""


def save_face_data_url(data_url, target_dir, prefix="face"):
    """Save a browser canvas data URL to disk and return the file path."""
    if not data_url or "," not in data_url:
        raise FaceAuthError("No captured face image was submitted.")

    header, encoded = data_url.split(",", 1)
    match = DATA_URL_RE.match(header)
    if not match:
        raise FaceAuthError("Unsupported image format. Capture a PNG or JPG image.")

    try:
        raw = base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise FaceAuthError("The captured image is not valid base64 data.") from exc

    if len(raw) > 8 * 1024 * 1024:
        raise FaceAuthError("The captured image is too large.")

    ext = match.group("ext").lower().replace("jpeg", "jpg")
    safe_prefix = secure_filename(prefix) or "face"
    target_path = Path(target_dir) / f"{safe_prefix}-{uuid4().hex}.{ext}"
    target_path.write_bytes(raw)
    return str(target_path)


def assert_single_face(image_path, detector_backend="opencv"):
    """Ensure DeepFace can detect exactly one face in an image."""
    try:
        from deepface import DeepFace

        faces = DeepFace.extract_faces(
            img_path=image_path,
            detector_backend=detector_backend,
            enforce_detection=True,
            align=True,
        )
    except Exception as exc:
        raise FaceAuthError("DeepFace could not detect a face. Try better lighting and face the camera.") from exc

    if len(faces) != 1:
        raise FaceAuthError("Please capture exactly one face in the frame.")


def verify_face(known_image_path, candidate_image_path, *, model_name, detector_backend, distance_metric):
    """Return (verified, details) for a known enrolled image and login image."""
    if not known_image_path or not Path(known_image_path).exists():
        raise FaceAuthError("This account does not have an enrolled face image.")

    try:
        from deepface import DeepFace

        result = DeepFace.verify(
            img1_path=known_image_path,
            img2_path=candidate_image_path,
            model_name=model_name,
            detector_backend=detector_backend,
            distance_metric=distance_metric,
            enforce_detection=True,
            align=True,
        )
    except Exception as exc:
        raise FaceAuthError("Face verification failed. Make sure your face is clear and centered.") from exc

    return bool(result.get("verified")), result


def remove_file_safely(path):
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass
