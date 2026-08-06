import cv2
import numpy as np
from typing import List, Dict, Any
import os
from PIL import Image


class VisualAnalyzer:
    """Analyze visual content from video frames."""

    def __init__(self):
        pass

    def analyze_frames(self, frame_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Analyze a sequence of video frames.
        Returns metrics for each frame and overall statistics.
        """
        if not frame_paths:
            return []

        results = []
        prev_frame = None

        for i, frame_path in enumerate(frame_paths):
            # Load frame
            frame = cv2.imread(frame_path)
            if frame is None:
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Calculate frame difference (scene change detection)
            scene_change_score = 0.0
            if prev_frame is not None:
                scene_change_score = self._calculate_frame_difference(
                    prev_frame, frame_rgb
                )

            # Calculate text density using OCR
            ocr_result = self._perform_ocr(frame_rgb)
            text_density = self._calculate_text_density(ocr_result, frame.shape)

            # Calculate color variance (visual complexity)
            color_variance = self._calculate_color_variance(frame_rgb)

            # Detect faces (talking head vs slide)
            face_count = self._detect_faces(frame_rgb)

            results.append(
                {
                    "frame_index": i,
                    "frame_path": frame_path,
                    "scene_change_score": scene_change_score,
                    "text_density": text_density,
                    "color_variance": color_variance,
                    "face_count": face_count,
                    "is_likely_slide": text_density > 0.1 and face_count == 0,
                    "ocr_text": ocr_result.get("text", ""),
                    "ocr_word_count": len(ocr_result.get("words", [])),
                }
            )

            prev_frame = frame_rgb

        return results

    def _calculate_frame_difference(
        self, frame1: np.ndarray, frame2: np.ndarray
    ) -> float:
        """Calculate normalized difference between two frames."""
        # Convert to grayscale
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_RGB2GRAY)

        # Resize to same size if needed
        if gray1.shape != gray2.shape:
            gray2 = cv2.resize(gray2, (gray1.shape[1], gray1.shape[0]))

        # Calculate absolute difference
        diff = cv2.absdiff(gray1, gray2)

        # Normalize
        diff_mean = np.mean(diff) / 255.0

        return float(diff_mean)

    def _perform_ocr(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Perform OCR on frame to detect text.
        Uses EasyOCR if available, falls back to simple heuristic.
        """
        try:
            import easyocr

            reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            results = reader.readtext(frame)

            text = " ".join([r[1] for r in results])
            words = [r[1] for r in results]

            return {"text": text, "words": words, "boxes": [r[0] for r in results]}
        except ImportError:
            # Fallback: simple text density estimation based on edge detection
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 50, 150)

            # Estimate text regions (horizontal edges)
            horizontal_kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT, (40, 1)
            )
            detect_horizontal = cv2.morphologyEx(
                edges, cv2.MORPH_OPEN, horizontal_kernel, iterations=2
            )

            text_pixels = cv2.countNonZero(detect_horizontal)
            total_pixels = frame.shape[0] * frame.shape[1]

            return {
                "text": "",
                "words": [],
                "estimated_text_area_ratio": text_pixels / total_pixels
                if total_pixels > 0
                else 0,
            }
        except Exception:
            return {"text": "", "words": [], "error": "OCR failed"}

    def _calculate_text_density(
        self, ocr_result: Dict[str, Any], frame_shape: tuple
    ) -> float:
        """Calculate text density from OCR results."""
        if "boxes" in ocr_result and ocr_result["boxes"]:
            # Calculate total text area
            text_area = 0
            for box in ocr_result["boxes"]:
                # Box is [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                x_coords = [p[0] for p in box]
                y_coords = [p[1] for p in box]
                width = max(x_coords) - min(x_coords)
                height = max(y_coords) - min(y_coords)
                text_area += width * height

            frame_area = frame_shape[0] * frame_shape[1]
            return text_area / frame_area if frame_area > 0 else 0

        # Fallback to estimated ratio
        return ocr_result.get("estimated_text_area_ratio", 0)

    def _calculate_color_variance(self, frame: np.ndarray) -> float:
        """Calculate color variance as a measure of visual complexity."""
        # Convert to LAB color space
        lab = cv2.cvtColor(frame, cv2.COLOR_RGB2LAB)

        # Calculate standard deviation of each channel
        l_std = np.std(lab[:, :, 0])
        a_std = np.std(lab[:, :, 1])
        b_std = np.std(lab[:, :, 2])

        # Combined variance
        variance = (l_std + a_std + b_std) / 3

        # Normalize to 0-1 range (typical max is around 100)
        return min(variance / 100, 1.0)

    def _detect_faces(self, frame: np.ndarray) -> int:
        """Detect number of faces in frame."""
        try:
            # Use OpenCV's Haar cascade for face detection
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            face_cascade = cv2.CascadeClassifier(cascade_path)

            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            return len(faces)
        except Exception:
            return 0

    def compute_visual_metrics(
        self, frame_results: List[Dict[str, Any]], timestamps: List[float]
    ) -> Dict[str, Any]:
        """Compute aggregate visual metrics."""
        if not frame_results:
            return {}

        # Scene change rate
        scene_changes = [r["scene_change_score"] for r in frame_results]
        high_changes = sum(1 for s in scene_changes if s > 0.3)
        duration_minutes = (timestamps[-1] - timestamps[0]) / 60 if len(timestamps) > 1 else 1
        visual_change_rate = high_changes / duration_minutes if duration_minutes > 0 else 0

        # Average text density
        avg_text_density = (
            sum(r["text_density"] for r in frame_results) / len(frame_results)
        )

        # Visual stability (low variation = static slides)
        low_variation_frames = sum(1 for s in scene_changes if s < 0.1)
        visual_stability = low_variation_frames / len(frame_results)

        # Slide ratio
        slide_frames = sum(1 for r in frame_results if r["is_likely_slide"])
        slide_ratio = slide_frames / len(frame_results)

        return {
            "avg_text_density": avg_text_density,
            "visual_change_rate_per_min": visual_change_rate,
            "visual_stability": visual_stability,
            "slide_ratio": slide_ratio,
            "total_frames": len(frame_results),
        }
