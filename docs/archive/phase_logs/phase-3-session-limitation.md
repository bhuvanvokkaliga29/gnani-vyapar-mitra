# Phase 3 Session Limitation Documentation

**Date**: September 3, 2026  
**Applies to**: `ConversationManager` and `ConversationSession`

---

## Session Architecture

The Buyer Intent Engine uses an **in-memory session store** for multi-turn conversational state.

### Implementation

```python
class ConversationManager:
    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}
```

- **Storage**: Python `dict` in the application process heap
- **Session key**: UUID-based `conversation_id` (e.g., `conv_a1b2c3d4e5f6`)
- **Session contents**: List of turn utterances + accumulated `BuyerIntent` object

### Lifecycle

| Event | Behavior |
|:---|:---|
| First request with no `conversation_id` | New session created, UUID assigned |
| Subsequent request with same `conversation_id` | Existing session retrieved, turn added |
| Request with unknown `conversation_id` | New empty session created (no error) |
| Process restart (uvicorn reload, crash, deploy) | **All sessions lost** |
| Horizontal scaling (multiple processes) | **Sessions not shared** between processes |

## Known Limitations

### 1. Volatile State

Sessions exist **only in the memory of the specific process** handling requests. They are lost on:

- Application restart
- Server crash
- Deployment rollout
- Container recreation
- `uvicorn --reload` (development hot-reload)

**Impact**: A buyer mid-conversation will lose accumulated context if the server restarts. Their next message starts a fresh session.

### 2. No Horizontal Scaling

If the application runs behind a load balancer with multiple workers/processes, sessions are **not shared**:

- Process A creates session `conv_123`
- Process B receives the next request for `conv_123`
- Process B creates a **new empty session** — all prior context is lost

**Mitigation for production**: Use sticky sessions (session affinity) at the load balancer, or migrate to Redis/database-backed sessions.

### 3. No Persistence

Sessions are never written to disk or database. There is no recovery mechanism after process termination.

### 4. No Expiration

Sessions are never automatically expired. In a long-running process, the `_sessions` dict will grow unboundedly. This is acceptable for the Buildathon scope but would need TTL-based eviction in production.

## Isolation Guarantee

Despite the in-memory limitation, sessions are **strictly isolated** by conversation ID:

- Session A's accumulated intent is never accessible from Session B
- Session A's utterance history is never mixed with Session B's
- This is verified by `tests/integration/test_intent_api_hardening.py::TestSessionIsolation`

## Future Migration Path

For production deployment, the session store should be migrated to:

1. **Redis** with TTL expiration (recommended for low-latency multi-turn)
2. **PostgreSQL** via the existing async SQLAlchemy infrastructure
3. **DynamoDB** or equivalent for serverless deployments

The `ConversationManager` interface is designed to make this migration straightforward — only `get_or_create_session()` and `reset()` need new implementations.
