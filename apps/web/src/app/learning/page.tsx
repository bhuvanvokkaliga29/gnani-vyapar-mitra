'use client';

import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  RefreshCw,
  ShieldCheck,
  Cpu,
  ArrowRight,
  Layers,
  Database,
  CheckCircle2,
  Lock
} from 'lucide-react';
import { useMerchant } from '@/lib/MerchantContext';
import { api, formatPaise, formatDateTime } from '@/lib/api';
import { LearningCenter } from '@/lib/types';

export default function LearningPage() {
  const { currentMerchant } = useMerchant();
  const [data, setData] = useState<LearningCenter | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadLearning = () => {
    setLoading(true);
    setError(null);
    api.getLearning(currentMerchant.id)
      .then((res) => setData(res))
      .catch((err) => setError(err.message || 'Failed to load learning center'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadLearning();
  }, [currentMerchant.id]);

  return (
    <div className="w-full px-2 sm:px-4 md:px-6 py-4 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="stripe-tag bg-[#f8fafd] border border-[#e5edf5] text-[#533afd] font-mono text-[11px]">
              TENANT: {currentMerchant.id}
            </span>
            <span className="text-xs text-[#64748d]">Phase 8 Closed-Loop Reinforcement Learning</span>
          </div>
          <h1 className="text-3xl font-light text-[#061b31] tracking-tight mt-1.5">
            Continuous Learning Center
          </h1>
          <p className="text-sm text-[#50617a] font-normal mt-1 leading-relaxed">
            How settled commercial outcomes safely update the LinUCB bandit model through evidence firewalls, admissible rewards, and partitioned memory.
          </p>
        </div>

        <button
          onClick={loadLearning}
          disabled={loading}
          className="stripe-btn-ghost flex items-center gap-1.5 text-xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded border border-rose-200 bg-rose-50 text-xs text-rose-800">
          {error}
        </div>
      )}

      {/* Closed-Loop Pipeline Diagram */}
      <div className="stripe-card p-6 bg-gradient-to-b from-[#f8fafd] to-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[#533afd]" />
            <h3 className="text-sm font-medium text-[#061b31]">The Continuous Learning Loop</h3>
          </div>
          <span className="stripe-tag bg-[#e8e9ff] text-[#533afd] text-[10px] font-medium">
            EXACTLY-ONCE GUARANTEE
          </span>
        </div>

        <div className="grid grid-cols-6 gap-2 text-xs">
          <div className="p-3 bg-white border border-[#e5edf5] rounded flex flex-col justify-between">
            <div>
              <div className="text-[10px] font-medium text-[#533afd]">1. Outcome</div>
              <div className="text-[11px] font-medium text-[#061b31] mt-1">Transaction Settled</div>
              <div className="text-[10px] text-[#64748d] mt-1">Phase 5 payment captured or failed</div>
            </div>
          </div>

          <div className="p-3 bg-white border border-[#e5edf5] rounded flex flex-col justify-between">
            <div>
              <div className="text-[10px] font-medium text-[#533afd]">2. Firewall</div>
              <div className="text-[11px] font-medium text-[#061b31] mt-1">Evidence Gate</div>
              <div className="text-[10px] text-[#64748d] mt-1">Rejects safety violations & noise</div>
            </div>
          </div>

          <div className="p-3 bg-white border border-[#e5edf5] rounded flex flex-col justify-between">
            <div>
              <div className="text-[10px] font-medium text-[#533afd]">3. Reward</div>
              <div className="text-[11px] font-medium text-[#061b31] mt-1">Contribution Math</div>
              <div className="text-[10px] text-[#64748d] mt-1">Strict unit contribution in paise</div>
            </div>
          </div>

          <div className="p-3 bg-white border border-[#e5edf5] rounded flex flex-col justify-between">
            <div>
              <div className="text-[10px] font-medium text-[#533afd]">4. Memory</div>
              <div className="text-[11px] font-medium text-[#061b31] mt-1">Policy Memory</div>
              <div className="text-[10px] text-[#64748d] mt-1">Durable, idempotent partition</div>
            </div>
          </div>

          <div className="p-3 bg-white border border-[#e5edf5] rounded flex flex-col justify-between">
            <div>
              <div className="text-[10px] font-medium text-[#533afd]">5. Model Update</div>
              <div className="text-[11px] font-medium text-[#061b31] mt-1">LinUCB Sherman-M.</div>
              <div className="text-[10px] text-[#64748d] mt-1">Rank-1 covariance update</div>
            </div>
          </div>

          <div className="p-3 bg-[#e8e9ff] border border-[#b9b9f9] rounded flex flex-col justify-between">
            <div>
              <div className="text-[10px] font-medium text-[#533afd]">6. Next Decision</div>
              <div className="text-[11px] font-medium text-[#182659] mt-1">Adaptive Choice</div>
              <div className="text-[10px] text-[#50617a] mt-1">Exploration bounds tightened</div>
            </div>
          </div>
        </div>
      </div>

      {/* Learning Health Counters */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="stripe-card p-4">
          <div className="text-xs text-[#64748d]">Eligible Opportunities</div>
          <div className="text-2xl font-light text-[#061b31] mt-1 tabular-nums">
            {data?.health.eligible_opportunities_count ?? 0}
          </div>
          <div className="text-[11px] text-[#839bc8] mt-1">Eligible for reward feedback</div>
        </div>

        <div className="stripe-card p-4">
          <div className="text-xs text-[#64748d]">Valid Evidence</div>
          <div className="text-2xl font-light text-emerald-700 mt-1 tabular-nums">
            {data?.health.valid_evidence_count ?? 0}
          </div>
          <div className="text-[11px] text-[#839bc8] mt-1">Passed firewall verification</div>
        </div>

        <div className="stripe-card p-4">
          <div className="text-xs text-[#64748d]">Rejected Evidence</div>
          <div className="text-2xl font-light text-[#061b31] mt-1 tabular-nums">
            {data?.health.rejected_evidence_count ?? 0}
          </div>
          <div className="text-[11px] text-[#839bc8] mt-1">Safety / boundary filters</div>
        </div>

        <div className="stripe-card p-4">
          <div className="text-xs text-[#64748d]">Memory Observations</div>
          <div className="text-2xl font-light text-[#533afd] mt-1 tabular-nums">
            {data?.health.memory_observations_count ?? 0}
          </div>
          <div className="text-[11px] text-[#839bc8] mt-1">Persisted in policy memory</div>
        </div>

        <div className="stripe-card p-4">
          <div className="text-xs text-[#64748d]">Model Updates</div>
          <div className="text-2xl font-light text-emerald-700 mt-1 tabular-nums">
            {data?.health.model_updates_count ?? 0}
          </div>
          <div className="text-[11px] text-[#839bc8] mt-1">LinUCB weights modified</div>
        </div>

        <div className="stripe-card p-4">
          <div className="text-xs text-[#64748d]">Duplicate Deduplicated</div>
          <div className="text-2xl font-light text-[#061b31] mt-1 tabular-nums">
            {data?.health.duplicate_observations_count ?? 0}
          </div>
          <div className="text-[11px] text-[#839bc8] mt-1">Zero redundant updates</div>
        </div>
      </div>

      {/* Context Breakdown & Model State */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Context-Dependent Learning Breakdown */}
        <div className="lg:col-span-2 stripe-card overflow-hidden">
          <div className="p-5 border-b border-[#e5edf5]">
            <h3 className="text-sm font-medium text-[#061b31]">Context-Dependent Strategy Performance</h3>
            <p className="text-xs text-[#64748d] mt-0.5">
              Reinforcement learning converges independently per buyer context key, discovering optimal trade-offs for each customer segment.
            </p>
          </div>

          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-[#f8fafd] border-b border-[#e5edf5] text-[#64748d]">
                <th className="p-3">Buyer Context</th>
                <th className="p-3">Category Label</th>
                <th className="p-3">Preferred Strategy</th>
                <th className="p-3 text-right">Observations</th>
                <th className="p-3 text-right">Contribution</th>
                <th className="p-3 text-right">Last Updated</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-[#64748d]">Loading context breakdown...</td>
                </tr>
              ) : data?.context_breakdown && data.context_breakdown.length > 0 ? (
                data.context_breakdown.map((ctx, idx) => (
                  <tr key={`${ctx.buyer_context_key}_${ctx.preferred_strategy}_${idx}`} className="border-b border-[#e5edf5] hover:bg-[#f8fafd]">
                    <td className="p-3 font-mono font-medium text-[#533afd] text-[11px]">{ctx.buyer_context_key}</td>
                    <td className="p-3 font-medium text-[#061b31]">{ctx.context_label}</td>
                    <td className="p-3 text-[#061b31]">{ctx.preferred_strategy}</td>
                    <td className="p-3 text-right tabular-nums">{ctx.evidence_count}</td>
                    <td className="p-3 text-right font-medium text-emerald-700 tabular-nums">
                      {formatPaise(ctx.observed_contribution_paise)}
                    </td>
                    <td className="p-3 text-right text-[#64748d] font-mono text-[11px]">
                      {formatDateTime(ctx.last_updated_at)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="p-8 text-center text-[#64748d]">
                    No contextual learning data recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Right 1 Col: LinUCB Model State */}
        <div className="stripe-card p-6 flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-[#533afd]" />
                <h3 className="text-sm font-medium text-[#061b31]">LinUCB Bandit Model</h3>
              </div>
              <span className="stripe-tag bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-medium">
                {data?.model_metadata.learning_status || 'HEALTHY'}
              </span>
            </div>

            <div className="p-3 bg-[#f8fafd] rounded border border-[#e5edf5] font-mono text-xs space-y-2">
              <div className="flex justify-between">
                <span className="text-[#64748d]">Model Contract:</span>
                <span className="font-medium text-[#061b31]">{data?.model_metadata.model_version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#64748d]">Algorithm:</span>
                <span className="font-medium text-[#061b31]">{data?.model_metadata.algorithm_version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#64748d]">Feature Dim:</span>
                <span className="font-medium text-[#061b31]">{data?.model_metadata.dimension} dimensions</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#64748d]">Regularization (λ):</span>
                <span className="font-medium text-[#061b31]">{data?.model_metadata.lambda_reg}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#64748d]">Exploration (α):</span>
                <span className="font-medium text-[#061b31]">{formatPaise(data?.model_metadata.alpha_paise)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#64748d]">Observations (N):</span>
                <span className="font-medium text-emerald-700 tabular-nums">{data?.model_metadata.observation_count}</span>
              </div>
            </div>

            <div className="mt-4 p-3 bg-[#e8e9ff] border border-[#b9b9f9] rounded text-[11px] text-[#182659] leading-relaxed flex items-start gap-2">
              <Lock className="w-3.5 h-3.5 shrink-0 text-[#533afd] mt-0.5" />
              <span>
                <strong className="font-semibold">Zero Matrix Leakage:</strong> Internal inverse covariance matrices ($A^{-1}, b$) are securely encapsulated within the backend runtime and excluded from frontend rendering.
              </span>
            </div>
          </div>

          <div className="pt-3 border-t border-[#e5edf5] text-[11px] text-[#64748d] font-mono">
            Last Model Step: {formatDateTime(data?.model_metadata.last_updated_at)}
          </div>
        </div>
      </div>
    </div>
  );
}
