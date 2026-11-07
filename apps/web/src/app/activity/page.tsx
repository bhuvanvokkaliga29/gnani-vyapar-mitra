'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  History,
  Search,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Copy,
  Check,
  ChevronDown,
  ChevronRight,
  ArrowRight
} from 'lucide-react';
import { useMerchant } from '@/lib/MerchantContext';
import { api, formatDateTime } from '@/lib/api';
import { ActivityListResponse, OpportunityTrace } from '@/lib/types';

export default function ActivityPage() {
  return (
    <Suspense fallback={<div className="p-8 text-xs text-[#64748d]">Loading activity inspector...</div>}>
      <ActivityContent />
    </Suspense>
  );
}

function ActivityContent() {
  const { currentMerchant } = useMerchant();
  const searchParams = useSearchParams();
  const initialSearch = searchParams?.get('search') || '';

  const [searchId, setSearchId] = useState(initialSearch);
  const [traceData, setTraceData] = useState<OpportunityTrace | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const [traceError, setTraceError] = useState<string | null>(null);

  const [activityData, setActivityData] = useState<ActivityListResponse | null>(null);
  const [activityLoading, setActivityLoading] = useState(true);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const loadActivity = () => {
    setActivityLoading(true);
    setActivityError(null);
    api.getActivity(currentMerchant.id, { limit: 50, offset: 0 })
      .then((res) => setActivityData(res))
      .catch((err) => setActivityError(err.message || 'Failed to load activity log'))
      .finally(() => setActivityLoading(false));
  };

  const handleTraceLookup = (idToLookup?: string) => {
    const target = idToLookup || searchId.trim();
    if (!target) return;
    setTraceLoading(true);
    setTraceError(null);
    api.getTrace(target, currentMerchant.id)
      .then((res) => setTraceData(res))
      .catch((err) => {
        setTraceError(err.message || `No trace found for identifier "${target}" within tenant boundary.`);
        setTraceData(null);
      })
      .finally(() => setTraceLoading(false));
  };

  useEffect(() => {
    loadActivity();
    if (initialSearch) {
      handleTraceLookup(initialSearch);
    }
  }, [currentMerchant.id]);

  const copyToClipboard = (text?: string | null, key?: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedId(key || text);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="w-full px-2 sm:px-4 md:px-6 py-4 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="stripe-tag bg-[#f8fafd] border border-[#e5edf5] text-[#533afd] font-mono text-[11px]">
              TENANT: {currentMerchant.id}
            </span>
            <span className="text-xs text-[#64748d]">Phase 9.4 Authoritative Audit & Traceability</span>
          </div>
          <h1 className="text-3xl font-light text-[#061b31] tracking-tight mt-1.5">
            Operational Activity & Trace Inspector
          </h1>
          <p className="text-sm text-[#50617a] font-normal mt-1 leading-relaxed">
            Reconstruct end-to-end commercial execution journeys and inspect immutable tenant audit records with precise stopping point diagnoses.
          </p>
        </div>

        <button
          onClick={loadActivity}
          disabled={activityLoading}
          className="stripe-btn-ghost flex items-center gap-1.5 text-xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${activityLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Log</span>
        </button>
      </div>

      {/* Trace Inspector Section */}
      <div className="stripe-card p-6 space-y-5 bg-gradient-to-b from-[#f8fafd] to-white">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-sm font-medium text-[#061b31]">Opportunity Trace Reconstruction</h3>
            <p className="text-xs text-[#64748d] mt-0.5">
              Enter any Opportunity ID, Decision ID, or Order ID to inspect complete cross-phase progression.
            </p>
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleTraceLookup();
          }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 text-[#839bc8] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="e.g. opp_alpha_01 or dec_24c9f06e44cd"
              value={searchId}
              onChange={(e) => setSearchId(e.target.value)}
              className="w-full bg-white border border-[#e5edf5] rounded pl-9 pr-3 py-2 text-xs font-mono text-[#061b31] focus:outline-none focus:border-[#533afd]"
            />
          </div>
          <button
            type="submit"
            disabled={traceLoading || !searchId.trim()}
            className="stripe-btn-primary text-xs px-4"
          >
            {traceLoading ? 'Tracing...' : 'Reconstruct Trace'}
          </button>
        </form>

        {traceError && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded text-xs text-rose-800 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{traceError}</span>
          </div>
        )}

        {traceData && (
          <div className="p-4 bg-white border border-[#d6d9fc] rounded space-y-4">
            <div className="flex justify-between items-start">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-medium text-[#533afd]">{traceData.opportunity_id}</span>
                  <button onClick={() => copyToClipboard(traceData.opportunity_id, 'trace_opp')}>
                    {copiedId === 'trace_opp' ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3 text-[#64748d]" />}
                  </button>
                </div>
                <div className="text-xs text-[#64748d] mt-1">Audit Events Linked: {traceData.audit_event_count}</div>
              </div>

              <div className="text-right">
                <span
                  className={`stripe-tag text-[10px] font-medium ${
                    traceData.trace_status === 'COMPLETED'
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-amber-50 text-amber-700 border border-amber-200'
                  }`}
                >
                  {traceData.trace_status}
                </span>
                {traceData.stopped_reason && (
                  <div className="text-[11px] text-amber-800 mt-1 font-medium">
                    {traceData.stopped_reason}
                  </div>
                )}
              </div>
            </div>

            {/* Stages Grid */}
            <div className="pt-3 border-t border-[#e5edf5]">
              <div className="text-[11px] text-[#64748d] font-medium uppercase tracking-wider mb-2">Reconstructed Pipeline Stages</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                {[
                  { label: 'Decision (9.1)', id: traceData.decision_id, tag: '9.1_DECISION' },
                  { label: 'Execution (9.2)', id: traceData.execution_id, tag: '9.2_EXECUTION' },
                  { label: 'Order (Phase 5)', id: traceData.order_id, tag: '5.0_ORDER' },
                  { label: 'Payment (Phase 5)', id: traceData.payment_id, tag: '5.0_PAYMENT' },
                  { label: 'Outcome (9.3)', id: traceData.outcome_id, tag: '9.3_OUTCOME' },
                  { label: 'Evidence (8.1)', id: traceData.evidence_id, tag: '8.1_EVIDENCE' },
                  { label: 'Memory (8.3)', id: traceData.memory_id, tag: '8.3_MEMORY' },
                  { label: 'Model (8.4)', id: traceData.applied_observation_id, tag: '8.4_MODEL_UPDATE' },
                ].map((s) => {
                  const isPresent = traceData.stages_present.includes(s.tag);
                  return (
                    <div
                      key={s.label}
                      className={`p-2.5 rounded border ${
                        isPresent ? 'bg-[#f8fafd] border-[#e5edf5]' : 'bg-white border-dashed border-[#e5edf5] opacity-50'
                      }`}
                    >
                      <div className="flex justify-between items-center">
                        <span className="text-[10px] text-[#64748d] font-sans">{s.label}</span>
                        {isPresent ? (
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                        ) : (
                          <span className="text-[9px] text-[#839bc8]">Pending</span>
                        )}
                      </div>
                      <div className="font-mono text-[11px] font-medium text-[#061b31] truncate mt-1">
                        {s.id || '—'}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Unified Audit Trail Table */}
      <div className="stripe-card overflow-hidden">
        <div className="p-5 border-b border-[#e5edf5] flex justify-between items-center">
          <div>
            <h3 className="text-sm font-medium text-[#061b31]">Authoritative Audit Trail</h3>
            <p className="text-xs text-[#64748d] mt-0.5">
              Immutable records of every domain transition, policy modification, and execution clearance.
            </p>
          </div>
          <div className="text-xs text-[#64748d] font-mono">
            Total Events: {activityData?.total ?? 0}
          </div>
        </div>

        {activityError && (
          <div className="p-4 bg-rose-50 text-rose-800 text-xs border-b border-rose-200">
            {activityError}
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-[#f8fafd] border-b border-[#e5edf5] text-[#64748d]">
                <th className="p-3">Audit ID</th>
                <th className="p-3">Timestamp</th>
                <th className="p-3">Entity Type</th>
                <th className="p-3">Action</th>
                <th className="p-3">Opportunity</th>
                <th className="p-3">Summary</th>
                <th className="p-3 text-right">Details</th>
              </tr>
            </thead>
            <tbody>
              {activityLoading ? (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-[#64748d]">
                    Loading audit events...
                  </td>
                </tr>
              ) : activityData?.items && activityData.items.length > 0 ? (
                activityData.items.map((evt) => (
                  <React.Fragment key={evt.audit_event_id}>
                    <tr className="border-b border-[#e5edf5] hover:bg-[#f8fafd] transition-colors">
                      <td className="p-3 font-mono font-medium text-[#533afd] text-[11px]">{evt.audit_event_id}</td>
                      <td className="p-3 font-mono text-[#64748d] text-[11px]">{formatDateTime(evt.timestamp)}</td>
                      <td className="p-3">
                        <span className="stripe-tag bg-[#f8fafd] border border-[#e5edf5] text-[#50617a] text-[10px]">
                          {evt.entity_type}
                        </span>
                      </td>
                      <td className="p-3 font-mono text-[11px] font-medium text-[#061b31]">{evt.action}</td>
                      <td className="p-3 font-mono text-[#64748d] text-[11px]">
                        {evt.opportunity_id ? (
                          <button
                            onClick={() => {
                              setSearchId(evt.opportunity_id || '');
                              handleTraceLookup(evt.opportunity_id || '');
                            }}
                            className="text-[#533afd] hover:underline"
                          >
                            {evt.opportunity_id}
                          </button>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="p-3 text-[#50617a] max-w-xs truncate">{evt.summary}</td>
                      <td className="p-3 text-right">
                        <button
                          onClick={() => setExpandedEventId(expandedEventId === evt.audit_event_id ? null : evt.audit_event_id)}
                          className="stripe-btn-ghost text-xs py-0.5 px-2"
                        >
                          {expandedEventId === evt.audit_event_id ? 'Hide' : 'Inspect'}
                        </button>
                      </td>
                    </tr>
                    {expandedEventId === evt.audit_event_id && (
                      <tr className="bg-[#f8fafd] border-b border-[#e5edf5]">
                        <td colSpan={7} className="p-4">
                          <div className="text-[11px] font-mono bg-white p-3 rounded border border-[#e5edf5] overflow-x-auto text-[#061b31]">
                            <pre>{JSON.stringify(evt.details, null, 2)}</pre>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-[#64748d]">
                    No audit records logged yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
