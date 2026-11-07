'use client';

import React, { useState, useEffect } from 'react';
import { Search, Filter, RefreshCw, Cpu, ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';
import { useMerchant } from '@/lib/MerchantContext';
import { api, formatPaise, formatDateTime, getExecutionStatusBadge, getOutcomeStatusBadge } from '@/lib/api';
import { DecisionListResponse } from '@/lib/types';
import { DecisionDetailDrawer } from '@/components/decisions/DecisionDetailDrawer';
import { NewBuyerRequestModal } from '@/components/decisions/NewBuyerRequestModal';

export default function DecisionsPage() {
  const { currentMerchant } = useMerchant();
  const [data, setData] = useState<DecisionListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isNewBuyerModalOpen, setIsNewBuyerModalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDecisionId, setSelectedDecisionId] = useState<string | null>(null);

  // Filters & Pagination
  const [modeFilter, setModeFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [page, setPage] = useState(0);
  const limit = 20;

  const loadDecisions = () => {
    setLoading(true);
    setError(null);
    api.getDecisions(currentMerchant.id, {
      limit,
      offset: page * limit,
      mode: modeFilter !== 'ALL' ? modeFilter : undefined,
      status: statusFilter !== 'ALL' ? statusFilter : undefined
    })
      .then((res) => setData(res))
      .catch((err) => setError(err.message || 'Failed to load decisions'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDecisions();
  }, [currentMerchant.id, modeFilter, statusFilter, page]);

  // Real-time diversity summary derived strictly from authoritative loaded items
  const uniqueStrategies = Array.from(new Set(data?.items.map((i) => i.selected_strategy_type) || []));
  const uniqueModes = Array.from(new Set(data?.items.map((i) => i.decision_mode) || []));
  const uniqueExecutionStatuses = Array.from(new Set(data?.items.map((i) => i.execution_status) || []));
  const uniqueOutcomes = Array.from(new Set(data?.items.map((i) => i.outcome_status || 'NOT_REACHED') || []));

  return (
    <div className="w-full px-2 sm:px-4 md:px-6 py-4 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="stripe-tag bg-[#f8fafd] border border-[#e5edf5] text-[#533afd] font-mono text-[11px]">
              TENANT: {currentMerchant.id}
            </span>
            <span className="text-xs text-[#64748d]">Total Evaluated: {data?.total ?? 0}</span>
          </div>
          <h1 className="text-3xl font-light text-[#061b31] tracking-tight mt-1.5">
            AI Decisions Ledger
          </h1>
          <p className="text-sm text-[#50617a] font-normal mt-1 leading-relaxed">
            Every autonomous policy proposal evaluated by Canonical Decision Runtime with full 11-stage lineage and strictly separated buyer vs merchant economics.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsNewBuyerModalOpen(true)}
            className="stripe-btn-primary flex items-center gap-1.5 text-xs bg-[#533afd] hover:bg-[#432ec7] text-white px-3 py-1.5 rounded-lg shadow-sm transition-colors cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>+ New Buyer Request</span>
          </button>
          <button
            onClick={loadDecisions}
            disabled={loading}
            className="stripe-btn-ghost flex items-center gap-1.5 text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Live Diversity Indicator Bar */}
      {data?.items && data.items.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-white border border-[#e5edf5] rounded-lg p-3 shadow-xs">
            <div className="text-[11px] font-medium text-[#64748d] uppercase tracking-wider">Strategies Active</div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-xl font-semibold text-[#061b31]">{uniqueStrategies.length}</span>
              <span className="text-[11px] text-[#533afd] font-medium">Commercial Archetypes</span>
            </div>
            <div className="mt-1 text-[11px] text-[#64748d] truncate" title={uniqueStrategies.join(', ')}>
              {uniqueStrategies.join(', ')}
            </div>
          </div>

          <div className="bg-white border border-[#e5edf5] rounded-lg p-3 shadow-xs">
            <div className="text-[11px] font-medium text-[#64748d] uppercase tracking-wider">Decision Modes</div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-xl font-semibold text-[#061b31]">{uniqueModes.length}</span>
              <span className="text-[11px] text-[#059669] font-medium">LinUCB Balance</span>
            </div>
            <div className="mt-1 text-[11px] text-[#64748d] truncate">
              {uniqueModes.join(' & ')}
            </div>
          </div>

          <div className="bg-white border border-[#e5edf5] rounded-lg p-3 shadow-xs">
            <div className="text-[11px] font-medium text-[#64748d] uppercase tracking-wider">Execution States</div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-xl font-semibold text-[#061b31]">{uniqueExecutionStatuses.length}</span>
              <span className="text-[11px] text-[#d97706] font-medium">Gate Lifecycles</span>
            </div>
            <div className="mt-1 text-[11px] text-[#64748d] truncate">
              Completed, Pending, Rejected
            </div>
          </div>

          <div className="bg-white border border-[#e5edf5] rounded-lg p-3 shadow-xs">
            <div className="text-[11px] font-medium text-[#64748d] uppercase tracking-wider">Commercial Outcomes</div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-xl font-semibold text-[#061b31]">{uniqueOutcomes.length}</span>
              <span className="text-[11px] text-[#2563eb] font-medium">Reconciled Streams</span>
            </div>
            <div className="mt-1 text-[11px] text-[#64748d] truncate">
              Paid, Failed, Open
            </div>
          </div>
        </div>
      )}

      {/* Filter Bar */}
      <div className="stripe-card p-3 flex items-center justify-between gap-4 text-xs">
        <div className="flex items-center gap-3">
          <span className="text-[#64748d] flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" />
            <span>Filter:</span>
          </span>

          <select
            value={modeFilter}
            onChange={(e) => {
              setModeFilter(e.target.value);
              setPage(0);
            }}
            className="border border-[#e5edf5] rounded px-2.5 py-1 bg-white text-[#061b31] focus:outline-none focus:border-[#533afd]"
          >
            <option value="ALL">All Modes (Explore & Exploit)</option>
            <option value="EXPLOIT">EXPLOIT Only</option>
            <option value="EXPLORE">EXPLORE Only</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(0);
            }}
            className="border border-[#e5edf5] rounded px-2.5 py-1 bg-white text-[#061b31] focus:outline-none focus:border-[#533afd]"
          >
            <option value="ALL">All Execution States</option>
            <option value="EXECUTION_COMPLETED">EXECUTION_COMPLETED</option>
            <option value="PENDING_EXECUTION_GATE">PENDING_EXECUTION_GATE</option>
            <option value="EXECUTION_REJECTED">EXECUTION_REJECTED / SAFETY_REJECTED</option>
          </select>
        </div>

        <div className="text-xs text-[#64748d] font-mono">
          Showing {data?.items.length ?? 0} of {data?.total ?? 0}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded border border-rose-200 bg-rose-50 text-xs text-rose-800">
          {error}
        </div>
      )}

      {/* Decisions Table Card */}
      <div className="stripe-card overflow-hidden border border-[#e5edf5] rounded-lg bg-white shadow-sm">
        {/* Table Horizontal Scroll Container */}
        <div className="w-full overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse min-w-[920px]">
            <thead>
              <tr className="bg-[#f8fafd] border-b border-[#e5edf5] text-[#64748d] text-[11px] uppercase tracking-wider font-medium">
                <th className="py-3 px-3 sticky left-0 bg-[#f8fafd] z-10 shadow-[1px_0_0_0_#e5edf5] whitespace-nowrap w-[120px]">
                  Decision ID
                </th>
                <th className="py-3 px-2 whitespace-nowrap w-[110px]">Opportunity ID</th>
                <th className="py-3 px-2 whitespace-nowrap w-[125px]">Buyer Context</th>
                <th className="py-3 px-2 whitespace-nowrap w-[115px]">Strategy</th>
                <th className="py-3 px-1.5 text-center whitespace-nowrap w-[65px]">Mode</th>
                <th className="py-3 px-2 text-right whitespace-nowrap w-[80px]">Proposed Price</th>
                <th className="py-3 px-2 text-center whitespace-nowrap w-[145px]">Execution Status</th>
                <th className="py-3 px-2 text-center whitespace-nowrap w-[110px]">Outcome</th>
                <th className="py-3 pr-3 pl-2 text-right whitespace-nowrap w-[95px]">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e5edf5]">
              {loading ? (
                <tr>
                  <td colSpan={9} className="p-8 text-center text-[#64748d]">
                    Loading authoritative decisions...
                  </td>
                </tr>
              ) : data?.items && data.items.length > 0 ? (
                data.items.map((dec) => (
                  <tr
                    key={dec.decision_id}
                    tabIndex={0}
                    role="button"
                    aria-label={`Inspect decision ${dec.decision_id}`}
                    onClick={() => setSelectedDecisionId(dec.decision_id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSelectedDecisionId(dec.decision_id);
                      }
                    }}
                    className="group hover:bg-[#f8fafd] cursor-pointer transition-colors focus-visible:outline-none focus-visible:bg-[#f4f5fe]"
                  >
                    <td className="py-2.5 px-3 font-mono text-[#533afd] font-medium whitespace-nowrap sticky left-0 bg-white group-hover:bg-[#f8fafd] group-focus-visible:bg-[#f4f5fe] z-10 shadow-[1px_0_0_0_#e5edf5]">
                      {dec.decision_id}
                    </td>
                    <td className="py-2.5 px-2 font-mono text-[#64748d]">
                      <span className="block max-w-[105px] truncate" title={dec.opportunity_id}>
                        {dec.opportunity_id}
                      </span>
                    </td>
                    <td className="py-2.5 px-2 font-mono text-[#50617a] text-[11px]">
                      <span
                        className="block max-w-[120px] truncate hover:text-[#061b31]"
                        title={dec.buyer_context_key}
                      >
                        {dec.buyer_context_key}
                      </span>
                    </td>
                    <td className="py-2.5 px-2 text-[#061b31] whitespace-nowrap font-medium text-[11px]">
                      {dec.selected_strategy_type}
                    </td>
                    <td className="py-2.5 px-1.5 text-center whitespace-nowrap">
                      <span className="stripe-tag bg-[#e8e9ff] text-[#533afd] text-[10px] font-medium px-2 py-0.5">
                        {dec.decision_mode}
                      </span>
                    </td>
                    <td className="py-2.5 px-2 text-right font-medium text-[#061b31] tabular-nums whitespace-nowrap">
                      {formatPaise(dec.proposed_price_paise)}
                    </td>
                    <td className="py-2.5 px-2 text-center whitespace-nowrap">
                      {(() => {
                        const badge = getExecutionStatusBadge(dec.execution_status);
                        return (
                          <span className={`stripe-tag ${badge.className} text-[10px] px-2 py-0.5 whitespace-nowrap`}>
                            {badge.label}
                          </span>
                        );
                      })()}
                    </td>
                    <td className="py-2.5 px-2 text-center whitespace-nowrap">
                      {(() => {
                        const badge = getOutcomeStatusBadge(dec.outcome_status);
                        return badge ? (
                          <span className={`stripe-tag ${badge.className} text-[10px] px-2 py-0.5 whitespace-nowrap`}>
                            {badge.label}
                          </span>
                        ) : (
                          <span className="text-[#839bc8] text-[10px]">—</span>
                        );
                      })()}
                    </td>
                    <td className="py-2.5 pr-3 pl-2 text-right text-[#64748d] font-mono text-[10px] whitespace-nowrap">
                      {formatDateTime(dec.created_at)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={9} className="p-8 text-center text-[#64748d]">
                    No decisions matching current filter criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer - Fixed to card bottom, not scrolled with table */}
        {data && data.total > limit && (
          <div className="p-3 border-t border-[#e5edf5] flex items-center justify-between bg-[#f8fafd] text-xs">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="stripe-btn-ghost px-2 py-1 disabled:opacity-40"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              <span>Previous</span>
            </button>
            <span className="text-[#64748d]">
              Page {page + 1} of {Math.ceil(data.total / limit)}
            </span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * limit >= data.total}
              className="stripe-btn-ghost px-2 py-1 disabled:opacity-40"
            >
              <span>Next</span>
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Decision Detail Drawer */}
      <DecisionDetailDrawer
        decisionId={selectedDecisionId}
        merchantId={currentMerchant.id}
        onClose={() => setSelectedDecisionId(null)}
      />

      {/* New Buyer Request Modal */}
      <NewBuyerRequestModal
        isOpen={isNewBuyerModalOpen}
        merchantId={currentMerchant.id}
        onClose={() => setIsNewBuyerModalOpen(false)}
        onDecisionCreated={() => loadDecisions()}
        onOpenFullTrace={(decisionId) => {
          setIsNewBuyerModalOpen(false);
          setSelectedDecisionId(decisionId);
        }}
      />
    </div>
  );
}
