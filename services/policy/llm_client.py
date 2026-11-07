"""Google Gemini LLM Client for Merchant Policy Agent.

Calls the official Gemini REST API with structured JSON output mode,
transforming natural language & catalog data into typed PolicyCandidate proposals.
Preserves the core invariant: THE LLM CAN PROPOSE. IT CANNOT SPEND.
"""

import os
import json
import time
import uuid
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
import structlog
import httpx

from domain.intent_schemas import BuyerIntent, ConfidenceLevel
from domain.commerce_schemas import MerchantCommerceContext, ProductResponse
from services.policy.schemas import (
    PolicyCandidate,
    StrategyType,
    CandidateValidationStatus,
    IncentiveProposal,
    PolicyEvidence
)
from services.policy.prompts import SYSTEM_PROMPT, format_policy_prompt

logger = structlog.get_logger()

GEMINI_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
DEFAULT_TIMEOUT_SECONDS = 3.5


class GeminiPolicyClient:
    """Client communicating with Google Gemini for candidate strategy generation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
        self.model_name = model_name or os.getenv("LLM_MODEL") or DEFAULT_GEMINI_MODEL
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        """Check if an API key is provided and non-empty."""
        return bool(self.api_key and self.api_key.strip() and not self.api_key.startswith("mock_"))

    def _build_request_payload(
        self,
        intent: BuyerIntent,
        context: MerchantCommerceContext,
        eligible_products: List[ProductResponse]
    ) -> Tuple[str, Dict[str, Any]]:
        url = GEMINI_API_URL_TEMPLATE.format(model=self.model_name, key=self.api_key)
        prompt_text = format_policy_prompt(intent, context, eligible_products)
        payload = {
            "system_instruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt_text}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
                "maxOutputTokens": 2048
            }
        }
        return url, payload

    async def propose_candidates_async(
        self,
        intent: BuyerIntent,
        context: MerchantCommerceContext,
        eligible_products: List[ProductResponse]
    ) -> Optional[List[PolicyCandidate]]:
        """Asynchronously call Gemini to generate candidate strategies."""
        if not self.is_configured:
            return None

        t0 = time.perf_counter()
        url, payload = self._build_request_payload(intent, context, eligible_products)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
            return self._handle_response(response, eligible_products, t0)
        except (httpx.TimeoutException, httpx.NetworkError) as net_err:
            logger.warn("gemini_async_network_or_timeout_fallback", error=str(net_err))
            return None
        except Exception as exc:
            logger.error("gemini_async_candidate_generation_failed", error=str(exc))
            return None

    def propose_candidates_sync(
        self,
        intent: BuyerIntent,
        context: MerchantCommerceContext,
        eligible_products: List[ProductResponse]
    ) -> Optional[List[PolicyCandidate]]:
        """Synchronously call Gemini to generate candidate strategies."""
        if not self.is_configured:
            return None

        t0 = time.perf_counter()
        url, payload = self._build_request_payload(intent, context, eligible_products)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
            return self._handle_response(response, eligible_products, t0)
        except (httpx.TimeoutException, httpx.NetworkError) as net_err:
            logger.warn("gemini_sync_network_or_timeout_fallback", error=str(net_err))
            return None
        except Exception as exc:
            logger.error("gemini_sync_candidate_generation_failed", error=str(exc))
            return None

    def _handle_response(
        self,
        response: httpx.Response,
        eligible_products: List[ProductResponse],
        t0: float
    ) -> Optional[List[PolicyCandidate]]:
        if response.status_code != 200:
            logger.warn("gemini_api_error_response", status_code=response.status_code, body=response.text[:300])
            return None

        data = response.json()
        candidates_text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        if not candidates_text:
            return None

        parsed_json = json.loads(candidates_text)
        raw_list = parsed_json.get("candidates", []) if isinstance(parsed_json, dict) else parsed_json

        if not isinstance(raw_list, list) or len(raw_list) == 0:
            return None

        policy_candidates: List[PolicyCandidate] = []
        for item in raw_list:
            cand = self._parse_candidate_dict(item, eligible_products)
            if cand:
                policy_candidates.append(cand)

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            "gemini_candidates_generated",
            count=len(policy_candidates),
            latency_ms=latency_ms,
            model=self.model_name
        )
        return policy_candidates if policy_candidates else None

    def _parse_candidate_dict(
        self,
        item: Dict[str, Any],
        eligible_products: List[ProductResponse]
    ) -> Optional[PolicyCandidate]:
        try:
            strat_raw = item.get("strategy_type", "SINGLE_PRODUCT")
            try:
                strat = StrategyType(strat_raw)
            except ValueError:
                strat = StrategyType.SINGLE_PRODUCT

            prod_ids = item.get("product_ids", [])
            if not isinstance(prod_ids, list):
                prod_ids = [str(prod_ids)] if prod_ids else []

            valid_ids = {p.id for p in eligible_products}
            filtered_prod_ids = [pid for pid in prod_ids if pid in valid_ids]

            if strat != StrategyType.NO_OFFER and not filtered_prod_ids:
                strat = StrategyType.NO_OFFER

            incentive = None
            inc_dict = item.get("incentive")
            if isinstance(inc_dict, dict) and inc_dict.get("incentive_type"):
                disc = inc_dict.get("discount_percent")
                incentive = IncentiveProposal(
                    incentive_type=str(inc_dict.get("incentive_type", "discount")),
                    discount_percent=Decimal(str(disc)) if disc is not None else None,
                    description=inc_dict.get("description")
                )

            evidence_list: List[PolicyEvidence] = []
            for ev in item.get("evidence", []):
                if isinstance(ev, dict) and ev.get("evidence_type") and ev.get("field") and ev.get("description"):
                    try:
                        evidence_list.append(PolicyEvidence(
                            evidence_type=ev["evidence_type"],
                            field=ev["field"],
                            description=ev["description"]
                        ))
                    except Exception:
                        pass

            return PolicyCandidate(
                candidate_id=f"cand_llm_{uuid.uuid4().hex[:8]}",
                strategy_type=strat,
                product_ids=filtered_prod_ids,
                bundle_components=item.get("bundle_components", []),
                incentive=incentive,
                positioning=item.get("positioning"),
                rationale=str(item.get("rationale", "LLM-proposed commercial candidate strategy.")),
                confidence=ConfidenceLevel.HIGH,
                evidence=evidence_list,
                validation_status=CandidateValidationStatus.REJECTED
            )
        except Exception as parse_err:
            logger.warn("gemini_candidate_parse_error", error=str(parse_err), item=item)
            return None
