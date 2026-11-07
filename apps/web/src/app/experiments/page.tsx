'use client';

import React, { useState, useEffect } from 'react';
import { FlaskConical, RefreshCw, CheckCircle2, AlertTriangle, ArrowUpRight, TrendingUp } from 'lucide-react';
import { useMerchant } from '@/lib/MerchantContext';
import { api, formatPaise, formatDateTime } from '@/lib/api';
import { ExperimentListResponse } from '@/lib/types';

export default function ExperimentsPage() {
  const { currentMerchant } = useMerchant();
  const [data, setData] = useState<ExperimentListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadExperiments = () => {
    setLoading(true);
    setError(null);
    api.getExperiments(currentMerchant.id)
      .then((res) => setData(res))
      .catch((err) => setError(err.message || 'Failed to load experiments'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadExperiments();
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
            <span className="text-xs text-[#64748d]">Phase 7 Controlled Policy Evaluations</span>
          </div>
          <h1 className="text-3xl font-light text-[#061b31] tracking-tight mt-1.5">
            Controlled Policy Experiments
          </h1>
          <p className="text-sm text-[#50617a] font-normal mt-1 leading-relaxed">
            Rigorous A/B evaluations comparing candidate commercial strategies against baseline controls with automated margin guardrails.
          </p>
        </div>

        <button
          onClick={loadExperiments}
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

      {/* Information Banner on Evidence Class */}
      <div className="p-4 bg-[#f8fafd] border border-[#e5edf5] rounded text-xs text-[#50617a] leading-relaxed">
        <span className="font-semibold text-[#061b31]">Evidence Classification Guarantee:</span> Metrics displayed here identify their provenance class. Simulated outcomes and Test-Mode Observed transactions are strictly tagged and never silently mixed with production revenue.
      </div>

      {/* Experiments Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {loading ? (
          <div className="col-span-2 stripe-card p-12 text-center text-xs text-[#64748d]">
            Loading controlled experiments...
          </div>
        ) : data?.items && data.items.length > 0 ? (
          data.items.map((exp) => (
            <div key={exp.experiment_id} className="stripe-card p-6 flex flex-col justify-between space-y-6">
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-[#533afd] font-medium">{exp.experiment_id}</span>
                      <span className="stripe-tag bg-[#e8e9ff] text-[#533afd] text-[10px] font-medium">
                        {exp.source}
                      </span>
                    </div>
                    <h3 className="text-base font-medium text-[#061b31] mt-1">{exp.name}</h3>
                  </div>

                  <span
                    className={`stripe-tag text-[10px] font-medium ${
                      exp.status === 'COMPLETED'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-amber-50 text-amber-700 border border-amber-200'
                    }`}
                  >
                    {exp.status}
                  </span>
                </div>

                {/* Strategy Comparison Block */}
                <div className="grid grid-cols-2 gap-3 mt-5 p-3.5 rounded bg-[#f8fafd] border border-[#e5edf5] text-xs">
                  <div>
                    <div className="text-[10px] text-[#64748d] uppercase tracking-wider">Control Policy</div>
                    <div className="font-mono text-xs font-medium text-[#061b31] mt-0.5">{exp.control_policy_id}</div>
                    <div className="text-sm font-medium text-[#061b31] mt-2 tabular-nums">
                      {formatPaise(exp.control_observed_ecps_paise)}
                    </div>
                    <div className="text-[10px] text-[#839bc8]">ECPS (Expected Contribution)</div>
                  </div>

                  <div className="border-l border-[#e5edf5] pl-3">
                    <div className="text-[10px] text-[#533afd] uppercase tracking-wider">Treatment Policy</div>
                    <div className="font-mono text-xs font-medium text-[#061b31] mt-0.5">{exp.treatment_policy_id}</div>
                    <div className="text-sm font-medium text-emerald-700 mt-2 tabular-nums">
                      {formatPaise(exp.treatment_observed_ecps_paise)}
                    </div>
                    <div className="text-[10px] text-[#839bc8]">ECPS (Expected Contribution)</div>
                  </div>
                </div>

                {/* Diff & Guardrail Status */}
                <div className="grid grid-cols-2 gap-4 mt-4 text-xs">
                  <div>
                    <span className="text-[#64748d]">Observed Lift (Δ ECPS):</span>
                    <div className="text-base font-medium text-emerald-700 mt-0.5 flex items-center gap-1 tabular-nums">
                      <TrendingUp className="w-4 h-4" />
                      <span>+{formatPaise(exp.observed_diff_paise)}</span>
                    </div>
                  </div>

                  <div>
                    <span className="text-[#64748d]">Margin Guardrail:</span>
                    <div className="mt-1">
                      <span className="stripe-tag bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px]">
                        {exp.guardrail_status}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-[#e5edf5] flex justify-between items-center text-[11px] text-[#64748d]">
                <span>Sample Size: {exp.population_size} opportunities</span>
                <span>Completed {formatDateTime(exp.completed_at)}</span>
              </div>
            </div>
          ))
        ) : (
          <div className="col-span-2 stripe-card p-12 text-center text-xs text-[#64748d]">
            No controlled experiments evaluated yet for this merchant.
          </div>
        )}
      </div>
    </div>
  );
}
