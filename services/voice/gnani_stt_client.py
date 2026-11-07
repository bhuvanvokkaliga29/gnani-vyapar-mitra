"""Gnani Prisma Speech-to-Text (STT / ASR) Client.

Calls Gnani.ai's official Prisma API (v3.0) via REST multipart/form-data:
Endpoint: POST https://api.vachana.ai/stt/v3
Headers: X-API-Key-ID: <GNANI_API_KEY>
"""

import time
import subprocess
from typing import Optional, Dict, Any
import httpx
import structlog
from apps.api.core.config import settings

logger = structlog.get_logger()

DEFAULT_TIMEOUT = 8.0
MAX_AUDIO_BYTES = 15 * 1024 * 1024  # 15 MB
SUPPORTED_FORMATS = {"codemix", "transcribe", "verbatim", "transliterate"}

_SHARED_STT_CLIENT: Optional[httpx.AsyncClient] = None

def get_shared_stt_client() -> httpx.AsyncClient:
    global _SHARED_STT_CLIENT
    if _SHARED_STT_CLIENT is None or _SHARED_STT_CLIENT.is_closed:
        _SHARED_STT_CLIENT = httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=60.0)
        )
    return _SHARED_STT_CLIENT
LANGUAGE_MAP = {
    "kn": "kn-IN",
    "hi": "hi-IN",
    "en": "en-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "gu": "gu-IN",
    "mr": "mr-IN",
    "bn": "bn-IN",
    "pa": "pa-IN",
    "ml": "ml-IN",
    "as": "as-IN",
    "indic-auto": "indic-auto"
}


def normalize_language_code(code: Optional[str]) -> str:
    """Normalize language code to Gnani Prisma supported codes:
    as-IN, bn-IN, en-IN, gu-IN, hi-IN, indic-auto, kn-IN, ml-IN, mr-IN, pa-IN, ta-IN, te-IN.
    """
    if not code:
        return "indic-auto"
    cleaned = code.strip().lower()
    mapping = {
        "kn": "kn-IN", "kn-in": "kn-IN",
        "hi": "hi-IN", "hi-in": "hi-IN",
        "en": "en-IN", "en-in": "en-IN",
        "ta": "ta-IN", "ta-in": "ta-IN",
        "te": "te-IN", "te-in": "te-IN",
        "gu": "gu-IN", "gu-in": "gu-IN",
        "mr": "mr-IN", "mr-in": "mr-IN",
        "bn": "bn-IN", "bn-in": "bn-IN",
        "pa": "pa-IN", "pa-in": "pa-IN",
        "ml": "ml-IN", "ml-in": "ml-IN",
        "as": "as-IN", "as-in": "as-IN",
        "indic-auto": "indic-auto"
    }
    return mapping.get(cleaned, "indic-auto")


def normalize_format(format_type: Optional[str]) -> Optional[str]:
    """Normalize format parameter to Gnani Prisma supported values:
    'verbatim', 'transcribe', 'codemix', 'transliterate', or None (omitted).
    """
    if format_type is None:
        return None
    cleaned = str(format_type).strip().lower().replace("-", "").replace("_", "")
    if cleaned in ("codemix", "codemixed", "kanglish"):
        return "codemix"
    if cleaned in ("transcribe", "transcription"):
        return "transcribe"
    if cleaned in ("verbatim",):
        return "verbatim"
    if cleaned in ("transliterate", "transliteration"):
        return "transliterate"
    if cleaned in ("omit", "none", "null", ""):
        return None
    # Default to codemix for Indic regional & mixed conversations
    return "codemix"


def transcode_to_wav(audio_bytes: bytes) -> bytes:
    """Transcode browser audio (WebM/Opus) to standard 16kHz mono WAV using ffmpeg."""
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", "pipe:0", "-f", "wav", "-ar", "16000", "-ac", "1", "pipe:1"],
            input=audio_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5.0
        )
        if proc.returncode == 0 and len(proc.stdout) > 44:
            b = bytearray(proc.stdout)
            n = len(b)
            # Patch RIFF chunk size (bytes 4-7) for streaming pipe output
            b[4:8] = (n - 8).to_bytes(4, "little")
            # Patch data chunk size
            data_idx = b.find(b"data")
            if data_idx != -1:
                b[data_idx + 4 : data_idx + 8] = (n - data_idx - 8).to_bytes(4, "little")
            return bytes(b)
        else:
            logger.warning("ffmpeg_transcode_non_zero", returncode=proc.returncode, stderr=proc.stderr[:200].decode("utf-8", errors="ignore"))
    except Exception as exc:
        logger.warning("ffmpeg_transcode_exception", error=str(exc))
    return audio_bytes


class GnaniSTTClient:
    """Production client for Gnani Prisma ASR."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        default_lang: Optional[str] = None
    ):
        self.api_key = api_key or settings.effective_gnani_speech_key
        self.base_url = (base_url or settings.GNANI_SPEECH_BASE_URL or settings.GNANI_BASE_URL or "https://api.vachana.ai").rstrip("/")
        self.model = model or settings.GNANI_STT_MODEL or "prisma-v3.0"
        self.default_lang = default_lang or settings.GNANI_STT_DEFAULT_LANG or "indic-auto"

    @property
    def is_configured(self) -> bool:
        """Check if an API key is available and non-empty."""
        return bool(self.api_key and self.api_key.strip() and not self.api_key.startswith("mock_"))

    async def transcribe_audio_async(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        content_type: str = "audio/wav",
        language_code: Optional[str] = None,
        format_type: Optional[str] = "codemix"
    ) -> Dict[str, Any]:
        """Transcribe merchant microphone audio into structured text.
        
        Args:
            audio_bytes: Raw binary audio buffer.
            filename: Audio filename with extension (e.g., recorded.webm or audio.wav).
            content_type: MIME type (e.g., audio/webm, audio/wav, audio/mpeg).
            language_code: Target language (e.g., 'indic-auto', 'kn-IN', 'hi-IN', 'en-IN').
            format_type: Output style: 'codemix', 'transcribe', 'verbatim', 'transliterate', or None.
            
        Returns:
            Dict containing transcript, language_detected, latency, and status.
        """
        # 1. Validation
        if not audio_bytes or len(audio_bytes) == 0:
            return {
                "success": False,
                "error": "Audio file is empty",
                "transcript": ""
            }

        if len(audio_bytes) > MAX_AUDIO_BYTES:
            return {
                "success": False,
                "error": f"Audio file exceeds maximum size limit of {MAX_AUDIO_BYTES // (1024 * 1024)}MB",
                "transcript": ""
            }

        # 2. Mock mode execution (if enabled in development)
        if settings.GNANI_USE_LOCAL_MOCK:
            logger.info("gnani_stt_local_mock_executed", audio_len=len(audio_bytes))
            return {
                "success": True,
                "transcript": "ಇವತ್ತಿನ ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?",
                "detected_language_code": "kn-IN",
                "confidence": 0.95,
                "model": "prisma-v3.0-mock",
                "latency_seconds": 0.05,
                "is_mock": True
            }

        # 3. Guard against unconfigured API key
        if not self.is_configured:
            return {
                "success": False,
                "error": "GNANI_API_KEY is not configured on the backend.",
                "transcript": ""
            }

        # 4. Transcode WebM / unsupported browser audio to standard WAV if needed
        is_webm = (
            "webm" in content_type.lower()
            or filename.lower().endswith(".webm")
            or audio_bytes.startswith(b"\x1a\x45\xdf\xa3")
        )
        if is_webm:
            logger.info("transcoding_browser_webm_to_wav", original_size=len(audio_bytes))
            audio_bytes = transcode_to_wav(audio_bytes)
            filename = "audio.wav"
            content_type = "audio/wav"

        # 5. Normalize Format Parameter
        norm_format = normalize_format(format_type)

        # 6. Live API Call
        url = f"{self.base_url}/stt/v3"
        headers = {
            "X-API-Key-ID": self.api_key
        }

        lang = normalize_language_code(language_code or self.default_lang)
        data: Dict[str, Any] = {
            "model": self.model,
            "language_code": lang,
            "topic": "retail commerce, merchant sales, inventory analytics, Vastram apparel",
            "keyterms": '["sales", "profit", "stock", "orders", "revenue", "Vastram", "WhatsApp", "Amazon", "Flipkart", "discount", "margin", "product", "bundle", "linen shirt", "today", "yesterday", "performance", "reorder"]'
        }
        if norm_format is not None:
            data["format"] = norm_format

        clean_content_type = content_type.split(";")[0].strip() if content_type else "audio/wav"
        files = {
            "audio_file": (filename, audio_bytes, clean_content_type)
        }

        t0 = time.perf_counter()
        try:
            client = get_shared_stt_client()
            res = await client.post(url, headers=headers, data=data, files=files)

            latency = round(time.perf_counter() - t0, 3)

            if res.status_code == 200:
                body = res.json()
                transcript = body.get("transcript", "").strip()
                detected_lang = body.get("detected_language_code") or lang

                logger.info(
                    "gnani_stt_transcription_success",
                    transcript_len=len(transcript),
                    detected_lang=detected_lang,
                    latency=latency
                )

                return {
                    "success": True,
                    "transcript": transcript,
                    "detected_language_code": detected_lang,
                    "confidence": body.get("confidence", 0.95),
                    "model": self.model,
                    "latency_seconds": latency,
                    "request_id": body.get("request_id"),
                    "is_mock": False
                }
            else:
                err_text = res.text
                err_msg = f"Gnani STT API returned status {res.status_code}"
                try:
                    err_json = res.json()
                    if isinstance(err_json, dict):
                        err_detail = err_json.get("error", {})
                        if isinstance(err_detail, dict) and "message" in err_detail:
                            err_msg = f"{err_detail.get('type', 'ERROR')}: {err_detail['message']}"
                        elif "message" in err_json:
                            err_msg = err_json["message"]
                except Exception:
                    err_msg = f"{err_msg}: {err_text[:200]}"

                logger.error("gnani_stt_api_error", status_code=res.status_code, error=err_msg)
                return {
                    "success": False,
                    "error": err_msg,
                    "transcript": ""
                }

        except httpx.TimeoutException:
            logger.warning("gnani_stt_timeout", timeout=DEFAULT_TIMEOUT)
            return {
                "success": False,
                "error": f"Gnani STT request timed out after {DEFAULT_TIMEOUT}s",
                "transcript": ""
            }
        except Exception as exc:
            logger.error("gnani_stt_exception", error=str(exc))
            return {
                "success": False,
                "error": f"Gnani STT network or connection error: {str(exc)}",
                "transcript": ""
            }

