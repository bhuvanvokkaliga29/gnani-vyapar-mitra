"""Gnani Timbre Text-to-Speech (TTS) Client.

Calls Gnani.ai's official Timbre API (v3.0) via REST:
Endpoint: POST https://api.vachana.ai/api/v1/tts/inference
Headers:
  X-API-Key-ID: <GNANI_API_KEY>
  Content-Type: application/json

Supported production voices on Timbre v3.0:
Lakshmi, Avinash, Shivani, Kalpana, Shubham, Prakash, Devansh, Yashraj, etc.
"""

import base64
import io
import time
import wave
from typing import Optional, Dict, Any, Tuple
import httpx
import structlog
from apps.api.core.config import settings

logger = structlog.get_logger()

DEFAULT_TIMEOUT = 8.0
MAX_TEXT_CHARS = 1000

_SHARED_TTS_CLIENT: Optional[httpx.AsyncClient] = None

def get_shared_tts_client() -> httpx.AsyncClient:
    global _SHARED_TTS_CLIENT
    if _SHARED_TTS_CLIENT is None or _SHARED_TTS_CLIENT.is_closed:
        _SHARED_TTS_CLIENT = httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50, keepalive_expiry=60.0)
        )
    return _SHARED_TTS_CLIENT


class GnaniTTSClient:
    """Production client for Gnani Timbre Speech Synthesis."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        default_voice: Optional[str] = None,
        default_lang: Optional[str] = None
    ):
        self.api_key = api_key or settings.effective_gnani_speech_key
        self.base_url = (base_url or settings.GNANI_SPEECH_BASE_URL or settings.GNANI_BASE_URL or "https://api.vachana.ai").rstrip("/")
        self.model = model or settings.GNANI_TTS_MODEL or "timbre-v3.0"
        self.default_voice = default_voice or settings.GNANI_TTS_DEFAULT_VOICE or "Lakshmi"
        self.default_lang = default_lang or settings.GNANI_TTS_DEFAULT_LANG or "kn"

    @property
    def is_configured(self) -> bool:
        """Check if an API key is available and non-empty."""
        return bool(self.api_key and self.api_key.strip() and not self.api_key.startswith("mock_"))

    @staticmethod
    def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 48000, channels: int = 1, sampwidth: int = 2) -> bytes:
        """Wrap raw linear PCM audio into a standard WAV container (RIFF/WAVE header)."""
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sampwidth)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        return wav_io.getvalue()

    async def synthesize_speech_async(
        self,
        text: str,
        voice: Optional[str] = None,
        language: Optional[str] = None,
        speed: float = 1.15
    ) -> Dict[str, Any]:
        """Synthesize natural Indian speech audio from merchant advisor text.
        
        Args:
            text: Text script to vocalize (concise 1-3 sentences recommended).
            voice: Voice persona (e.g. 'Lakshmi', 'Avinash', 'Shivani').
            language: Language code: 'kn', 'hi', 'en'.
            speed: Playback rate multiplier (default 1.15 natural brisk delivery, clamped to 0.85-1.15 for Timbre v3.0).
            
        Returns:
            Dict containing audio_bytes, audio_base64, content_type, latency, status.
        """
        import re
        clean_text = (text or "").strip()
        # Clean any XML/emotion tags or markdown characters to ensure steady, calm volume and pitch
        clean_text = re.sub(r'<[^>]+>', '', clean_text)
        clean_text = re.sub(r'[*_#`~]', '', clean_text).strip()

        if not clean_text:
            return {
                "success": False,
                "error": "Input text is empty",
                "audio_base64": None
            }

        if len(clean_text) > MAX_TEXT_CHARS:
            clean_text = clean_text[:MAX_TEXT_CHARS]

        selected_lang = language or self.default_lang or "en"
        selected_voice = voice or self.default_voice or "Lakshmi"
        if selected_lang.lower().startswith("en") and (not voice or voice == "Lakshmi"):
            selected_voice = "Lakshmi"

        # Clamped strictly within Timbre v3.0's allowed range [0.85, 1.15]; default 1.15 for brisk, natural human cadence
        safe_speed = round(max(0.85, min(1.15, float(speed if speed is not None else 1.15))), 2)

        # 1. Mock mode execution
        if settings.GNANI_USE_LOCAL_MOCK:
            logger.info("gnani_tts_local_mock_executed", text_len=len(clean_text))
            return {
                "success": True,
                "audio_bytes": b"",
                "audio_base64": None,
                "content_type": "audio/wav",
                "voice": selected_voice,
                "language": selected_lang,
                "latency_seconds": 0.05,
                "is_mock": True,
                "is_fallback": False
            }

        # 2. Guard against unconfigured API key -> fallback to edge-tts if needed
        if not self.is_configured:
            return await self._fallback_edge_tts(clean_text, selected_lang, "GNANI_API_KEY unconfigured")

        # 3. Live API Call to Gnani Timbre: Primary High-Speed SSE Stream with REST Fallback
        url_sse = f"{self.base_url}/api/v1/tts/sse"
        headers = {
            "X-API-Key-ID": self.api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "text": clean_text,
            "voice": selected_voice,
            "model": self.model or "timbre-v3.0",
            "language": selected_lang,
            "speed": safe_speed,
            "audio_config": {
                "encoding": "linear_pcm",
                "container": "wav",
                "sample_rate": 48000
            }
        }

        t0 = time.perf_counter()
        client = get_shared_tts_client()
        first_chunk_t: Optional[float] = None
        raw_chunks: List[bytes] = []

        try:
            # Step A: High-Speed Server-Sent Events (SSE) Stream
            async with client.stream("POST", url_sse, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT) as sse_res:
                if sse_res.status_code == 200:
                    import json
                    async for line in sse_res.aiter_lines():
                        if line.startswith("data:"):
                            try:
                                d = json.loads(line[5:].strip())
                                audio_str = d.get("audio")
                                if audio_str:
                                    if first_chunk_t is None:
                                        first_chunk_t = round(time.perf_counter() - t0, 3)
                                    raw_chunks.append(base64.b64decode(audio_str))
                            except Exception:
                                pass

                    if raw_chunks:
                        total_latency = round(time.perf_counter() - t0, 3)
                        full_audio = b"".join(raw_chunks)
                        if not full_audio.startswith(b"RIFF"):
                            audio_bytes = self._pcm_to_wav(full_audio, sample_rate=48000, channels=1)
                        else:
                            b = bytearray(full_audio)
                            n = len(b)
                            if n > 44:
                                b[4:8] = (n - 8).to_bytes(4, "little")
                                data_idx = b.find(b"data")
                                if data_idx != -1:
                                    b[data_idx + 4 : data_idx + 8] = (n - data_idx - 8).to_bytes(4, "little")
                                audio_bytes = bytes(b)
                            else:
                                audio_bytes = full_audio

                        content_type = "audio/wav"
                        b64 = base64.b64encode(audio_bytes).decode("ascii")

                        logger.info(
                            "gnani_tts_sse_stream_success",
                            voice=selected_voice,
                            language=selected_lang,
                            audio_size=len(audio_bytes),
                            first_chunk_latency=first_chunk_t or total_latency,
                            total_latency=total_latency
                        )

                        return {
                            "success": True,
                            "audio_bytes": audio_bytes,
                            "audio_base64": f"data:{content_type};base64,{b64}",
                            "content_type": content_type,
                            "voice": selected_voice,
                            "language": selected_lang,
                            "latency_seconds": total_latency,
                            "time_to_first_byte": first_chunk_t or total_latency,
                            "is_mock": False,
                            "is_fallback": False,
                            "engine": "sse_stream"
                        }
        except Exception as sse_exc:
            logger.info("gnani_tts_sse_stream_fallback_to_rest", error=str(sse_exc))

        # Step B: Synchronous REST Inference Fallback
        url_rest = f"{self.base_url}/api/v1/tts/inference"
        try:
            res = await client.post(url_rest, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)
            latency = round(time.perf_counter() - t0, 3)

            if res.status_code == 200:
                audio_bytes = res.content
                if not audio_bytes.startswith(b"RIFF"):
                    audio_bytes = self._pcm_to_wav(audio_bytes, sample_rate=48000, channels=1)
                else:
                    b = bytearray(audio_bytes)
                    n = len(b)
                    b[4:8] = (n - 8).to_bytes(4, "little")
                    data_idx = b.find(b"data")
                    if data_idx != -1:
                        b[data_idx + 4 : data_idx + 8] = (n - data_idx - 8).to_bytes(4, "little")
                    audio_bytes = bytes(b)

                content_type = "audio/wav"
                b64 = base64.b64encode(audio_bytes).decode("ascii")

                logger.info(
                    "gnani_tts_synthesis_success",
                    voice=selected_voice,
                    language=selected_lang,
                    audio_size=len(audio_bytes),
                    latency=latency
                )

                return {
                    "success": True,
                    "audio_bytes": audio_bytes,
                    "audio_base64": f"data:{content_type};base64,{b64}",
                    "content_type": content_type,
                    "voice": selected_voice,
                    "language": selected_lang,
                    "latency_seconds": latency,
                    "time_to_first_byte": latency,
                    "is_mock": False,
                    "is_fallback": False,
                    "engine": "rest_sync"
                }
            else:
                err_msg = res.text[:250]
                logger.warning("gnani_tts_api_failed_attempting_fallback", status=res.status_code, error=err_msg)
                return await self._fallback_edge_tts(clean_text, selected_lang, f"Gnani status {res.status_code}: {err_msg}")

        except httpx.TimeoutException:
            logger.warning("gnani_tts_timeout_attempting_fallback", timeout=DEFAULT_TIMEOUT)
            return await self._fallback_edge_tts(clean_text, selected_lang, f"Gnani TTS timeout after {DEFAULT_TIMEOUT}s")
        except Exception as exc:
            logger.warning("gnani_tts_exception_attempting_fallback", error=str(exc))
            return await self._fallback_edge_tts(clean_text, selected_lang, str(exc))

    async def _fallback_edge_tts(self, text: str, lang: str, reason: str) -> Dict[str, Any]:
        """Graceful local fallback using Edge TTS when Gnani API is unavailable."""
        logger.info("edge_tts_fallback_invoked", reason=reason, lang=lang)
        voice_map = {
            "kn": "kn-IN-GaganNeural",
            "hi": "hi-IN-MadhurNeural",
            "en": "en-IN-NeerjaExpressiveNeural"
        }
        edge_voice = voice_map.get(lang, "kn-IN-GaganNeural")

        try:
            import edge_tts
            import io

            comm = edge_tts.Communicate(text, edge_voice)
            audio_buffer = io.BytesIO()
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])

            audio_bytes = audio_buffer.getvalue()
            b64 = base64.b64encode(audio_bytes).decode("ascii")

            return {
                "success": True,
                "audio_bytes": audio_bytes,
                "audio_base64": f"data:audio/mp3;base64,{b64}",
                "content_type": "audio/mp3",
                "voice": f"{edge_voice} (Fallback)",
                "language": lang,
                "latency_seconds": 0.5,
                "is_mock": False,
                "is_fallback": True,
                "fallback_reason": reason
            }
        except Exception as fb_err:
            logger.error("edge_tts_fallback_failed", error=str(fb_err))
            return {
                "success": False,
                "error": f"Speech synthesis failed: {reason}. Fallback also failed: {str(fb_err)}",
                "audio_base64": None
            }

