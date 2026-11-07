/**
 * Centralized API Client for Phase 10 Merchant AI Control Center.
 * Connects Next.js to the FastAPI backend.
 */

import {
  DashboardOverview,
  DecisionListResponse,
  DecisionDetail,
  PolicyManagement,
  ExperimentListResponse,
  LearningCenter,
  ActivityListResponse,
  OpportunityTrace,
  ControlActionResponse
} from './types';

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(endpoint: string, options?: RequestInit, merchantId?: string): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> || {})
  };

  if (merchantId) {
    headers['X-Caller-Merchant-ID'] = merchantId;
  }

  try {
    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(errBody.detail || 'API request failed', res.status, errBody);
    }
    return (await res.json()) as T;
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(err.message || 'Network error connecting to backend API', 500);
  }
}

export const api = {
  // 1. Overview
  getOverview: (merchantId: string) =>
    request<DashboardOverview>(`/api/v1/dashboard/overview?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  // 2. Decisions
  getDecisions: (merchantId: string, params?: { limit?: number; offset?: number; mode?: string; status?: string }) => {
    const query = new URLSearchParams({ merchant_id: merchantId });
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    if (params?.mode) query.set('mode', params.mode);
    if (params?.status) query.set('execution_status', params.status);
    return request<DecisionListResponse>(`/api/v1/dashboard/decisions?${query.toString()}`, undefined, merchantId);
  },

  getDecisionDetail: (decisionId: string, merchantId: string) =>
    request<DecisionDetail>(`/api/v1/dashboard/decisions/${encodeURIComponent(decisionId)}?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  executeDecision: (decisionId: string, merchantId: string) =>
    request<any>(`/api/v1/decisions/${encodeURIComponent(decisionId)}/execute`, {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId })
    }, merchantId),

  evaluateDecision: (merchantId: string, prompt?: string) =>
    request<any>('/api/v1/decisions/evaluate', {
      method: 'POST',
      body: JSON.stringify({
        merchant_id: merchantId,
        opportunity_id: `opp_live_demo_${Date.now()}`,
        raw_prompt: prompt || undefined
      })
    }, merchantId),

  reconcileOrder: (orderId: string) =>
    request<any>(`/api/v1/orders/${encodeURIComponent(orderId)}/reconcile`, {
      method: 'POST'
    }),

  // 3. Policies
  getPolicies: (merchantId: string) =>
    request<PolicyManagement>(`/api/v1/dashboard/policies?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  promotePolicy: (merchantId: string, candidatePolicyId: string, rationale: string, expectedPreviousPolicyId?: string) =>
    request<ControlActionResponse>('/api/v1/dashboard/policies/promote', {
      method: 'POST',
      body: JSON.stringify({
        merchant_id: merchantId,
        candidate_policy_id: candidatePolicyId,
        expected_previous_policy_id: expectedPreviousPolicyId,
        rationale
      })
    }, merchantId),

  rollbackPolicy: (merchantId: string, targetPolicyId: string, rationale: string, expectedCurrentPolicyId?: string) =>
    request<ControlActionResponse>('/api/v1/dashboard/policies/rollback', {
      method: 'POST',
      body: JSON.stringify({
        merchant_id: merchantId,
        target_policy_id: targetPolicyId,
        expected_current_policy_id: expectedCurrentPolicyId,
        rationale
      })
    }, merchantId),

  // 4. Experiments
  getExperiments: (merchantId: string) =>
    request<ExperimentListResponse>(`/api/v1/dashboard/experiments?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  // 5. Learning Center
  getLearning: (merchantId: string) =>
    request<LearningCenter>(`/api/v1/dashboard/learning?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  // 6. Activity
  getActivity: (merchantId: string, params?: { limit?: number; offset?: number }) => {
    const query = new URLSearchParams({ merchant_id: merchantId });
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return request<ActivityListResponse>(`/api/v1/dashboard/activity?${query.toString()}`, undefined, merchantId);
  },

  // 7. Opportunity Trace
  getTrace: (opportunityId: string, merchantId: string) =>
    request<OpportunityTrace>(`/api/v1/dashboard/traces/${encodeURIComponent(opportunityId)}?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  // 8. Growth Doctor
  getDoctorFindings: (merchantId: string) =>
    request<any>(`/api/v1/doctor/findings?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  proposeDoctorAction: (merchantId: string, findingId: string) =>
    request<any>('/api/v1/doctor/actions/propose', {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId, finding_id: findingId })
    }, merchantId),

  // 9. Marketplace Growth Manager
  getMarketplacePlan: (merchantId: string) =>
    request<any>(`/api/v1/marketplace/plan?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  getChannels: (merchantId: string) =>
    request<any>(`/api/v1/marketplace/channels?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  generateListing: (merchantId: string, productId: string, channelId: string = 'AMAZON') =>
    request<any>('/api/v1/marketplace/listings/generate', {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId, product_id: productId, channel_id: channelId })
    }, merchantId),

  exportOndc: (merchantId: string, productId: string) =>
    request<any>('/api/v1/marketplace/export/ondc', {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId, product_id: productId })
    }, merchantId),

  // 10. Sales & Negotiation Agent
  chatWithAgent: (merchantId: string, message: string, productId?: string, negotiationRound: number = 1, language: string = 'en') =>
    request<any>('/api/v1/sales-agent/chat', {
      method: 'POST',
      body: JSON.stringify({
        merchant_id: merchantId,
        message,
        product_id: productId,
        negotiation_round: negotiationRound,
        language
      })
    }, merchantId),

  // 11. Owner Policy & Approvals
  parsePolicy: (merchantId: string, text: string) =>
    request<any>('/api/v1/owner/policy/parse', {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId, text })
    }, merchantId),

  confirmPolicy: (merchantId: string, proposalId: string) =>
    request<any>('/api/v1/owner/policy/confirm', {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId, proposal_id: proposalId })
    }, merchantId),

  getApprovals: (merchantId: string) =>
    request<any>(`/api/v1/owner/approvals?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  resolveApproval: (merchantId: string, approvalId: string, decision: 'APPROVED' | 'REJECTED') =>
    request<any>(`/api/v1/owner/approvals/${encodeURIComponent(approvalId)}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId, decision })
    }, merchantId),

  // 12. Campaigns & Group Deals
  getContacts: (merchantId: string) =>
    request<any>(`/api/v1/campaigns/contacts?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  optOutContact: (merchantId: string, phone: string) =>
    request<any>('/api/v1/campaigns/opt-out', {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId, phone })
    }, merchantId),

  getCampaigns: (merchantId: string) =>
    request<any>(`/api/v1/campaigns?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  createCampaign: (merchantId: string, name: string, discountPercent: number, targetSegment: string = 'INACTIVE_60_DAYS') =>
    request<any>('/api/v1/campaigns/create', {
      method: 'POST',
      body: JSON.stringify({
        merchant_id: merchantId,
        name,
        discount_percent: discountPercent,
        target_segment: targetSegment
      })
    }, merchantId),

  dispatchCampaign: (merchantId: string, campaignId: string) =>
    request<any>(`/api/v1/campaigns/${encodeURIComponent(campaignId)}/dispatch?merchant_id=${encodeURIComponent(merchantId)}`, {
      method: 'POST'
    }, merchantId),

  getGroupDeals: (merchantId: string) =>
    request<any>(`/api/v1/campaigns/group-deals?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  createGroupDeal: (merchantId: string, targetGroupName: string, productId: string, minThresholdUnits: number, discountedPricePaise: number) =>
    request<any>('/api/v1/campaigns/group-deals/create', {
      method: 'POST',
      body: JSON.stringify({
        merchant_id: merchantId,
        target_group_name: targetGroupName,
        product_id: productId,
        min_threshold_units: minThresholdUnits,
        discounted_price_paise: discountedPricePaise
      })
    }, merchantId),

  pledgeGroupDeal: (dealId: string, units: number = 1) =>
    request<any>(`/api/v1/campaigns/group-deals/${encodeURIComponent(dealId)}/pledge`, {
      method: 'POST',
      body: JSON.stringify({ units })
    }),

  // 13. Products & Orders
  getProducts: (merchantId: string) =>
    request<any>(`/api/v1/merchants/${encodeURIComponent(merchantId)}/products`, undefined, merchantId),

  createProduct: (merchantId: string, data: any) =>
    request<any>(`/api/v1/merchants/${encodeURIComponent(merchantId)}/products`, {
      method: 'POST',
      body: JSON.stringify(data)
    }, merchantId),

  updateProduct: (merchantId: string, productId: string, data: any) =>
    request<any>(`/api/v1/merchants/${encodeURIComponent(merchantId)}/products/${encodeURIComponent(productId)}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    }, merchantId),

  aiRefineProduct: (merchantId: string, data: any) =>
    request<any>(`/api/v1/merchants/${encodeURIComponent(merchantId)}/products/ai-refine`, {
      method: 'POST',
      body: JSON.stringify(data)
    }, merchantId),

  getOrders: (limit: number = 20, offset: number = 0) =>
    request<any>(`/api/v1/orders?limit=${limit}&offset=${offset}`),

  // 14. Demo Reset
  resetDemoData: (merchantId: string) =>
    request<any>('/api/v1/demo/reset', {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId })
    }, merchantId),

  // 15. WhatsApp Business Integration
  getWhatsAppDiagnostics: () =>
    request<any>('/api/v1/whatsapp/diagnostics'),

  simulateWhatsApp: (senderPhone: string, messageText: string, wamid?: string) =>
    request<any>('/api/v1/whatsapp/simulate', {
      method: 'POST',
      body: JSON.stringify({
        sender_phone: senderPhone,
        message_text: messageText,
        wamid: wamid
      })
    }),

  // 16. Gnani Voice AI & Flagship Doctor Advisor
  transcribeVoice: async (audioBlob: Blob, languageCode: string = 'indic-auto', formatType: string = 'codemix') => {
    const formData = new FormData();
    const filename = audioBlob.type.includes('wav') ? 'merchant_audio.wav' : 'merchant_audio.webm';
    formData.append('audio_file', audioBlob, filename);
    formData.append('language_code', languageCode);
    formData.append('format_type', formatType);

    const res = await fetch(`${API_BASE}/api/v1/voice/transcribe`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Voice transcription failed');
    }
    return await res.json();
  },

  synthesizeVoice: (text: string, language: string = 'kn', voice?: string) =>
    request<any>('/api/v1/voice/synthesize', {
      method: 'POST',
      body: JSON.stringify({ text, language, voice })
    }),

  queryDoctor: (data: {
    merchant_id?: string;
    query: string;
    session_id?: string;
    conversation_history?: Array<{ role: string; content: string }>;
    preferred_language?: string;
    synthesize_audio?: boolean;
    agent_type?: string;
  }) =>
    request<any>('/api/v1/doctor/query', {
      method: 'POST',
      body: JSON.stringify({
        merchant_id: data.merchant_id || 'merch_atlas_travel',
        query: data.query,
        session_id: data.session_id,
        conversation_history: data.conversation_history || [],
        preferred_language: data.preferred_language,
        synthesize_audio: data.synthesize_audio ?? true,
        agent_type: data.agent_type || 'DOCTOR'
      })
    }, data.merchant_id),

  queryVoiceAgent: (data: {
    merchant_id?: string;
    query: string;
    session_id?: string;
    conversation_history?: Array<{ role: string; content: string }>;
    preferred_language?: string;
    synthesize_audio?: boolean;
  }) =>
    request<any>('/api/v1/doctor/query', {
      method: 'POST',
      body: JSON.stringify({
        merchant_id: data.merchant_id || 'merch_atlas_travel',
        query: data.query,
        session_id: data.session_id,
        conversation_history: data.conversation_history || [],
        preferred_language: data.preferred_language,
        synthesize_audio: data.synthesize_audio ?? true,
        agent_type: 'VOICE_AGENT'
      })
    }, data.merchant_id),

  createCallback: (data: {
    merchant_id: string;
    phone_number: string;
    preferred_language: string;
    topic: string;
    reason?: string;
    preferred_time_slot?: string;
  }) =>
    request<any>('/api/v1/doctor/callback', {
      method: 'POST',
      body: JSON.stringify(data)
    }, data.merchant_id),

  getCallbacks: (merchantId: string) =>
    request<any>(`/api/v1/doctor/callbacks?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  approveDoctorAction: (data: {
    merchant_id: string;
    action_type: string;
    action_title: string;
    payload: any;
  }) =>
    request<any>('/api/v1/doctor/action/approve', {
      method: 'POST',
      body: JSON.stringify(data)
    }, data.merchant_id),

  // Stage E: Persistent Sessions & Governed Action Lifecycle
  getDoctorSessions: (merchantId: string) =>
    request<any>(`/api/v1/doctor/sessions?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  createDoctorSession: (merchantId: string, title?: string, language: string = 'kn') =>
    request<any>('/api/v1/doctor/sessions', {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId, title, language })
    }, merchantId),

  getDoctorSession: (merchantId: string, sessionId: string) =>
    request<any>(`/api/v1/doctor/sessions/${encodeURIComponent(sessionId)}?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  archiveDoctorSession: (merchantId: string, sessionId: string) =>
    request<any>(`/api/v1/doctor/sessions/${encodeURIComponent(sessionId)}/archive`, {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId })
    }, merchantId),

  interruptDoctorSession: (merchantId: string, sessionId: string, partialText?: string) =>
    request<any>(`/api/v1/doctor/sessions/${encodeURIComponent(sessionId)}/interrupt`, {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId, partial_text: partialText })
    }, merchantId),

  getDoctorPendingActions: (merchantId: string) =>
    request<any>(`/api/v1/doctor/actions/pending?merchant_id=${encodeURIComponent(merchantId)}`, undefined, merchantId),

  approveDoctorActionProposal: (merchantId: string, proposalId: string, actor: string = 'MERCHANT_OWNER') =>
    request<any>(`/api/v1/doctor/actions/${encodeURIComponent(proposalId)}/approve`, {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId, actor })
    }, merchantId),

  rejectDoctorActionProposal: (merchantId: string, proposalId: string, reason?: string, actor: string = 'MERCHANT_OWNER') =>
    request<any>(`/api/v1/doctor/actions/${encodeURIComponent(proposalId)}/reject`, {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId, reason, actor })
    }, merchantId),

  cancelDoctorActionProposal: (merchantId: string, proposalId: string, actor: string = 'MERCHANT_OWNER') =>
    request<any>(`/api/v1/doctor/actions/${encodeURIComponent(proposalId)}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ merchant_id: merchantId, actor })
    }, merchantId),

  // Gnani Agent Builder Platform Endpoints
  getGnaniAgentStatus: (merchantId: string) =>
    request<any>('/api/v1/gnani-agent/status', undefined, merchantId),

  getGnaniAgentConfig: (merchantId: string, environment: string = 'development') =>
    request<any>(`/api/v1/gnani-agent/config?environment=${encodeURIComponent(environment)}`, undefined, merchantId),

  getGnaniChatWidgetConfig: (merchantId: string, environment: string = 'development') =>
    request<any>(`/api/v1/gnani-agent/chat-widget?environment=${encodeURIComponent(environment)}`, undefined, merchantId),

  triggerGnaniTestCall: (merchantId: string, phoneNumber: string, clientReferenceId?: string) =>
    request<any>('/api/v1/gnani-agent/trigger-call', {
      method: 'POST',
      body: JSON.stringify({ phone_number: phoneNumber, client_reference_id: clientReferenceId })
    }, merchantId),

  syncGnaniKnowledge: (merchantId: string) =>
    request<any>(`/api/v1/gnani-agent/sync-knowledge?merchant_id=${encodeURIComponent(merchantId)}`, {
      method: 'POST'
    }, merchantId)
};

// Utilities for currency, dates, and formatting
export function formatPaise(paise: number | undefined | null, currency: string = 'INR'): string {
  if (paise === undefined || paise === null) return '₹0';
  const rupees = paise / 100;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: currency,
    maximumFractionDigits: 0
  }).format(rupees);
}

export function formatPercent(val: number | undefined | null): string {
  if (val === undefined || val === null) return '0%';
  return `${Number(val).toFixed(1)}%`;
}

export function formatDateTime(isoString?: string | null): string {
  if (!isoString) return '—';
  try {
    const date = new Date(isoString);
    return new Intl.DateTimeFormat('en-IN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    }).format(date);
  } catch {
    return isoString;
  }
}

export function getExecutionStatusBadge(status: string): { className: string; label: string } {
  switch (status) {
    case 'EXECUTION_COMPLETED':
      return { className: 'bg-emerald-50 text-emerald-700 border border-emerald-200', label: 'EXECUTION_COMPLETED' };
    case 'EXECUTION_REJECTED':
      return { className: 'bg-rose-50 text-rose-700 border border-rose-200', label: 'EXECUTION_REJECTED' };
    case 'SAFETY_REJECTED':
      return { className: 'bg-rose-50 text-rose-700 border border-rose-200', label: 'SAFETY_REJECTED' };
    case 'PENDING_EXECUTION_GATE':
      return { className: 'bg-amber-50 text-amber-700 border border-amber-200', label: 'PENDING_EXECUTION_GATE' };
    default:
      return { className: 'bg-slate-50 text-slate-700 border border-slate-200', label: status || 'UNKNOWN' };
  }
}

export function getOutcomeStatusBadge(status?: string | null): { className: string; label: string } | null {
  if (!status) return null;
  switch (status) {
    case 'PAYMENT_SUCCESS':
      return { className: 'bg-emerald-50 text-emerald-700 border border-emerald-200', label: 'PAID (Test Mode)' };
    case 'PAYMENT_FAILED':
    case 'FAILED':
      return { className: 'bg-rose-50 text-rose-700 border border-rose-200', label: 'PAYMENT_FAILED' };
    case 'ORDER_CREATED':
      return { className: 'bg-blue-50 text-blue-700 border border-blue-200', label: 'ORDER_CREATED' };
    default:
      return { className: 'bg-slate-50 text-slate-700 border border-slate-200', label: status };
  }
}
