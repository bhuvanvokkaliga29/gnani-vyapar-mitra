"""Low-level HTTP Client for Razorpay REST API with Timeout Protection."""

import httpx
from typing import Optional, Dict, Any
from apps.api.core.config import settings
from services.razorpay.errors import (
    RazorpayError,
    RazorpayTimeoutError,
    RazorpayNetworkError,
    RazorpayAuthenticationError,
    RazorpayBadRequestError,
    RazorpayNotFoundError
)


class RazorpayClient:
    """Asynchronous HTTP Client for interacting with Razorpay REST API."""

    DEFAULT_BASE_URL = "https://api.razorpay.com/v1"
    DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[httpx.Timeout] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ):
        self.key_id = key_id or settings.RAZORPAY_KEY_ID
        self.key_secret = key_secret or settings.RAZORPAY_KEY_SECRET
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._external_client = http_client

    async def request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute an authenticated HTTP request to Razorpay with structured error handling."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        auth = (self.key_id, self.key_secret)

        async def _execute(client: httpx.AsyncClient):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json_data,
                    params=params,
                    auth=auth,
                    timeout=self.timeout
                )
            except (httpx.TimeoutException, TimeoutError) as exc:
                raise RazorpayTimeoutError(
                    f"Request to Razorpay timed out on {method} {path}: {str(exc)}"
                ) from exc
            except (httpx.NetworkError, httpx.ConnectError) as exc:
                raise RazorpayNetworkError(
                    f"Network connection failed reaching Razorpay on {method} {path}: {str(exc)}"
                ) from exc

            # Process HTTP response status
            if response.status_code == 401:
                raise RazorpayAuthenticationError(
                    "Invalid Razorpay API credentials.",
                    status_code=401,
                    details=response.json() if response.content else {}
                )
            elif response.status_code == 400:
                raise RazorpayBadRequestError(
                    f"Bad Request to Razorpay: {response.text}",
                    status_code=400,
                    details=response.json() if response.content else {}
                )
            elif response.status_code == 404:
                raise RazorpayNotFoundError(
                    f"Resource not found on Razorpay: {path}",
                    status_code=404,
                    details=response.json() if response.content else {}
                )
            elif response.is_error:
                raise RazorpayError(
                    f"Razorpay API returned error status {response.status_code}: {response.text}",
                    status_code=response.status_code,
                    details=response.json() if response.content else {}
                )

            return response.json()

        if self._external_client:
            return await _execute(self._external_client)
        else:
            async with httpx.AsyncClient() as client:
                return await _execute(client)
