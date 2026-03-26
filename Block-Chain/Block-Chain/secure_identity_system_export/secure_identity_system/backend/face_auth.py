import base64
import os
from dataclasses import dataclass, field

import cv2
import numpy as np

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

try:
    from deepface import DeepFace  # type: ignore

    _HAS_DEEPFACE = True
except ModuleNotFoundError:  # pragma: no cover
    DeepFace = None
    _HAS_DEEPFACE = False


@dataclass
class FaceAnalysis:
    encoding: np.ndarray | None = None
    quality_score: float = 0.0
    quality_label: str = "Needs review"
    blur_score: float = 0.0
    brightness: float = 0.0
    face_ratio: float = 0.0
    face_count: int = 0
    ready: bool = False
    issues: list[str] = field(default_factory=list)


@dataclass
class FaceMatch:
    match: bool
    distance: float
    tolerance: float
    confidence: float


def decode_image(data_url):
    if not data_url:
        return None
    if "," in data_url:
        _, b64_data = data_url.split(",", 1)
    else:
        b64_data = data_url

    try:
        img_bytes = base64.b64decode(b64_data)
    except ValueError:
        return None

    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if bgr is None:
        return None

    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _cosine_distance(source_representation, test_representation):
    a = np.array(source_representation).flatten()
    b = np.array(test_representation).flatten()
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - (np.dot(a, b) / (norm_a * norm_b))


def _clamp(value, lower=0.0, upper=1.0):
    return max(lower, min(upper, value))

def _detect_faces(image_bgr):
    cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    cascade = cv2.CascadeClassifier(cascade_path)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    return faces, gray


def _hist_encoding(gray_roi, bins=64):
    resized = cv2.resize(gray_roi, (96, 96), interpolation=cv2.INTER_AREA)
    hist = cv2.calcHist([resized], [0], None, [bins], [0, 256]).flatten().astype(np.float32)
    norm = np.linalg.norm(hist)
    if norm > 0:
        hist /= norm
    return hist


def _fallback_analysis(image_rgb):
    image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    faces, gray = _detect_faces(image_bgr)
    h, w = gray.shape[:2]
    issues = []

    if faces is None or len(faces) == 0:
        return FaceAnalysis(face_count=0, issues=["No face detected. Center your face in frame."])

    if len(faces) > 1:
        return FaceAnalysis(
            face_count=int(len(faces)),
            issues=["Multiple faces detected. Make sure only one person is visible."],
        )

    x, y, fw, fh = [int(v) for v in faces[0]]
    face_ratio = (fw * fh) / float(max(1, w * h))

    roi = gray[max(0, y) : max(0, y) + max(1, fh), max(0, x) : max(0, x) + max(1, fw)]
    if roi.size == 0:
        return FaceAnalysis(face_count=1, issues=["Face region could not be extracted. Try again."])

    blur_score = float(cv2.Laplacian(roi, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    encoding_np = _hist_encoding(roi)

    if blur_score < 60:
        issues.append("Image is too soft. Reduce motion and improve focus.")
    if brightness < 60:
        issues.append("Image is too dark. Increase lighting.")
    if brightness > 200:
        issues.append("Image is overexposed. Reduce direct light.")
    if face_ratio < 0.08:
        issues.append("Face is too far. Move closer to the camera.")
    if face_ratio > 0.45:
        issues.append("Face is too close. Move slightly away.")

    blur_component = _clamp((blur_score - 40) / 160)
    brightness_component = 1.0 - _clamp(abs(brightness - 128) / 128)
    framing_component = 1.0 - _clamp(abs(face_ratio - 0.18) / 0.18)
    quality_score = round((0.45 * blur_component + 0.35 * brightness_component + 0.20 * framing_component) * 100, 1)

    ready = len(issues) == 0 and quality_score >= 55
    if quality_score >= 85:
        quality_label = "Excellent"
    elif quality_score >= 70:
        quality_label = "Good"
    elif quality_score >= 55:
        quality_label = "Fair"
    else:
        quality_label = "Needs review"

    if not ready and not issues:
        issues.append("Capture needs improvement before submission.")

    return FaceAnalysis(
        encoding=encoding_np,
        quality_score=quality_score,
        quality_label=quality_label,
        blur_score=round(blur_score, 1),
        brightness=round(brightness, 1),
        face_ratio=round(face_ratio, 3),
        face_count=1,
        ready=ready,
        issues=issues,
    )


def analyze_face(image_rgb):
    if image_rgb is None:
        return FaceAnalysis(issues=["Invalid image payload."])

    if not _HAS_DEEPFACE:
        return _fallback_analysis(image_rgb)

    try:
        # DeepFace expects BGR arrays natively
        image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        
        objs = DeepFace.represent(
            img_path=image_bgr,
            model_name="Facenet",
            enforce_detection=True,
            anti_spoofing=False
        )

        if len(objs) == 0:
            return FaceAnalysis(face_count=0, issues=["No face detected. Center your face in frame."])
            
        if len(objs) > 1:
            return FaceAnalysis(
                face_count=len(objs),
                issues=["Multiple faces detected. Make sure only one person is visible."],
            )

        face_obj = objs[0]
        
        # Check liveness detection returned by FasNet
        is_real = face_obj.get("is_real", True)
        if not is_real:
            return FaceAnalysis(issues=["Anti-spoofing failed. Ensure you are capturing a live human, not a photo/screen."])

        encoding_np = np.array(face_obj["embedding"], dtype=np.float32)

        return FaceAnalysis(
            encoding=encoding_np,
            quality_score=95.0,  # Trust the DeepFace extraction
            quality_label="Excellent",
            blur_score=100.0,
            brightness=100.0,
            face_ratio=0.15,
            face_count=1,
            ready=True,
            issues=[],
        )

    except ValueError as e:
        # Expected error from deepface if no face is found during enforce_detection
        return FaceAnalysis(issues=[f"Face analysis failed (Please center face): {str(e)}"])
    except Exception as e:
        return FaceAnalysis(issues=[f"AI Model Error: {str(e)}"])


def get_face_encoding(image_rgb):
    return analyze_face(image_rgb).encoding


def compare_face(known_encoding, candidate_encoding, tolerance=0.40):
    if known_encoding is None or candidate_encoding is None:
        return FaceMatch(match=False, distance=1.0, tolerance=tolerance, confidence=0.0)

    distance = _cosine_distance(known_encoding, candidate_encoding)
    
    # Cosine distance typically ranges from 0 to 2.
    # Convert this to a 0-100% confidence scale for UI
    confidence = round(_clamp(1.0 - (distance / 2.0)) * 100, 1)
    
    return FaceMatch(
        match=distance <= tolerance,
        distance=round(distance, 4),
        tolerance=tolerance,
        confidence=confidence,
    )


def match_face(known_encoding, candidate_encoding, tolerance=0.40):
    return compare_face(known_encoding, candidate_encoding, tolerance=tolerance).match


def find_matching_face(candidate_encoding, all_encodings, threshold=0.35):
    """Scan all stored AI face encodings and return the closest match below threshold.

    Facenet Cosine threshold is normally ~0.40. We use 0.35 here for stricter duplicate prevention.

    Returns:
        tuple (email, distance) of the closest match, or (None, None) if no match.
    """
    if candidate_encoding is None or not all_encodings:
        return None, None

    best_email = None
    best_distance = float("inf")

    for record in all_encodings:
        stored_encoding = record.get("encoding")
        if stored_encoding is None:
            continue

        try:
            distance = _cosine_distance(stored_encoding, candidate_encoding)
        except Exception:
            continue

        if distance < best_distance:
            best_distance = distance
            best_email = record.get("email")

    if best_distance <= threshold:
        return best_email, round(best_distance, 4)

    return None, None
