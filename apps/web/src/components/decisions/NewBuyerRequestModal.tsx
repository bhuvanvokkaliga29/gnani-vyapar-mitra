'use client';

import React, { useState, useEffect } from 'react';
import {
  X,
  Sparkles,
  ShoppingBag,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  RefreshCw,
  Clock,
  CheckCircle2,
  ExternalLink,
  Eye,
  Copy,
  Check,
  Tag,
  PackageCheck,
  SlidersHorizontal
} from 'lucide-react';
import { DecisionDetail } from '@/lib/types';
import { api, formatPaise, formatDateTime } from '@/lib/api';

interface NewBuyerRequestModalProps {
  isOpen: boolean;
  merchantId: string;
  onClose: () => void;
  onDecisionCreated?: (decisionId: string) => void;
  onOpenFullTrace?: (decisionId: string) => void;
}

const CANONICAL_PRESETS: { label: string; prompt: string; intentTag: string }[] = [
  {
    label: 'Weekend Backpack',
    prompt: 'Looking for a durable weekend travel backpack under 4000',
    intentTag: 'Standard Fulfillment'
  },
  {
    label: 'Laptop Sleeve Bundle',
    prompt: 'Looking for a travel pack together with a protective laptop sleeve under 6000',
    intentTag: 'Complementary Bundle'
  },
  {
    label: 'Strict Budget Pack',
    prompt: 'Need a durable travel backpack with a strict ceiling of 2850',
    intentTag: 'Bounded Discount'
  },
  {
    label: 'Commuter Pack',
    prompt: 'Looking for an ultralight commuter backpack under 3000 for daily travel',
    intentTag: 'Substitute Product'
  },
  {
    label: 'Low Budget NO_OFFER',
    prompt: 'Need durable hiking backpack under 800',
    intentTag: 'Safety Boundary Test'
  }
];

export function NewBuyerRequestModal({
  isOpen,
  merchantId,
  onClose,
  onDecisionCreated,
  onOpenFullTrace
}: NewBuyerRequestModalProps) {
  const [step, setStep] = useState<'composer' | 'result'>('composer');
  const [prompt, setPrompt] = useState('');
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<DecisionDetail | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Checkout flow state
  const [isCheckingOut, setIsCheckingOut] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [checkoutSuccessMessage, setCheckoutSuccessMessage] = useState<string | null>(null);

  // Reset when opening
  useEffect(() => {
    if (isOpen) {
      setStep('composer');
      setPrompt('');
      setError(null);
      setDetail(null);
      setCheckoutError(null);
      setCheckoutSuccessMessage(null);
    }
  }, [isOpen]);

  // Escape key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const copyToClipboard = (text?: string | null, label?: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedId(label || text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const isStaleByTtl = detail?.created_at
    ? Date.now() - new Date(detail.created_at).getTime() > 900 * 1000
    : false;

  const isNoOffer =
    detail?.buyer_offer?.strategy_type === 'NO_OFFER' ||
    detail?.candidates?.some((c) => c.is_selected && c.strategy_type === 'NO_OFFER') ||
    detail?.buyer_offer?.offer_price_paise === 0;

  const isAlreadyPaid = detail?.outcome_status === 'PAYMENT_SUCCESS';

  const isExecutable =
    detail &&
    !isStaleByTtl &&
    !isNoOffer &&
    !isAlreadyPaid &&
    detail.safety_status === 'ADMISSIBLE' &&
    detail.execution_status !== 'SAFETY_REJECTED' &&
    detail.execution_status !== 'POLICY_RETIRED' &&
    detail.execution_status !== 'POLICY_ROLLED_BACK' &&
    detail.execution_status !== 'POLICY_NOT_ACTIVE' &&
    detail.execution_status !== 'DECISION_STALE' &&
    detail.execution_status !== 'EXECUTION_REJECTED' &&
    detail.execution_status !== 'EXECUTION_CONFLICT' &&
    detail.execution_status !== 'TENANT_MISMATCH' &&
    detail.execution_status !== 'INVALID_DECISION';

  const handleEvaluate = async () => {
    setIsEvaluating(true);
    setError(null);
    try {
      const res = await api.evaluateDecision(merchantId, prompt.trim() || undefined);
      if (res && res.decision_id) {
        const fullDetail = await api.getDecisionDetail(res.decision_id, merchantId);
        setDetail(fullDetail);
        setStep('result');
        if (onDecisionCreated) {
          onDecisionCreated(res.decision_id);
        }
      } else {
        throw new Error('No decision returned from authoritative runtime.');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to evaluate buyer request through runtime.');
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleStartCheckout = async () => {
    if (!detail) return;
    setIsCheckingOut(true);
    setCheckoutError(null);
    setCheckoutSuccessMessage(null);

    try {
      // 1. Authoritative Boundary Traversal
      const execResult = await api.executeDecision(detail.decision_id, merchantId);

      if (!execResult.execution_authorized || execResult.boundary_status !== 'EXECUTION_COMPLETED') {
        const rejectionMsg =
          execResult.rejection_reasons?.join(', ') ||
          `Boundary execution rejected (${execResult.boundary_status})`;
        setCheckoutError(rejectionMsg);
        const updated = await api.getDecisionDetail(detail.decision_id, merchantId);
        setDetail(updated);
        return;
      }

      const razorpayOrderId = execResult.razorpay_order_id || detail.razorpay_order_id;
      const authorizedAmountPaise =
        execResult.authorized_amount_paise ||
        detail.authorized_amount_paise ||
        detail.buyer_offer.offer_price_paise;

      if (!razorpayOrderId) {
        throw new Error('No Razorpay Order ID returned from execution boundary.');
      }

      const keyId = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || 'rzp_test_TXLFfNuyfKpBqM';

      // 2. Razorpay Checkout Modal
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
            const updated = await api.getDecisionDetail(detail.decision_id, merchantId);
            setDetail(updated);
            setCheckoutSuccessMessage('Payment complete! Transaction reconciled in Test Mode.');
          },
          prefill: {
            name: 'AI Buyer Agent',
            email: 'ai.buyer@example.com',
            contact: '9999999999'
          },
          theme: { color: '#533afd' }
        };

        const rzp = new (window as any).Razorpay(options);
        rzp.open();
      } else {
        const checkoutUrl = `/test_checkout.html?key_id=${encodeURIComponent(keyId)}&order_id=${encodeURIComponent(razorpayOrderId)}&amount=${authorizedAmountPaise}`;
        window.open(checkoutUrl, '_blank', 'noopener,noreferrer');
      }
    } catch (err: any) {
      setCheckoutError(err.message || 'Failed to initiate checkout traversal');
    } finally {
      setIsCheckingOut(false);
    }
  };

  // Safe explanation derived strictly from positioning or rationale without COGS/margin leakage
  const getBuyerSafeExplanation = () => {
    if (!detail) return '';
    if (isNoOffer) {
      return "No current catalog option satisfies the buyer's stated requirements and merchant commercial boundaries.";
    }
    const rawExplanation =
      detail.merchant_evaluation?.rationale ||
      'Optimal match identified from merchant catalog adhering strictly to commercial boundaries.';
    // Filter out any accidental internal jargon
    const sanitized = rawExplanation
      .replace(/cogs\s*:\s*\d+/gi, '')
      .replace(/margin\s*:\s*[\d.]+%?/gi, '')
      .replace(/linucb/gi, 'evaluation')
      .replace(/predicted contribution\s*:\s*\d+/gi, '')
      .trim();

    return (
      sanitized ||
      `Product recommendation satisfies the buyer's ${detail.intent_summary?.category || 'catalog'} requirements within the authorized budget.`
    );
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="buyer-request-modal-title"
      data-testid="new-buyer-request-modal"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-[#061b31]/40 backdrop-blur-xs animate-in fade-in duration-200"
    >
      <div className="relative w-full max-w-2xl bg-white border border-[#e5edf5] rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#e5edf5] flex items-center justify-between bg-[#f8fafd]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#533afd]/10 text-[#533afd] flex items-center justify-center font-medium">
              <ShoppingBag className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 id="buyer-request-modal-title" className="text-base font-semibold text-[#061b31]">
                  {step === 'composer' ? 'What does the buyer want?' : 'Buyer Request Evaluation'}
                </h2>
                <span className="stripe-tag bg-white border border-[#e5edf5] text-[#533afd] font-mono text-[10px]">
                  {merchantId}
                </span>
                {step === 'result' && (
                  <span className="stripe-tag bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px]">
                    Evaluated
                  </span>
                )}
              </div>
              <p className="text-xs text-[#64748d]">
                {step === 'composer'
                  ? 'Describe the buyer inquiry or shopping context in natural language.'
                  : 'Authoritative autonomous proposal formulated by Canonical Decision Runtime.'}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1.5 rounded-lg hover:bg-[#e5edf5] text-[#64748d] hover:text-[#061b31] transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 text-xs text-[#061b31]">
          {error && (
            <div className="p-3.5 rounded-lg border border-rose-200 bg-rose-50 text-rose-800 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
              <div>
                <div className="font-medium text-xs">Evaluation Error</div>
                <div className="text-[11px] mt-0.5">{error}</div>
              </div>
            </div>
          )}

          {checkoutError && (
            <div className="p-3.5 rounded-lg border border-rose-200 bg-rose-50 text-rose-800 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
              <div>
                <div className="font-medium text-xs">Checkout Notice</div>
                <div className="text-[11px] mt-0.5">{checkoutError}</div>
              </div>
            </div>
          )}

          {checkoutSuccessMessage && (
            <div className="p-3.5 rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-800 flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5 text-emerald-600" />
              <div>
                <div className="font-medium text-xs">Checkout Success</div>
                <div className="text-[11px] mt-0.5">{checkoutSuccessMessage}</div>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* STEP 1: COMPOSER VIEW                                                     */}
          {/* ========================================================================= */}
          {step === 'composer' && (
            <div className="space-y-4">
              {/* Information Hygiene Banner */}
              <div className="flex items-center gap-2.5 px-3.5 py-2.5 bg-[#f8fafd] border border-[#e5edf5] rounded-lg text-xs text-[#50617a]">
                <ShieldCheck className="w-4 h-4 text-[#533afd] shrink-0" />
                <span>
                  <strong className="font-semibold text-[#061b31]">Information Hygiene:</strong> COGS, margins, and policy internals remain protected and are never exposed to buyer agents.
                </span>
              </div>

              <div>
                <label htmlFor="buyer-prompt-input" className="block text-xs font-medium text-[#061b31] mb-1.5">
                  Natural Language Buyer Utterance
                </label>
                <textarea
                  id="buyer-prompt-input"
                  rows={4}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="I need a high-quality travel backpack for a weekend trip under ₹7,500."
                  className="w-full text-xs p-3 border border-[#e5edf5] rounded-lg focus:outline-none focus:border-[#533afd] focus:ring-1 focus:ring-[#533afd] placeholder-[#94a3b8] resize-none leading-relaxed"
                />
              </div>

              {/* Preset Chips */}
              <div>
                <div className="text-[11px] font-medium text-[#64748d] uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-[#533afd]" />
                  <span>Sample Buyer Inquiries (Click to populate)</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {CANONICAL_PRESETS.map((preset, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setPrompt(preset.prompt)}
                      className="text-left p-2.5 rounded-lg border border-[#e5edf5] hover:border-[#533afd] hover:bg-[#f8fafd] transition-all group cursor-pointer"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-[#061b31] text-[11px] group-hover:text-[#533afd]">
                          {preset.label}
                        </span>
                        <span className="text-[9px] px-1.5 py-0.5 bg-[#f1f5f9] text-[#64748d] rounded font-mono">
                          {preset.intentTag}
                        </span>
                      </div>
                      <p className="text-[10px] text-[#64748d] mt-1 line-clamp-1">
                        "{preset.prompt}"
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Information Hygiene Guarantee Note */}
              <div className="p-3 bg-[#f8fafd] border border-[#e5edf5] rounded-lg flex items-center gap-2.5 text-[11px] text-[#64748d]">
                <ShieldCheck className="w-4 h-4 text-[#059669] shrink-0" />
                <span>
                  The request evaluates against <strong>{merchantId}</strong> authoritative catalog, active policy constraints, and real-time inventory. Merchant unit costs (COGS) and profit margins are never leaked to buyer agents.
                </span>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* STEP 2: EVALUATION RESULT VIEW                                            */}
          {/* ========================================================================= */}
          {step === 'result' && detail && (
            <div className="space-y-4">
              {/* Identifiers Strip */}
              <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 bg-[#f8fafd] border border-[#e5edf5] rounded-lg text-[11px]">
                <div className="flex items-center gap-3 font-mono">
                  <span className="text-[#64748d]">DECISION:</span>
                  <button
                    onClick={() => copyToClipboard(detail.decision_id, 'dec')}
                    className="font-medium text-[#533afd] hover:underline flex items-center gap-1 cursor-pointer"
                    title="Click to copy decision ID"
                  >
                    <span>{detail.decision_id}</span>
                    {copiedId === 'dec' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                  </button>
                </div>
                <div className="flex items-center gap-2 text-[#64748d]">
                  <span>Mode:</span>
                  <span className="stripe-tag bg-white border border-[#e5edf5] font-semibold text-[#061b31]">
                    {detail.merchant_evaluation?.decision_mode || 'EXPLOIT'}
                  </span>
                  <span>Evaluated:</span>
                  <span className="text-[#061b31] font-mono">{formatDateTime(detail.created_at)}</span>
                </div>
              </div>

              {/* SECTION A — WHAT THE BUYER ASKED FOR */}
              <div className="space-y-1.5">
                <div className="text-[11px] font-semibold text-[#64748d] uppercase tracking-wider">
                  Section A — Original Buyer Request (What the Buyer Asked For)
                </div>
                <div className="p-3 rounded-lg border border-[#e5edf5] bg-[#fafcff] text-xs text-[#061b31] italic font-serif flex items-start gap-2">
                  <span className="text-lg leading-none text-[#533afd]">“</span>
                  <span className="flex-1 font-sans text-xs not-italic text-[#1e293b]">
                    {prompt || detail.raw_prompt || 'High quality travel backpack for weekend travel under 7500'}
                  </span>
                  <span className="text-lg leading-none text-[#533afd]">”</span>
                </div>
              </div>

              {/* SECTION B — WHAT WE UNDERSTOOD */}
              <div className="space-y-1.5">
                <div className="text-[11px] font-semibold text-[#64748d] uppercase tracking-wider">
                  Section B — What We Understood (Buyer Intent)
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  <div className="p-2.5 rounded-lg border border-[#e5edf5] bg-white">
                    <div className="text-[10px] text-[#64748d] uppercase font-medium">Category</div>
                    <div className="font-medium text-[#061b31] mt-0.5 capitalize truncate">
                      {detail.intent_summary?.category || detail.buyer_context_key.replace(/^bck_/, '').split('_')[0] || 'Travel Backpack'}
                    </div>
                  </div>

                  <div className="p-2.5 rounded-lg border border-[#e5edf5] bg-white">
                    <div className="text-[10px] text-[#64748d] uppercase font-medium">Budget Ceiling</div>
                    <div className="font-semibold text-[#061b31] mt-0.5">
                      {detail.intent_summary?.budget_paise
                        ? formatPaise(detail.intent_summary.budget_paise)
                        : 'No limit specified'}
                    </div>
                  </div>

                  <div className="p-2.5 rounded-lg border border-[#e5edf5] bg-white">
                    <div className="text-[10px] text-[#64748d] uppercase font-medium">Preferences</div>
                    <div className="font-medium text-[#061b31] mt-0.5 truncate" title={detail.intent_summary?.preferences?.join(', ') || 'High Quality'}>
                      {detail.intent_summary?.preferences?.length
                        ? detail.intent_summary.preferences.join(', ')
                        : 'High Quality, Durable'}
                    </div>
                  </div>

                  <div className="p-2.5 rounded-lg border border-[#e5edf5] bg-white">
                    <div className="text-[10px] text-[#64748d] uppercase font-medium">Use Case / Context</div>
                    <div className="font-medium text-[#061b31] mt-0.5 truncate" title={detail.intent_summary?.use_case || 'Weekend Travel'}>
                      {detail.intent_summary?.use_case || 'Weekend Travel'}
                    </div>
                  </div>
                </div>
              </div>

              {/* SECTION C — RECOMMENDED OFFER */}
              <div className="space-y-1.5">
                <div className="text-[11px] font-semibold text-[#64748d] uppercase tracking-wider">
                  Section C — Recommended Commercial Offer
                </div>

                {isNoOffer ? (
                  <div className="p-4 rounded-lg border border-amber-200 bg-amber-50 text-amber-900 space-y-1">
                    <div className="font-semibold text-xs flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 text-amber-600" />
                      <span>No Safe Offer Available</span>
                    </div>
                    <p className="text-[11px] text-amber-800 leading-relaxed">
                      The autonomous policy engine determined that no eligible catalog item satisfies the buyer's constraints without violating merchant margin floors or inventory requirements.
                    </p>
                  </div>
                ) : (
                  <div className="p-4 rounded-lg border border-[#e5edf5] bg-white shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm text-[#061b31]">
                          {detail.buyer_offer?.offer_title || 'Atlas Travel Gear Package'}
                        </span>
                        <span className="stripe-tag bg-[#f4f5fe] border border-[#d6d9fd] text-[#533afd] text-[10px]">
                          {detail.buyer_offer?.strategy_type || 'SINGLE_PRODUCT'}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#64748d]">
                        <span className="flex items-center gap-1">
                          <PackageCheck className="w-3.5 h-3.5 text-emerald-600" />
                          <span>{detail.buyer_offer?.delivery_days || 2}-day delivery</span>
                        </span>
                        <span>•</span>
                        <span>{detail.buyer_offer?.warranty_months || 12}-month warranty</span>
                        {detail.buyer_offer?.product_ids && detail.buyer_offer.product_ids.length > 1 && (
                          <>
                            <span>•</span>
                            <span className="font-mono text-[#533afd]">
                              {detail.buyer_offer.product_ids.length} items bundled
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <div className="text-[10px] text-[#64748d] uppercase font-medium">Customer Price</div>
                      <div className="text-2xl font-semibold text-[#061b31] font-mono tracking-tight">
                        {formatPaise(detail.buyer_offer?.offer_price_paise)}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* SECTION D — WHY THIS OFFER */}
              <div className="space-y-1.5">
                <div className="text-[11px] font-semibold text-[#64748d] uppercase tracking-wider">
                  Section D — Decision Rationale (Buyer-Safe)
                </div>
                <div className="p-3 rounded-lg border border-[#e5edf5] bg-[#f8fafd] text-[11px] text-[#475569] leading-relaxed">
                  {getBuyerSafeExplanation()}
                </div>
              </div>

              {/* SECTION E — SAFETY & CHECKOUT READINESS */}
              <div className="space-y-1.5">
                <div className="text-[11px] font-semibold text-[#64748d] uppercase tracking-wider">
                  Section E — Merchant Control & Execution Gate
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-2.5 rounded-lg border border-[#e5edf5] bg-white flex items-center justify-between">
                    <div>
                      <div className="text-[10px] text-[#64748d] uppercase font-medium">Safety Evaluation</div>
                      <div className="font-semibold text-emerald-700 mt-0.5 flex items-center gap-1">
                        {detail.safety_status === 'ADMISSIBLE' ? (
                          <>
                            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                            <span>ADMISSIBLE</span>
                          </>
                        ) : (
                          <>
                            <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                            <span className="text-rose-700">{detail.safety_status}</span>
                          </>
                        )}
                      </div>
                    </div>
                    <span className="text-[10px] text-[#64748d] font-mono">Phase 8.6</span>
                  </div>

                  <div className="p-2.5 rounded-lg border border-[#e5edf5] bg-white flex items-center justify-between">
                    <div>
                      <div className="text-[10px] text-[#64748d] uppercase font-medium">Checkout Readiness</div>
                      <div className="font-semibold mt-0.5">
                        {isAlreadyPaid ? (
                          <span className="text-emerald-700 flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>PAYMENT COMPLETED</span>
                          </span>
                        ) : isStaleByTtl ? (
                          <span className="text-amber-700 flex items-center gap-1">
                            <Clock className="w-3.5 h-3.5" />
                            <span>DECISION EXPIRED</span>
                          </span>
                        ) : isNoOffer ? (
                          <span className="text-slate-600">NO OFFER APPLICABLE</span>
                        ) : isExecutable ? (
                          <span className="text-[#533afd] flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5 text-[#533afd]" />
                            <span>READY FOR CHECKOUT</span>
                          </span>
                        ) : (
                          <span className="text-[#64748d]">{detail.execution_status}</span>
                        )}
                      </div>
                    </div>
                    <span className="text-[10px] text-[#64748d] font-mono">Phase 9.2</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-[#e5edf5] bg-[#f8fafd] flex flex-wrap items-center justify-between gap-3">
          {step === 'composer' ? (
            <>
              <button
                type="button"
                onClick={onClose}
                className="stripe-btn-ghost text-xs px-3 py-1.5 cursor-pointer"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleEvaluate}
                disabled={isEvaluating || !prompt.trim()}
                className="stripe-btn-primary flex items-center gap-1.5 text-xs bg-[#533afd] hover:bg-[#432ec7] text-white px-4 py-2 rounded-lg shadow-sm transition-colors disabled:opacity-50 cursor-pointer"
              >
                <Sparkles className={`w-3.5 h-3.5 ${isEvaluating ? 'animate-spin' : ''}`} />
                <span>{isEvaluating ? 'Evaluating Request...' : 'Evaluate Request'}</span>
              </button>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setStep('composer')}
                  className="stripe-btn-ghost text-xs px-3 py-1.5 cursor-pointer flex items-center gap-1"
                >
                  <span>← Edit Request</span>
                </button>

                {onOpenFullTrace && detail && (
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      onOpenFullTrace(detail.decision_id);
                    }}
                    className="stripe-btn-ghost text-xs px-3 py-1.5 cursor-pointer flex items-center gap-1 text-[#533afd] hover:bg-[#f4f5fe]"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>View Full Decision Trace</span>
                  </button>
                )}
              </div>

              <div className="flex items-center gap-2">
                {isAlreadyPaid ? (
                  <div className="stripe-tag bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs px-3 py-1.5 font-medium flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>PAID (Test Mode)</span>
                  </div>
                ) : isStaleByTtl ? (
                  <button
                    type="button"
                    onClick={handleEvaluate}
                    disabled={isEvaluating}
                    className="stripe-btn-primary flex items-center gap-1.5 text-xs bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-lg cursor-pointer"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isEvaluating ? 'animate-spin' : ''}`} />
                    <span>Evaluate Fresh Request</span>
                  </button>
                ) : isExecutable ? (
                  <button
                    type="button"
                    onClick={handleStartCheckout}
                    disabled={isCheckingOut}
                    className="stripe-btn-primary flex items-center gap-1.5 text-xs bg-[#533afd] hover:bg-[#432ec7] text-white px-4 py-2 rounded-lg shadow-sm transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    <ShoppingBag className={`w-3.5 h-3.5 ${isCheckingOut ? 'animate-spin' : ''}`} />
                    <span>{isCheckingOut ? 'Traversing Boundary...' : 'Open Test Checkout'}</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={onClose}
                    className="stripe-btn-ghost text-xs px-3 py-1.5 cursor-pointer"
                  >
                    Close
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
