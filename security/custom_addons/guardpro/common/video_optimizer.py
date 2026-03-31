# -*- coding: utf-8 -*-
"""Video optimization utility for uploaded videos."""

import base64
import logging
import os
import shutil
import subprocess
import tempfile

_logger = logging.getLogger(__name__)


class VideoOptimizer:
    """Utility class for compressing uploaded videos."""

    # Compression settings tuned for incident evidence uploads.
    TARGET_VIDEO_BITRATE = "1200k"
    TARGET_AUDIO_BITRATE = "96k"
    CRF = "28"
    PRESET = "veryfast"
    MAX_SIZE_BYTES = 25 * 1024 * 1024  # Skip compression for smaller files.

    @classmethod
    def _ffmpeg_available(cls):
        """Check if ffmpeg exists on server."""
        return shutil.which("ffmpeg") is not None

    @classmethod
    def optimize_video(cls, video_data, filename=None):
        """
        Compress video content and return base64 bytes.

        Args:
            video_data: base64 string/bytes or raw bytes
            filename: original filename (optional)

        Returns:
            tuple(optimized_base64_bytes, optimized_bool)
        """
        if not video_data:
            return video_data, False

        try:
            if isinstance(video_data, str):
                video_bytes = base64.b64decode(video_data)
            else:
                video_bytes = video_data
                # Handle already-base64 bytes payloads from some code paths.
                try:
                    decoded = base64.b64decode(video_data, validate=True)
                    if decoded:
                        video_bytes = decoded
                except Exception:
                    pass

            original_size = len(video_bytes)
            if original_size <= cls.MAX_SIZE_BYTES:
                return base64.b64encode(video_bytes), False

            if not cls._ffmpeg_available():
                _logger.warning("ffmpeg not available, skipping video compression for %s", filename or "upload")
                return base64.b64encode(video_bytes), False

            with tempfile.NamedTemporaryFile(delete=False, suffix=".input") as source:
                source.write(video_bytes)
                source_path = source.name
            output_path = source_path + ".mp4"

            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                source_path,
                "-c:v",
                "libx264",
                "-preset",
                cls.PRESET,
                "-crf",
                cls.CRF,
                "-b:v",
                cls.TARGET_VIDEO_BITRATE,
                "-maxrate",
                cls.TARGET_VIDEO_BITRATE,
                "-bufsize",
                "2400k",
                "-c:a",
                "aac",
                "-b:a",
                cls.TARGET_AUDIO_BITRATE,
                "-movflags",
                "+faststart",
                output_path,
            ]

            process = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=180,
            )

            if process.returncode != 0 or not os.path.exists(output_path):
                _logger.warning(
                    "Video compression failed for %s: %s",
                    filename or "upload",
                    process.stderr.decode("utf-8", errors="ignore")[:300],
                )
                return base64.b64encode(video_bytes), False

            with open(output_path, "rb") as output_file:
                optimized_bytes = output_file.read()

            if len(optimized_bytes) >= original_size:
                return base64.b64encode(video_bytes), False

            reduction = (1 - (len(optimized_bytes) / float(original_size))) * 100
            _logger.info(
                "Video optimized for %s: %d KB -> %d KB (%.1f%% reduction)",
                filename or "upload",
                original_size // 1024,
                len(optimized_bytes) // 1024,
                reduction,
            )
            return base64.b64encode(optimized_bytes), True

        except Exception as exc:
            _logger.error("Error compressing video %s: %s", filename or "upload", str(exc))
            if isinstance(video_data, str):
                return video_data, False
            return base64.b64encode(video_data), False
        finally:
            for path in (locals().get("source_path"), locals().get("output_path")):
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception:
                        pass
