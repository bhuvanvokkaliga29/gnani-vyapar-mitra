"""API Router for Model Context Protocol (MCP) External AI Buyer Interface.

Contract: mcp-commerce/v1
Endpoints:
- POST /api/v1/mcp: Standard JSON-RPC 2.0 dispatcher for tools/list, tools/call, resources/list, resources/read
- GET  /api/v1/mcp/tools: Discovery of registered MCP tools
- POST /api/v1/mcp/tools/{tool_name}: Direct HTTP invocation for web AI buyers
- GET  /api/v1/mcp/resources: Discovery of read-only resources
- GET  /api/v1/mcp/sse: Server-Sent Events stream for asynchronous agent connections
"""

import json
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Request, Header, HTTPException, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from apps.api.core.database import get_db
from services.mcp.server import mcp_server
from services.mcp.auth import authenticate_buyer, set_current_auth_context
from services.mcp.errors import (
    McpError,
    McpTenantMismatchError,
    McpInsufficientCapabilityError,
    McpAuthenticationError,
    McpInvalidOfferError,
    McpOfferExpiredError,
    McpProductNotFoundError,
    McpOrderNotFoundError,
)
from services.mcp.tools.catalog import search_catalog, get_product
from services.mcp.tools.intent import evaluate_buyer_intent
from services.mcp.tools.offers import get_offer
from services.mcp.tools.checkout import request_checkout
from services.mcp.tools.orders import get_order_status

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/mcp", tags=["Model Context Protocol (MCP)"])


def _extract_and_authenticate(request: Request, authorization: Optional[str] = None):
    """Authenticate incoming HTTP request and set active ContextVar."""
    client_meta = {
        "client_name": request.headers.get("X-Client-Name", "http_ai_buyer"),
        "client_version": request.headers.get("X-Client-Version", "1.0.0"),
        "buyer_agent_id": request.headers.get("X-Buyer-Agent-Id", "agent_external_buyer_v1")
    }
    identity = authenticate_buyer(auth_header=authorization, client_metadata=client_meta)
    set_current_auth_context(identity)
    return identity


# -----------------------------------------------------------------------------
# 1. JSON-RPC 2.0 PROTOCOL ENDPOINT (Spec: MCP 2026)
# -----------------------------------------------------------------------------

@router.post("", summary="Model Context Protocol JSON-RPC 2.0 Dispatcher")
async def mcp_jsonrpc_dispatcher(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db)
):
    """Handle standard JSON-RPC 2.0 requests from MCP-compliant AI buyer clients."""
    _extract_and_authenticate(request, authorization)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        )

    req_id = body.get("id")
    method = body.get("method")
    params = body.get("params", {})

    logger.info("mcp_jsonrpc_request", method=method, req_id=req_id)

    try:
        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        elif method == "tools/list":
            tools = await mcp_server.list_tools()
            tool_list = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": getattr(t, "parameters", {}) or {}
                }
                for t in tools
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tool_list}}

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})

            result = await _dispatch_tool(tool_name, args, db)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, default=str)}],
                    "structured_content": result,
                    "isError": False
                }
            }

        elif method == "resources/list":
            resources = await mcp_server.list_resources()
            res_list = [
                {
                    "uri": r.uri,
                    "name": r.name,
                    "description": r.description,
                    "mimeType": r.mime_type
                }
                for r in resources
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": res_list}}

        elif method == "resources/read":
            uri = params.get("uri")
            contents = await mcp_server.read_resource(uri)
            content_list = [
                {"uri": uri, "mimeType": c.mime_type, "text": c.content}
                for c in contents
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"contents": content_list}}

        else:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method '{method}' not found"}
                }
            )

    except McpError as exc:
        logger.warn("mcp_domain_error", error_type=exc.error_type, message=exc.message)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "data": {"error_type": exc.error_type, **exc.details}
            }
        }
    except Exception as exc:
        logger.error("mcp_internal_server_error", error=str(exc))
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32603, "message": f"Internal MCP Error: {str(exc)}"}
        }


# -----------------------------------------------------------------------------
# 2. DIRECT REST CONVENIENCE ROUTES
# -----------------------------------------------------------------------------

@router.get("/tools", summary="List Registered MCP Tools")
async def list_tools_http():
    """Discover all registered MCP tools and their descriptions."""
    tools = await mcp_server.list_tools()
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "parameters": getattr(t, "parameters", {}) or {}
            }
            for t in tools
        ]
    }


@router.post("/tools/{tool_name}", summary="Direct HTTP Execution of an MCP Tool")
async def execute_tool_http(
    tool_name: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db)
):
    """Execute a single MCP tool via direct HTTP POST."""
    _extract_and_authenticate(request, authorization)
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}

    try:
        result = await _dispatch_tool(tool_name, body, db)
        return {"tool": tool_name, "success": True, "result": result}
    except McpError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_type": exc.error_type, "message": exc.message, "details": exc.details}
        )
    except Exception as exc:
        logger.error("mcp_http_tool_error", tool=tool_name, error=str(exc))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/resources", summary="List Registered MCP Resources")
async def list_resources_http():
    """Discover read-only MCP resources."""
    resources = await mcp_server.list_resources()
    return {
        "resources": [
            {
                "uri": r.uri,
                "name": r.name,
                "description": r.description,
                "mimeType": r.mime_type
            }
            for r in resources
        ]
    }


# -----------------------------------------------------------------------------
# 3. SERVER-SENT EVENTS (SSE) STREAM
# -----------------------------------------------------------------------------

@router.get("/sse", summary="Server-Sent Events Stream for MCP Clients")
async def sse_endpoint(request: Request, authorization: Optional[str] = Header(default=None)):
    """Server-Sent Events handshake for network AI agents."""
    _extract_and_authenticate(request, authorization)

    async def event_generator():
        # Emit initial connected event
        init_data = json.dumps({
            "event": "connected",
            "server": "merchant-policy-agent",
            "protocol": "Model Context Protocol",
            "version": "1.0.0"
        })
        yield f"event: endpoint\ndata: {init_data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# -----------------------------------------------------------------------------
# INTERNAL TOOL DISPATCHER
# -----------------------------------------------------------------------------

async def _dispatch_tool(tool_name: str, arguments: Dict[str, Any], db: AsyncSession) -> Any:
    """Internal router dispatching tool calls to authoritative implementations."""
    if tool_name == "search_catalog":
        res = await search_catalog(
            query=arguments.get("query"),
            category=arguments.get("category"),
            max_price_paise=arguments.get("max_price_paise"),
            currency=arguments.get("currency", "INR"),
            db=db
        )
        return [p.model_dump(mode="json") for p in res]

    elif tool_name == "get_product":
        product_id = arguments.get("product_id")
        if not product_id:
            raise McpError("Parameter 'product_id' is required.")
        res = await get_product(product_id=product_id, db=db)
        return res.model_dump(mode="json")

    elif tool_name == "evaluate_buyer_intent":
        message = arguments.get("message")
        if not message:
            raise McpError("Parameter 'message' is required.")
        res = await evaluate_buyer_intent(message=message)
        return res.model_dump(mode="json")

    elif tool_name == "get_offer":
        res = await get_offer(
            message=arguments.get("message"),
            buyer_intent=arguments.get("buyer_intent"),
            opportunity_id=arguments.get("opportunity_id"),
            db=db
        )
        return res.model_dump(mode="json")

    elif tool_name == "request_checkout":
        offer_id = arguments.get("offer_id")
        if not offer_id:
            raise McpError("Parameter 'offer_id' is required.")
        res = await request_checkout(
            offer_id=offer_id,
            idempotency_key=arguments.get("idempotency_key"),
            db=db
        )
        return res.model_dump(mode="json")

    elif tool_name == "get_order_status":
        res = await get_order_status(
            order_id=arguments.get("order_id"),
            razorpay_order_id=arguments.get("razorpay_order_id"),
            db=db
        )
        return res.model_dump(mode="json")

    else:
        raise McpError(f"Unknown tool: '{tool_name}'", details={"tool": tool_name})
