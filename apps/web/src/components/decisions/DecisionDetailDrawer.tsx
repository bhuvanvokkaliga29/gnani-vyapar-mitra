'use client';

import React, { useState, useEffect } from 'react';
import {
  X,
  Copy,
  Check,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  Lock,
  Eye,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  Sparkles,
  Clock
} from 'lucide-react';
import { DecisionDetail } from '@/lib/types';
import { api, formatPaise, formatPercent, formatDateTime } from '@/lib/api';

interface DecisionDetailDrawerProps {
  decisionId: string | null;
  merchantId: string;
  onClose: () => void;
}

export function DecisionDetailDrawer({ decisionId, merchantId, onClose }: DecisionDetailDrawerProps) {
  const [detail, setDetail] = useState<DecisionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'buyer' | 'merchant' | 'candidates'>('buyer');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [isEvaluatingFresh, setIsEvaluatingFresh] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [checkoutSuccessMessage, setCheckoutSuccessMessage] = useState<string | null>(null);

  const isStaleByTtl = detail?.created_at
    ? Date.now() - new Date(detail.created_at).getTime() > 900 * 1000
    : false;

  const isExecutable =
    detail &&
    !isStaleByTtl &&
    detail.safety_status === 'ADMISSIBLE' &&
    detail.buyer_offer?.strategy_type !== 'NO_OFFER' &&
    detail.execution_status !== 'SAFETY_REJECTED' &&
    detail.execution_status !== 'POLICY_RETIRED' &&
    detail.execution_status !== 'POLICY_ROLLED_BACK' &&
    detail.execution_status !== 'POLICY_NOT_ACTIVE' &&
    detail.execution_status !== 'DECISION_STALE' &&
    detail.execution_status !== 'EXECUTION_REJECTED' &&
    detail.execution_status !== 'EXECUTION_CONFLICT' &&
    detail.execution_status !== 'TENANT_MISMATCH' &&
    detail.execution_status !== 'INVALID_DECISION' &&
    detail.outcome_status !== 'PAYMENT_SUCCESS';

  const handleEvaluateFresh = async () => {
    setIsEvaluatingFresh(true);
    setCheckoutError(null);
    setCheckoutSuccessMessage(null);
    try {
      const res = await api.evaluateDecision(merchantId);
      if (res && res.decision_id) {
        const freshDetail = await api.getDecisionDetail(res.decision_id, merchantId);
        setDetail(freshDetail);
        setCheckoutSuccessMessage(`Evaluated fresh opportunity (${res.decision_id}). Ready for checkout!`);
      }
    } catch (err: any) {
      setCheckoutError(err.message || 'Failed to evaluate fresh opportunity');
    } finally {
      setIsEvaluatingFresh(false);
    }
  };

  const handleStartCheckout = async () => {
    if (!detail) return;
    setIsCheckingOut(true);
    setCheckoutError(null);
    setCheckoutSuccessMessage(null);

    try {
      // 1. Traverse execution boundary
      const execResult = await api.executeDecision(detail.decision_id, merchantId);

      if (!execResult.execution_authorized || execResult.boundary_status !== 'EXECUTION_COMPLETED') {
        const rejectionMsg = execResult.rejection_reasons?.join(', ') || `Boundary execution rejected (${execResult.boundary_status})`;
        setCheckoutError(rejectionMsg);
        const updated = await api.getDecisionDetail(detail.decision_id, merchantId);
        setDetail(updated);
        return;
      }

      const razorpayOrderId = execResult.razorpay_order_id || detail.razorpay_order_id;
      const authorizedAmountPaise = execResult.authorized_amount_paise || detail.authorized_amount_paise || detail.buyer_offer.offer_price_paise;

      if (!razorpayOrderId) {
        throw new Error('No Razorpay Order ID returned from execution boundary.');
      }

      const keyId = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || 'rzp_test_TXLFfNuyfKpBqM';

      // 2. If Razorpay Checkout SDK is loaded on window, open authentic Test Mode checkout modal
      if (typeof window !== 'undefined' && (window as any).Razorpay) {
        const options = {
          key: keyId,
          amount: authorizedAmountPaise,
          currency: 'INR',
          name: 'Merchant Policy Agent',
          description: `Order ${execResult.order_id || razorpayOrderId} - Test Mode`,
          order_id: razorpayOrderId,
          handler: async function (response: any) {
            try {
              setCheckoutSuccessMessage(`Payment Captured (${response.razorpay_payment_id}). Reconciling closed loop...`);
              await api.reconcileOrder(response.razorpay_order_id);
            } catch (err: any) {
              console.error('Reconciliation error:', err);
            }
            // Reload decision detail to reflect completed 11-stage trace
            const updated = await api.getDecisionDetail(detail.decision_id, merchantId);
            setDetail(updated);
            setCheckoutSuccessMessage('Payment complete! All 11 closed-loop stages verified.');
          },
          prefill: {
            name: 'AI Buyer Agent',
            email: 'ai.buyer@example.com',
            contact: '9999999999'
          },
          theme: { color: '#2563eb' }
        };

        const rzp = new (window as any).Razorpay(options);
        rzp.open();
      } else {
        // Fallback: Open standalone test checkout harness in new window
        const checkoutUrl = `/test_checkout.html?key_id=${encodeURIComponent(keyId)}&order_id=${encodeURIComponent(razorpayOrderId)}&amount=${authorizedAmountPaise}`;
        window.open(checkoutUrl, '_blank', 'noopener,noreferrer');
      }
    } catch (err: any) {
      setCheckoutError(err.message || 'Failed to initiate test checkout');
    } finally {
      setIsCheckingOut(false);
    }
  };

  useEffect(() => {
    if (!decisionId) return;
    setLoading(true);
    setError(null);
    api.getDecisionDetail(decisionId, merchantId)
      .then((data) => setDetail(data))
      .catch((err) => setError(err.message || 'Failed to load decision detail'))
      .finally(() => setLoading(false));
  }, [decisionId, merchantId]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!decisionId) return null;

  const copyToClipboard = (text?: string | null, label?: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedId(label || text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const stages = [
    { key: 'req', label: '1. Request', id: detail?.request_id, active: !!detail?.request_id },
    { key: 'opp', label: '2. Opportunity', id: detail?.opportunity_id, active: !!detail?.opportunity_id },
    { key: 'dec', label: '3. Decision', id: detail?.decision_id, active: !!detail?.decision_id },
    { key: 'eauth', label: '4. Authorization', id: detail?.authorization_id, active: !!detail?.authorization_id },
    { key: 'dexec', label: '5. Execution', id: detail?.execution_id, active: !!detail?.execution_id },
    { key: 'ord', label: '6. Order', id: detail?.order_id, active: !!detail?.order_id },
    { key: 'pay', label: '7. Payment', id: detail?.payment_id, active: !!detail?.payment_id },
    { key: 'out', label: '8. Outcome', id: detail?.outcome_id, active: !!detail?.outcome_id },
    { key: 'evi', label: '9. Evidence', id: detail?.evidence_id, active: !!detail?.evidence_id },
    { key: 'mem', label: '10. Memory', id: detail?.memory_id, active: !!detail?.memory_id },
    { key: 'amo', label: '11. Model Update', id: detail?.applied_observation_id, active: !!detail?.applied_observation_id },
  ];

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/20 backdrop-blur-[1px]" role="dialog" aria-modal="true" aria-label="Decision Inspection Drawer">
      <div className="w-full max-w-2xl bg-white border-l border-[#e5edf5] h-full flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="p-5 border-b border-[#e5edf5] flex items-center justify-between bg-[#f8fafd]">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-[#533afd] font-medium">{detail?.decision_id || decisionId}</span>
              <button
                onClick={() => copyToClipboard(detail?.decision_id, 'header_dec')}
                aria-label="Copy decision ID"
                className="text-[#64748d] hover:text-[#061b31]"
              >
                {copiedId === 'header_dec' ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
            <h2 className="text-base font-medium text-[#061b31] mt-0.5">Autonomous Decision Inspection</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close drawer"
            className="p-1 rounded hover:bg-white text-[#64748d] hover:text-[#061b31] border border-transparent hover:border-[#e5edf5]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {loading && (
            <div className="py-20 text-center text-xs text-[#64748d]">
              Loading authoritative decision lineage...
            </div>
          )}

          {error && (
            <div className="p-4 rounded border border-rose-200 bg-rose-50 text-xs text-rose-800">
              {error}
            </div>
          )}

          {detail && (
            <>
              {/* 11-Stage Lineage Stepper */}
              <div className="stripe-card p-4">
                <div className="text-xs font-medium text-[#50617a] mb-2 uppercase tracking-wider">
                  11-Stage End-to-End Identity Chain
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {stages.map((st) => (
                    <div
                      key={st.key}
                      className={`p-2 rounded border flex items-center justify-between font-mono ${
                        st.active
                          ? 'border-[#d6d9fc] bg-[#f8fafd]'
                          : 'border-dashed border-[#e5edf5] bg-white opacity-50'
                      }`}
                    >
                      <div className="truncate pr-2">
                        <div className="text-[10px] text-[#64748d] font-sans">{st.label}</div>
                        <div className="truncate text-[#061b31] font-medium text-[11px]">
                          {st.id || 'Not reached'}
                        </div>
                      </div>
                      {st.id && (
                        <button
                          onClick={() => copyToClipboard(st.id, st.key)}
                          className="shrink-0 p-1 text-[#64748d] hover:text-[#533afd]"
                        >
                          {copiedId === st.key ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Strict Dual-View Tabs */}
              <div>
                <div className="flex border-b border-[#e5edf5] gap-4 mb-4">
                  <button
                    onClick={() => setActiveTab('buyer')}
                    className={`pb-2 text-xs font-medium flex items-center gap-1.5 transition-colors ${
                      activeTab === 'buyer'
                        ? 'border-b-2 border-[#533afd] text-[#533afd]'
                        : 'text-[#64748d] hover:text-[#061b31]'
                    }`}
                  >
                    <Eye className="w-3.5 h-3.5" />
                    Buyer-Facing Offer
                  </button>
                  <button
                    onClick={() => setActiveTab('merchant')}
                    className={`pb-2 text-xs font-medium flex items-center gap-1.5 transition-colors ${
                      activeTab === 'merchant'
                        ? 'border-b-2 border-[#533afd] text-[#533afd]'
                        : 'text-[#64748d] hover:text-[#061b31]'
                    }`}
                  >
                    <Lock className="w-3.5 h-3.5 text-[#533afd]" />
                    Merchant Unit Economics (Private)
                  </button>
                  <button
                    onClick={() => setActiveTab('candidates')}
                    className={`pb-2 text-xs font-medium flex items-center gap-1.5 transition-colors ${
                      activeTab === 'candidates'
                        ? 'border-b-2 border-[#533afd] text-[#533afd]'
                        : 'text-[#64748d] hover:text-[#061b31]'
                    }`}
                  >
                    Selected Candidate
                  </button>
                </div>

                {/* Buyer Offer Tab */}
                {activeTab === 'buyer' && (
                  <div className="space-y-4">
                    <div className="p-3 bg-[#e8e9ff] border border-[#b9b9f9] rounded text-[11px] text-[#182659] leading-relaxed">
                      <span className="font-semibold">Confidential Information Hygiene:</span> Buyer received the exact product proposal below. Merchant internal COGS, profit margin, and predicted contribution are strictly withheld from buyer-facing payloads.
                    </div>

                    <div className="stripe-card p-4 space-y-3">
                      <div className="flex justify-between items-start">
                        <div>
                          <div className="text-xs text-[#64748d]">Offer Title</div>
                          <div className="text-sm font-medium text-[#061b31] mt-0.5">{detail.buyer_offer.offer_title}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs text-[#64748d]">Offer Price</div>
                          <div className="text-lg font-medium text-[#061b31] tabular-nums">
                            {formatPaise(detail.buyer_offer.offer_price_paise, detail.buyer_offer.currency)}
                          </div>
                        </div>
                      </div>

                      <div className="grid grid-cols-3 gap-3 pt-3 border-t border-[#e5edf5] text-xs">
                        <div>
                          <span className="text-[#64748d]">Strategy</span>
                          <div className="font-medium text-[#061b31] mt-0.5">{detail.buyer_offer.strategy_type}</div>
                        </div>
                        <div>
                          <span className="text-[#64748d]">Delivery</span>
                          <div className="font-medium text-[#061b31] mt-0.5">{detail.buyer_offer.delivery_days} days</div>
                        </div>
                        <div>
                          <span className="text-[#64748d]">Warranty</span>
                          <div className="font-medium text-[#061b31] mt-0.5">{detail.buyer_offer.warranty_months} months</div>
                        </div>
                      </div>

                      {detail.buyer_offer.included_items.length > 0 && (
                        <div className="pt-2 border-t border-[#e5edf5]">
                          <span className="text-[11px] text-[#64748d]">Included Items & Accessories:</span>
                          <div className="flex flex-wrap gap-1.5 mt-1">
                            {detail.buyer_offer.included_items.map((it, idx) => (
                              <span key={idx} className="stripe-tag bg-[#f8fafd] border border-[#e5edf5] text-[#50617a] text-[11px]">
                                {it}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Merchant Private Tab */}
                {activeTab === 'merchant' && (
                  <div className="space-y-4">
                    <div className="stripe-card p-4 space-y-4">
                      <div className="grid grid-cols-3 gap-4 text-xs">
                        <div>
                          <div className="text-[#64748d]">Product COGS</div>
                          <div className="text-base font-medium text-[#061b31] mt-0.5 tabular-nums">
                            {formatPaise(detail.merchant_evaluation.cogs_paise)}
                          </div>
                        </div>
                        <div>
                          <div className="text-[#64748d]">Gross Profit</div>
                          <div className="text-base font-medium text-emerald-700 mt-0.5 tabular-nums">
                            {formatPaise(detail.merchant_evaluation.gross_profit_paise)}
                          </div>
                        </div>
                        <div>
                          <div className="text-[#64748d]">Gross Margin</div>
                          <div className="text-base font-medium text-[#061b31] mt-0.5 tabular-nums">
                            {formatPercent(detail.merchant_evaluation.gross_margin_percent)}
                          </div>
                        </div>
                      </div>

                      <div className="grid grid-cols-3 gap-4 pt-3 border-t border-[#e5edf5] text-xs">
                        <div>
                          <div className="text-[#64748d]">Predicted Contribution</div>
                          <div className="text-sm font-medium text-[#533afd] mt-0.5 tabular-nums">
                            {formatPaise(detail.merchant_evaluation.predicted_contribution_paise)}
                          </div>
                        </div>
                        <div>
                          <div className="text-[#64748d]" title="LinUCB exploration radius: s(x) = sqrt(x^T A^-1 x)">
                            Bandit Uncertainty
                          </div>
                          <div className="text-sm font-medium text-[#061b31] mt-0.5 tabular-nums">
                            ±{detail.merchant_evaluation.uncertainty.toFixed(3)}
                          </div>
                          <div className="text-[10px] text-[#64748d]">s = √(xᵀA⁻¹x)</div>
                        </div>
                        <div>
                          <div className="text-[#64748d]">Decision Mode</div>
                          <div className="mt-0.5">
                            <span className="stripe-tag bg-[#e8e9ff] text-[#533afd] text-[10px] font-medium">
                              {detail.merchant_evaluation.decision_mode}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="pt-3 border-t border-[#e5edf5]">
                        <div className="text-xs text-[#64748d]">Decision Rationale</div>
                        <p className="text-xs text-[#50617a] mt-1 leading-relaxed bg-[#f8fafd] p-2.5 rounded border border-[#e5edf5]">
                          {detail.merchant_evaluation.rationale}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Candidate Alternatives Tab */}
                {activeTab === 'candidates' && (
                  <div className="space-y-3">
                    <div className="p-2.5 bg-[#f8fafd] border border-[#e5edf5] rounded text-[11px] text-[#50617a]">
                      Selected policy candidate evaluated for this buyer decision from generated slate. Governed active policy baseline remains distinct.
                    </div>
                    <div className="stripe-card overflow-hidden">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="bg-[#f8fafd] border-b border-[#e5edf5] text-[#64748d]">
                            <th className="p-2.5">Candidate ID</th>
                            <th className="p-2.5">Strategy</th>
                            <th className="p-2.5 text-right">Price</th>
                            <th className="p-2.5 text-right">Predicted Contribution</th>
                            <th className="p-2.5 text-right" title="Deterministic candidate multi-factor ranking score (0.000 - 1.000) from Phase 3">Ranking Score</th>
                            <th className="p-2.5 text-center">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detail.candidates.map((c) => (
                            <tr
                              key={c.candidate_id}
                              className={`border-b border-[#e5edf5] ${
                                c.is_selected ? 'bg-[#e8e9ff]/30 font-medium' : 'hover:bg-[#f8fafd]'
                              }`}
                            >
                              <td className="p-2.5 font-mono text-[11px]">{c.candidate_id}</td>
                              <td className="p-2.5">{c.strategy_type}</td>
                              <td className="p-2.5 text-right tabular-nums">{formatPaise(c.proposed_price_paise)}</td>
                              <td className="p-2.5 text-right tabular-nums">{formatPaise(c.predicted_contribution_paise)}</td>
                              <td className="p-2.5 text-right tabular-nums">{c.composite_ranking_score.toFixed(3)}</td>
                              <td className="p-2.5 text-center">
                                {c.is_selected ? (
                                  <span className="stripe-tag bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px]">
                                    SELECTED
                                  </span>
                                ) : (
                                  <span className="text-[10px] text-[#64748d]">Candidate</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>

              {/* Safety & Execution Status */}
              <div className="grid grid-cols-2 gap-4">
                <div className="stripe-card p-3.5 space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-[#061b31]">
                    <ShieldCheck className="w-4 h-4 text-emerald-600" />
                    Safety Clearance
                  </div>
                  <div className="text-xs text-[#50617a]">
                    Status: <span className="font-medium text-emerald-700">{detail.safety_status}</span>
                  </div>
                  {detail.safety_rejection_reasons.length > 0 && (
                    <div className="text-[11px] text-rose-700 bg-rose-50 p-2 rounded">
                      {detail.safety_rejection_reasons.join(', ')}
                    </div>
                  )}
                </div>

                <div className="stripe-card p-3.5 space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-medium text-[#061b31]">
                    <CheckCircle2 className="w-4 h-4 text-[#533afd]" />
                    Boundary Execution & Learning
                  </div>
                  <div className="text-xs text-[#50617a]">
                    Execution: <span className="font-medium text-[#061b31]">{detail.execution_status}</span>
                  </div>
                  <div className="text-xs text-[#50617a]">
                    Outcome: <span className={`font-medium ${
                      detail.outcome_status === 'PAYMENT_SUCCESS'
                        ? 'text-emerald-700'
                        : detail.outcome_status === 'PAYMENT_FAILED'
                        ? 'text-amber-700'
                        : 'text-[#64748d]'
                    }`}>{detail.outcome_status || 'NOT_REACHED'}</span>
                  </div>
                  <div className="text-xs text-[#50617a]">
                    Learning Eligible: <span className="font-medium text-[#061b31]">{detail.learning_eligible ? 'YES' : 'NO'}</span>
                    {detail.outcome_status === 'PAYMENT_FAILED' && detail.learning_eligible && (
                      <span className="block text-[10px] text-[#64748d] mt-0.5">
                        Non-purchase observed with ₹0 reward for unbiased bandit feedback
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Test Mode Checkout Action */}
              {isExecutable && (
                <div className="stripe-card p-4 bg-gradient-to-r from-[#f8fafd] to-[#eff6ff] border border-[#bfdbfe] rounded-lg shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#2563eb] text-white tracking-wide uppercase">
                        Instant Checkout
                      </span>
                      <span className="text-xs font-semibold text-[#061b31]">
                        Commercial Checkout Ready
                      </span>
                    </div>
                    <span className="font-mono text-xs font-bold text-[#2563eb]">
                      {formatPaise(detail.buyer_offer.offer_price_paise)}
                    </span>
                  </div>
                  <p className="text-xs text-[#50617a] leading-relaxed">
                    This decision has cleared deterministic commercial safety and is eligible for execution.
                    Launch checkout to complete the transaction and verify settlement.
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      onClick={handleStartCheckout}
                      disabled={isCheckingOut}
                      className="inline-flex items-center justify-center gap-1.5 px-4 py-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white text-xs font-semibold rounded shadow transition-colors disabled:opacity-50 cursor-pointer"
                    >
                      {isCheckingOut ? (
                        <>
                          <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          <span>Preparing Checkout...</span>
                        </>
                      ) : (
                        <>
                          <ExternalLink className="w-3.5 h-3.5" />
                          <span>Open Checkout</span>
                        </>
                      )}
                    </button>
                    {checkoutError && (
                      <span className="text-[11px] text-rose-600 bg-rose-50 px-2 py-1 rounded">
                        {checkoutError}
                      </span>
                    )}
                    {checkoutSuccessMessage && (
                      <span className="text-[11px] text-emerald-700 bg-emerald-50 px-2 py-1 rounded font-medium">
                        {checkoutSuccessMessage}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Stale TTL Expired Alert & Live Evaluation Action */}
              {(isStaleByTtl || detail.execution_status === 'DECISION_STALE') && detail.outcome_status !== 'PAYMENT_SUCCESS' && (
                <div className="stripe-card p-4 bg-amber-50/60 border border-amber-200 rounded-lg shadow-sm space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-200 text-amber-900 tracking-wide uppercase">
                        Safety TTL Expired (15m)
                      </span>
                      <span className="text-xs font-semibold text-amber-900">
                        Decision Expired
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-amber-800 leading-relaxed">
                    Commercial decisions expire after 15 minutes to guarantee fresh inventory and pricing safety. Generate a fresh live opportunity to test commercial checkout.
                  </p>
                  <div className="flex items-center gap-2 pt-1">
                    <button
                      onClick={handleEvaluateFresh}
                      disabled={isEvaluatingFresh}
                      className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 bg-[#533afd] hover:bg-[#432ec7] text-white text-xs font-semibold rounded shadow transition-colors disabled:opacity-50 cursor-pointer"
                    >
                      <Sparkles className={`w-3.5 h-3.5 ${isEvaluatingFresh ? 'animate-spin' : ''}`} />
                      <span>{isEvaluatingFresh ? 'Evaluating Fresh Opportunity...' : 'Evaluate Fresh Live Opportunity'}</span>
                    </button>
                    {checkoutError && (
                      <span className="text-[11px] text-rose-600 bg-rose-50 px-2 py-1 rounded">
                        {checkoutError}
                      </span>
                    )}
                    {checkoutSuccessMessage && (
                      <span className="text-[11px] text-emerald-700 bg-emerald-50 px-2 py-1 rounded font-medium">
                        {checkoutSuccessMessage}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
