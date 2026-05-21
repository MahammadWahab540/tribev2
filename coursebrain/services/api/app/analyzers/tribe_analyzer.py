from typing import List, Dict, Any, Optional
import numpy as np


class TribeAnalyzer:
    """
    Analyze video using TribeV2 neuro-signal predictions.
    
    IMPORTANT: TribeV2 is licensed under CC-BY-NC-4.0 (non-commercial use only).
    This analyzer gracefully handles cases where TribeV2 is unavailable.
    """

    def __init__(self, cache_folder: str = "./cache", device: str = "auto"):
        self.cache_folder = cache_folder
        self.device = device
        self.model = None
        self._load_error = None

    def load_model(self) -> bool:
        """
        Load TribeV2 model lazily.
        Returns True if successful, False otherwise.
        """
        if self.model is not None:
            return True

        if self._load_error is not None:
            return False

        try:
            from tribev2 import TribeModel

            self.model = TribeModel.from_pretrained(
                "facebook/tribev2",
                cache_folder=self.cache_folder,
                device=self.device,
            )
            return True
        except ImportError as e:
            self._load_error = f"TribeV2 not installed: {str(e)}"
            return False
        except Exception as e:
            self._load_error = f"Failed to load TribeV2: {str(e)}"
            return False

    def analyze_video(self, video_path: str) -> Dict[str, Any]:
        """
        Analyze video using TribeV2.
        Returns features aligned with timestamps.
        
        Gracefully falls back if TribeV2 is unavailable.
        """
        result = {
            "available": False,
            "features": [],
            "error": None,
        }

        if not self.load_model():
            result["error"] = self._load_error
            return result

        try:
            # Get events dataframe from video
            events = self.model.get_events_dataframe(video_path=video_path)

            # Predict brain responses
            preds, segments = self.model.predict(events=events)

            # Compute features
            features = self._compute_tribe_features(preds, segments)

            result["available"] = True
            result["features"] = features
            result["error"] = None

        except Exception as e:
            result["available"] = False
            result["features"] = []
            result["error"] = str(e)

        return result

    def _compute_tribe_features(
        self, preds: np.ndarray, segments: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Compute product-friendly features from TribeV2 predictions.
        
        Features:
        - activation_energy: mean absolute z-scored activation across vertices
        - signal_variation: cosine distance between adjacent prediction vectors
        """
        if preds is None or len(preds) == 0:
            return []

        # Z-score predictions across timesteps
        # preds shape: n_timesteps x n_vertices
        mean = np.mean(preds, axis=0, keepdims=True)
        std = np.std(preds, axis=0, keepdims=True) + 1e-8
        z_preds = (preds - mean) / std

        n_timesteps = z_preds.shape[0]

        features = []
        for t in range(n_timesteps):
            # Activation energy: mean absolute z-score across vertices
            activation_energy = float(np.mean(np.abs(z_preds[t])))

            # Signal variation: cosine distance from previous timestep
            signal_variation = 0.0
            if t > 0:
                # Cosine distance = 1 - cosine_similarity
                dot_product = np.dot(z_preds[t], z_preds[t - 1])
                norm_t = np.linalg.norm(z_preds[t])
                norm_prev = np.linalg.norm(z_preds[t - 1])
                if norm_t > 0 and norm_prev > 0:
                    cosine_sim = dot_product / (norm_t * norm_prev)
                    signal_variation = float(1 - cosine_sim)
                else:
                    signal_variation = 0.0

            # Get timestamp from segment
            start_sec = 0.0
            end_sec = 0.0
            if t < len(segments):
                seg = segments[t]
                if hasattr(seg, "start"):
                    start_sec = float(seg.start)
                if hasattr(seg, "end"):
                    end_sec = float(seg.end)
                elif hasattr(seg, "duration"):
                    end_sec = start_sec + float(seg.duration)

            features.append(
                {
                    "timestep": t,
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                    "activation_energy": activation_energy,
                    "signal_variation": signal_variation,
                }
            )

        # Compute rolling statistics
        activation_energies = [f["activation_energy"] for f in features]
        signal_variations = [f["signal_variation"] for f in features]

        # Rolling standard deviation (window of ~30 seconds worth of timesteps)
        # Assuming ~10 timesteps per second, window size = 300
        window_size = min(300, len(activation_energies) // 4 + 1)

        for i, feature in enumerate(features):
            # Rolling variation
            start_idx = max(0, i - window_size)
            window_activations = activation_energies[start_idx : i + 1]
            rolling_std = float(np.std(window_activations)) if window_activations else 0.0
            feature["rolling_variation"] = rolling_std

        # Identify low/high variation windows
        if activation_energies:
            p20_activation = np.percentile(activation_energies, 20)
            p80_activation = np.percentile(activation_energies, 80)
            p80_variation = np.percentile(signal_variations, 80) if signal_variations else 0

            for feature in features:
                feature["is_low_variation"] = (
                    feature["rolling_variation"] < p20_activation * 0.5
                )
                feature["is_high_variation"] = (
                    feature["activation_energy"] > p80_activation
                    or feature["signal_variation"] > p80_variation
                )

        return features

    def compute_summary(self, features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute summary statistics from Tribe features."""
        if not features:
            return {
                "avg_activation_energy": 0.0,
                "low_variation_windows": 0,
                "high_variation_windows": 0,
            }

        activation_energies = [f["activation_energy"] for f in features]
        low_variation = sum(1 for f in features if f.get("is_low_variation", False))
        high_variation = sum(1 for f in features if f.get("is_high_variation", False))

        return {
            "avg_activation_energy": float(np.mean(activation_energies)),
            "low_variation_windows": low_variation,
            "high_variation_windows": high_variation,
        }

    def align_to_windows(
        self, features: List[Dict[str, Any]], windows: List[Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """
        Align Tribe features to analysis windows.
        Returns tribe metrics for each window.
        """
        if not features or not windows:
            return [{} for _ in windows]

        results = []
        for window in windows:
            # Find features that overlap with this window
            window_features = [
                f
                for f in features
                if f["start_sec"] < window["end_sec"]
                and f["end_sec"] > window["start_sec"]
            ]

            if window_features:
                avg_activation = np.mean(
                    [f["activation_energy"] for f in window_features]
                )
                avg_variation = np.mean(
                    [f["signal_variation"] for f in window_features]
                )
                low_var_count = sum(
                    1 for f in window_features if f.get("is_low_variation", False)
                )
                high_var_count = sum(
                    1 for f in window_features if f.get("is_high_variation", False)
                )

                results.append(
                    {
                        "tribe_activation_energy": float(avg_activation),
                        "tribe_signal_variation": float(avg_variation),
                        "low_variation_count": low_var_count,
                        "high_variation_count": high_var_count,
                    }
                )
            else:
                results.append(
                    {
                        "tribe_activation_energy": None,
                        "tribe_signal_variation": None,
                        "low_variation_count": 0,
                        "high_variation_count": 0,
                    }
                )

        return results
