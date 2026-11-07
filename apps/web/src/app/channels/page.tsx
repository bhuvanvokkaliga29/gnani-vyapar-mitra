'use client';

import React, { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import {
  TrendingUp,
  RefreshCw,
  AlertCircle,
  HelpCircle,
  CheckCircle2,
  XCircle,
  ArrowRight,
  Info,
  Layers,
  FileText,
  ExternalLink,
  ShieldAlert,
  Sparkles,
  ShoppingBag,
  Store,
  Share2,
  Compass,
  SlidersHorizontal,
  ChevronRight,
  Eye
} from 'lucide-react';
import { useMerchant } from '@/lib/MerchantContext';
import { api, formatPaise } from '@/lib/api';
import { ChannelAnalyticsModal } from '@/components/channels/ChannelAnalyticsModal';

type ViewMode = 'SEGREGATED' | 'SINGLE_CHANNEL' | 'SKU_MATRIX';

export default function ChannelIntelligencePage() {
  const { currentMerchant } = useMerchant();
  const [plan, setPlan] = useState<any[]>([]);
  const [channels, setChannels] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [selectedChannelId, setSelectedChannelId] = useState<string>('AMAZON');
  const [viewMode, setViewMode] = useState<ViewMode>('SEGREGATED');
  const [filterDecision, setFilterDecision] = useState<'ALL' | 'LIST' | 'HOLD'>('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [inspectedItem, setInspectedItem] = useState<{ product: any; channel: any } | null>(null);
  const [showAssumptionsModal, setShowAssumptionsModal] = useState(false);
  const [analyzingChannelData, setAnalyzingChannelData] = useState<{
    channel: any;
    approved: any[];
    held: any[];
  } | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [planRes, chRes, ordersRes] = await Promise.all([
        api.getMarketplacePlan(currentMerchant.id),
        api.getChannels(currentMerchant.id),
        api.getOrders(100, 0).catch(() => ({ orders: [] }))
      ]);
      const loadedPlan = planRes.plan || [];
      const loadedChannels = chRes.channels || [];
      const loadedOrders = ordersRes.orders || [];
      setPlan(loadedPlan);
      setChannels(loadedChannels);
      setOrders(loadedOrders);

      if (loadedPlan.length > 0 && loadedChannels.length > 0) {
        const firstProd = loadedPlan[0];
        const firstCh = firstProd.channels?.[0] || null;
        setInspectedItem({ product: firstProd, channel: firstCh });
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load channel intelligence');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [currentMerchant.id]);

  // Group products by channel
  const channelSegregation = useMemo(() => {
    if (!channels.length || !plan.length) return [];

    return channels.map((ch) => {
      const approvedProducts: any[] = [];
      const heldProducts: any[] = [];

      plan.forEach((prod) => {
        const evalForChannel = prod.channels?.find((c: any) => c.channel_id === ch.channel_id);
        if (!evalForChannel) return;

        const combined = {
          ...prod,
          channelEcon: evalForChannel
        };

        if (evalForChannel.decision === 'HOLD') {
          heldProducts.push(combined);
        } else {
          approvedProducts.push(combined);
        }
      });

      const totalApprovedContribution = approvedProducts.reduce(
        (sum, p) => sum + (p.channelEcon.net_contribution_paise * (p.inventory_quantity || 1)),
        0
      );

      return {
        channel: ch,
        approved: approvedProducts,
        held: heldProducts,
        totalContributionPaise: totalApprovedContribution
      };
    });
  }, [channels, plan]);

  // Single active channel data
  const activeChannelData = useMemo(() => {
    return channelSegregation.find((cs) => cs.channel.channel_id === selectedChannelId);
  }, [channelSegregation, selectedChannelId]);

  const getDecisionBadge = (decision: string) => {
    switch (decision) {
      case 'LIST':
        return {
          className: 'bg-emerald-50 text-emerald-800 border-emerald-200',
          label: 'LIST (Marketplace)',
          icon: CheckCircle2
        };
      case 'DIRECT_CHANNEL':
        return {
          className: 'bg-blue-50 text-blue-800 border-blue-200',
          label: 'DIRECT (WhatsApp / Web)',
          icon: Store
        };
      case 'HOLD':
        return {
          className: 'bg-rose-50 text-rose-800 border-rose-200',
          label: 'HOLD (Margin Leakage)',
          icon: XCircle
        };
      default:
        return {
          className: 'bg-slate-50 text-slate-700 border-slate-200',
          label: decision,
          icon: Info
        };
    }
  };

  const getChannelIcon = (id: string) => {
    switch (id) {
      case 'AMAZON':
      case 'FLIPKART':
        return ShoppingBag;
      case 'MEESHO':
        return TrendingUp;
      case 'DIRECT_WHATSAPP':
        return Store;
      case 'ONDC':
        return Compass;
      case 'GOOGLE_LOCAL':
        return Store;
      case 'INSTAGRAM':
        return Share2;
      default:
        return Layers;
    }
  };

  return (
    <div className="w-full px-2 sm:px-4 md:px-6 py-4 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#d8d8d8]">
        <div>
          <div className="flex items-center gap-3">
            <img
              src="/vyapar_mitra_logo.png"
              alt="Vyapar Mitra"
              className="h-10 sm:h-11 w-auto object-contain"
            />
            <div className="h-6 w-[1px] bg-[#e4e4e7] hidden sm:block" />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[11px] font-semibold text-[#146ef5] bg-[#eff6ff] px-2 py-0.5 rounded-[4px] border border-[#146ef5]/20">
                  CHANNEL ECONOMICS ENGINE
                </span>
                <span className="text-xs text-[#5a5a5a]">
                  Deterministic Unit Contribution Routing
                </span>
              </div>
              <h1 className="text-xl md:text-2xl font-semibold text-[#080808] tracking-tight mt-0.5">
                Product Segregation by Digital Channel
              </h1>
            </div>
          </div>
          <p className="text-xs md:text-sm text-[#5a5a5a] mt-1 max-w-3xl leading-relaxed">
            Routes every SKU to the highest-yielding channels while blocking margin-destructive listings. Real deductions calculated in integer paise across fees, return logistics, and ad CAC.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAssumptionsModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-[#d8d8d8] rounded-[4px] text-[#5a5a5a] hover:bg-[#f0f0f0] bg-white transition-colors"
          >
            <HelpCircle className="w-3.5 h-3.5" />
            <span>Channel Fee Matrix</span>
          </button>
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[#146ef5] text-white rounded-[4px] hover:bg-[#1366e2] transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Recalculate Math</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-[4px] border border-rose-300 bg-rose-50 text-xs text-rose-800 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {/* Top Level Channel Allocation Summary Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
        {channelSegregation.map((cs) => {
          const Icon = getChannelIcon(cs.channel.channel_id);
          const isSelected = selectedChannelId === cs.channel.channel_id && viewMode === 'SINGLE_CHANNEL';
          return (
            <div
              key={cs.channel.channel_id}
              onClick={() => {
                setSelectedChannelId(cs.channel.channel_id);
                setViewMode('SINGLE_CHANNEL');
              }}
              role="button"
              tabIndex={0}
              className={`p-3 rounded-[6px] border text-left transition-all flex flex-col justify-between cursor-pointer ${
                isSelected
                  ? 'border-[#146ef5] bg-[#eff6ff] shadow-sm'
                  : 'border-[#d8d8d8] bg-white hover:border-[#bdbdbd]'
              }`}
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="p-1 rounded-[4px] bg-[#f0f0f0] text-[#080808]">
                    <Icon className="w-3.5 h-3.5" />
                  </span>
                  <span className="text-[10px] font-mono font-medium text-[#5a5a5a]">
                    {cs.channel.fee_percent}% fee
                  </span>
                </div>
                <div className="font-semibold text-xs text-[#080808] mt-2 truncate" title={cs.channel.name}>
                  {cs.channel.name.split('/')[0].split('(')[0].trim()}
                </div>
              </div>
              <div className="mt-2 pt-2 border-t border-[#d8d8d8]/60 flex items-center justify-between text-[11px]">
                <span className="text-emerald-700 font-semibold">{cs.approved.length} List</span>
                <span className="text-rose-700 font-semibold">{cs.held.length} Hold</span>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setAnalyzingChannelData({
                    channel: cs.channel,
                    approved: cs.approved,
                    held: cs.held
                  });
                }}
                className="mt-2.5 w-full flex items-center justify-center gap-1.5 py-1 px-2 text-[10px] font-semibold bg-[#146ef5]/10 text-[#146ef5] hover:bg-[#146ef5] hover:text-white rounded-[4px] transition-colors"
                title={`Analyze ${cs.channel.name} channel economics and order flow`}
              >
                <TrendingUp className="w-3 h-3" />
                <span>Analyze Channel</span>
              </button>
            </div>
          );
        })}
      </div>

      {/* View Mode Controls & Channel Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-[#f0f0f0] border border-[#d8d8d8] rounded-[6px]">
        {/* View Mode Switcher */}
        <div className="flex items-center gap-1 bg-white p-1 rounded-[4px] border border-[#d8d8d8] self-start sm:self-auto">
          <button
            onClick={() => setViewMode('SEGREGATED')}
            className={`px-3 py-1 text-xs rounded-[3px] font-medium transition-colors ${
              viewMode === 'SEGREGATED'
                ? 'bg-[#146ef5] text-white shadow-xs'
                : 'text-[#5a5a5a] hover:text-[#080808]'
            }`}
          >
            All Channels (Segregated Board)
          </button>
          <button
            onClick={() => setViewMode('SINGLE_CHANNEL')}
            className={`px-3 py-1 text-xs rounded-[3px] font-medium transition-colors ${
              viewMode === 'SINGLE_CHANNEL'
                ? 'bg-[#146ef5] text-white shadow-xs'
                : 'text-[#5a5a5a] hover:text-[#080808]'
            }`}
          >
            Channel Focus Table
          </button>
          <button
            onClick={() => setViewMode('SKU_MATRIX')}
            className={`px-3 py-1 text-xs rounded-[3px] font-medium transition-colors ${
              viewMode === 'SKU_MATRIX'
                ? 'bg-[#146ef5] text-white shadow-xs'
                : 'text-[#5a5a5a] hover:text-[#080808]'
            }`}
          >
            Cross-SKU Matrix
          </button>
        </div>

        {/* Channel Selector when in Single Channel mode */}
        {viewMode === 'SINGLE_CHANNEL' && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-[#5a5a5a] font-medium">Channel:</span>
            <select
              value={selectedChannelId}
              onChange={(e) => setSelectedChannelId(e.target.value)}
              className="text-xs font-semibold px-2.5 py-1 bg-white border border-[#d8d8d8] rounded-[4px] text-[#080808] focus:outline-none focus:border-[#146ef5]"
            >
              {channels.map((ch) => (
                <option key={ch.channel_id} value={ch.channel_id}>
                  {ch.name} ({ch.fee_percent}% fee)
                </option>
              ))}
            </select>

            <span className="text-xs text-[#5a5a5a] font-medium ml-2">Show:</span>
            <select
              value={filterDecision}
              onChange={(e) => setFilterDecision(e.target.value as any)}
              className="text-xs font-medium px-2 py-1 bg-white border border-[#d8d8d8] rounded-[4px] text-[#080808]"
            >
              <option value="ALL">All Decisions</option>
              <option value="LIST">Approved to List</option>
              <option value="HOLD">Hold (Margin Leakage)</option>
            </select>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* VIEW 1: CHANNEL-FIRST SEGREGATED BOARD (Default)                          */}
      {/* Displays every channel with its approved vs held product segregation      */}
      {/* ========================================================================= */}
      {viewMode === 'SEGREGATED' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between text-xs text-[#5a5a5a]">
            <span>
              Showing <strong>{channelSegregation.length} digital channels</strong> evaluated across <strong>{plan.length} catalog SKUs</strong>.
            </span>
            <span className="text-[11px] font-mono">
              Floor Constraint: ≥ {currentMerchant?.minimum_margin_percent ?? 25.0}% Net Margin
            </span>
          </div>

          <div className="grid grid-cols-1 gap-6">
            {channelSegregation.map((cs) => {
              const Icon = getChannelIcon(cs.channel.channel_id);
              return (
                <div key={cs.channel.channel_id} className="studio-card overflow-hidden">
                  {/* Channel Card Header */}
                  <div className="p-4 bg-[#f8f9fa] border-b border-[#d8d8d8] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="p-2 rounded-[6px] bg-white border border-[#d8d8d8] text-[#080808] shadow-xs">
                        <Icon className="w-5 h-5 text-[#146ef5]" />
                      </span>
                      <div>
                        <div className="flex items-center gap-2">
                          <h2 className="text-sm md:text-base font-semibold text-[#080808]">
                            {cs.channel.name}
                          </h2>
                          <span className="px-1.5 py-0.5 rounded-[3px] text-[10px] font-mono bg-white border border-[#d8d8d8] text-[#5a5a5a]">
                            {cs.channel.verification_status}
                          </span>
                        </div>
                        <p className="text-[11px] text-[#5a5a5a] mt-0.5">
                          {cs.channel.audience_fit}
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
                      <div className="text-right">
                        <span className="text-[#5a5a5a] block text-[10px] uppercase tracking-wider">Fee Structure</span>
                        <span className="font-semibold text-[#080808]">
                          {cs.channel.fee_percent}% + {formatPaise(cs.channel.fixed_fee_paise)}
                        </span>
                      </div>
                      <div className="text-right border-l border-[#d8d8d8] pl-4">
                        <span className="text-[#5a5a5a] block text-[10px] uppercase tracking-wider">Est. Return Rate</span>
                        <span className="font-semibold text-rose-700">
                          {cs.channel.return_rate_percent}%
                        </span>
                      </div>
                      <div className="text-right border-l border-[#d8d8d8] pl-4">
                        <span className="text-[#5a5a5a] block text-[10px] uppercase tracking-wider">Eligible Volume</span>
                        <span className="font-semibold text-emerald-700">
                          {cs.approved.length} of {cs.approved.length + cs.held.length} SKUs
                        </span>
                      </div>
                      <div className="border-l border-[#d8d8d8] pl-4">
                        <button
                          type="button"
                          onClick={() => setAnalyzingChannelData({
                            channel: cs.channel,
                            approved: cs.approved,
                            held: cs.held
                          })}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-[#146ef5] text-white rounded-[4px] hover:bg-[#1366e2] transition-colors shadow-2xs font-sans"
                        >
                          <TrendingUp className="w-3.5 h-3.5" />
                          <span>Analyze Channel</span>
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Segregated Product Sections */}
                  <div className="p-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {/* Column 1: Approved to List on this Channel */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between pb-2 border-b border-[#d8d8d8]">
                        <div className="flex items-center gap-1.5">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                          <h3 className="text-xs font-semibold uppercase tracking-wider text-emerald-900">
                            Approved to Sell on {cs.channel.name.split(' ')[0]} ({cs.approved.length})
                          </h3>
                        </div>
                        <span className="text-[10px] text-emerald-700 font-mono font-medium">
                          Net Margin ≥ 25%
                        </span>
                      </div>

                      {cs.approved.length === 0 ? (
                        <div className="p-4 rounded-[4px] bg-[#f8f9fa] border border-dashed border-[#d8d8d8] text-center text-xs text-[#5a5a5a]">
                          No products qualify for this channel without violating the margin floor.
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {cs.approved.map((prod) => {
                            const badge = getDecisionBadge(prod.channelEcon.decision);
                            return (
                              <div
                                key={prod.product_id}
                                onClick={() => setInspectedItem({ product: prod, channel: prod.channelEcon })}
                                className="p-3 rounded-[6px] border border-[#d8d8d8] bg-white hover:border-[#146ef5] transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs"
                              >
                                <div className="space-y-0.5">
                                  <div className="font-semibold text-xs text-[#080808] flex items-center gap-2">
                                    <span>{prod.product_name}</span>
                                    <span className="font-mono text-[10px] text-[#5a5a5a]">({prod.sku})</span>
                                  </div>
                                  <div className="text-[11px] text-[#5a5a5a] flex items-center gap-3">
                                    <span>List: <strong className="text-[#080808]">{formatPaise(prod.price_paise)}</strong></span>
                                    <span>COGS: <strong className="text-[#080808]">{formatPaise(prod.cost_paise)}</strong></span>
                                    <span>Stock: {prod.inventory_quantity}</span>
                                  </div>
                                </div>

                                <div className="flex items-center gap-3 self-end sm:self-auto">
                                  <div className="text-right">
                                    <div className="font-semibold text-xs text-[#146ef5]">
                                      +{formatPaise(prod.channelEcon.net_contribution_paise)}
                                    </div>
                                    <div className="text-[10px] font-semibold text-emerald-700">
                                      {prod.channelEcon.margin_percent.toFixed(1)}% margin
                                    </div>
                                  </div>

                                  <Link
                                    href="/listings"
                                    className="p-1.5 rounded-[4px] text-[#146ef5] hover:bg-[#eff6ff] border border-[#146ef5]/20 text-[11px] font-medium flex items-center gap-1 whitespace-nowrap"
                                    title="Generate listing pack for this SKU"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <FileText className="w-3.5 h-3.5" />
                                    <span className="hidden sm:inline">Pack</span>
                                  </Link>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* Column 2: Blocked / Hold on this Channel */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between pb-2 border-b border-[#d8d8d8]">
                        <div className="flex items-center gap-1.5">
                          <ShieldAlert className="w-4 h-4 text-rose-600" />
                          <h3 className="text-xs font-semibold uppercase tracking-wider text-rose-900">
                            Hold / Blocked from {cs.channel.name.split(' ')[0]} ({cs.held.length})
                          </h3>
                        </div>
                        <span className="text-[10px] text-rose-700 font-mono font-medium">
                          Protected from Profit Leakage
                        </span>
                      </div>

                      {cs.held.length === 0 ? (
                        <div className="p-4 rounded-[4px] bg-emerald-50/50 border border-emerald-200 text-center text-xs text-emerald-800">
                          All catalog SKUs clear the profit guardrails for this channel!
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {cs.held.map((prod) => {
                            return (
                              <div
                                key={prod.product_id}
                                onClick={() => setInspectedItem({ product: prod, channel: prod.channelEcon })}
                                className="p-3 rounded-[6px] border border-rose-200 bg-rose-50/40 hover:bg-rose-50/70 transition-all cursor-pointer flex flex-col justify-between gap-2"
                              >
                                <div className="flex items-start justify-between gap-2">
                                  <div>
                                    <div className="font-semibold text-xs text-[#080808]">
                                      {prod.product_name}
                                    </div>
                                    <div className="font-mono text-[10px] text-[#5a5a5a]">
                                      {prod.sku} • Price: {formatPaise(prod.price_paise)} • Cost: {formatPaise(prod.cost_paise)}
                                    </div>
                                  </div>
                                  <div className="text-right">
                                    <span className="px-1.5 py-0.5 rounded-[3px] text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-300">
                                      HOLD
                                    </span>
                                    <div className="text-[10px] text-rose-700 font-mono mt-0.5">
                                      {prod.channelEcon.margin_percent.toFixed(1)}% margin
                                    </div>
                                  </div>
                                </div>

                                <div className="text-[11px] text-[#5a5a5a] border-t border-rose-200/60 pt-1.5 flex items-center justify-between">
                                  <p className="line-clamp-1 italic text-rose-900">
                                    {prod.channelEcon.rationale}
                                  </p>
                                  <Link
                                    href="/sales-agent"
                                    onClick={(e) => e.stopPropagation()}
                                    className="text-[10px] font-medium text-[#146ef5] hover:underline shrink-0 ml-2 flex items-center gap-0.5"
                                  >
                                    <span>Route Direct</span>
                                    <ArrowRight className="w-3 h-3" />
                                  </Link>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* VIEW 2: SINGLE CHANNEL FOCUS TABLE                                        */}
      {/* Deep-dive into one channel's fee breakdown across all SKUs                */}
      {/* ========================================================================= */}
      {viewMode === 'SINGLE_CHANNEL' && activeChannelData && (
        <div className="space-y-4">
          <div className="studio-card p-4 bg-[#f8f9fa] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-[#080808]">
                  {activeChannelData.channel.name}
                </h2>
                <span className="px-2 py-0.5 rounded-[4px] font-mono text-[10px] bg-white border border-[#d8d8d8] text-[#5a5a5a]">
                  Fee: {activeChannelData.channel.fee_percent}% + {formatPaise(activeChannelData.channel.fixed_fee_paise)}
                </span>
                <span className="px-2 py-0.5 rounded-[4px] font-mono text-[10px] bg-rose-50 border border-rose-200 text-rose-700">
                  Return Rate: {activeChannelData.channel.return_rate_percent}%
                </span>
              </div>
              <p className="text-xs text-[#5a5a5a] mt-1">
                {activeChannelData.channel.audience_fit}
              </p>
            </div>

            <div className="flex items-center gap-3">
              <div className="text-right">
                <span className="text-[10px] text-[#5a5a5a] block uppercase tracking-wider">Approved SKUs</span>
                <span className="text-sm font-semibold text-emerald-700">
                  {activeChannelData.approved.length} of {activeChannelData.approved.length + activeChannelData.held.length}
                </span>
              </div>
              <div className="text-right border-l border-[#d8d8d8] pl-3">
                <span className="text-[10px] text-[#5a5a5a] block uppercase tracking-wider">Total Potential Net</span>
                <span className="text-sm font-semibold text-[#146ef5]">
                  {formatPaise(activeChannelData.totalContributionPaise)}
                </span>
              </div>
              <div className="border-l border-[#d8d8d8] pl-3">
                <button
                  type="button"
                  onClick={() => setAnalyzingChannelData({
                    channel: activeChannelData.channel,
                    approved: activeChannelData.approved,
                    held: activeChannelData.held
                  })}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-[#146ef5] text-white rounded-[4px] hover:bg-[#1366e2] transition-colors shadow-2xs"
                >
                  <TrendingUp className="w-3.5 h-3.5" />
                  <span>Analyze Channel</span>
                </button>
              </div>
            </div>
          </div>

          <div className="studio-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-[#f0f0f0] text-[#080808] font-semibold border-b border-[#d8d8d8]">
                  <tr>
                    <th className="py-2.5 px-3">Product / SKU</th>
                    <th className="py-2.5 px-3">List Price</th>
                    <th className="py-2.5 px-3">COGS</th>
                    <th className="py-2.5 px-3">Channel Fee</th>
                    <th className="py-2.5 px-3">Shipping & Returns</th>
                    <th className="py-2.5 px-3">Net Payout</th>
                    <th className="py-2.5 px-3">Net Margin</th>
                    <th className="py-2.5 px-3">Decision</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#d8d8d8]">
                  {plan
                    .filter((item) => {
                      const chEcon = item.channels?.find((c: any) => c.channel_id === selectedChannelId);
                      if (!chEcon) return false;
                      if (filterDecision === 'LIST') return chEcon.decision !== 'HOLD';
                      if (filterDecision === 'HOLD') return chEcon.decision === 'HOLD';
                      return true;
                    })
                    .map((item) => {
                      const chEcon = item.channels?.find((c: any) => c.channel_id === selectedChannelId);
                      if (!chEcon) return null;
                      const badge = getDecisionBadge(chEcon.decision);
                      const isInspected = inspectedItem?.product?.product_id === item.product_id;

                      return (
                        <tr
                          key={item.product_id}
                          onClick={() => setInspectedItem({ product: item, channel: chEcon })}
                          className={`cursor-pointer transition-colors ${
                            isInspected ? 'bg-[#eff6ff]' : 'hover:bg-[#f0f0f0]'
                          }`}
                        >
                          <td className="py-3 px-3">
                            <div className="font-semibold text-[#080808]">{item.product_name}</div>
                            <div className="font-mono text-[10px] text-[#5a5a5a]">{item.sku} • {item.inventory_quantity} in stock</div>
                          </td>
                          <td className="py-3 px-3 font-medium text-[#080808]">{formatPaise(item.price_paise)}</td>
                          <td className="py-3 px-3 font-mono text-[#5a5a5a]">{formatPaise(item.cost_paise)}</td>
                          <td className="py-3 px-3 text-rose-700">−{formatPaise(chEcon.fees_paise)}</td>
                          <td className="py-3 px-3 text-rose-700">−{formatPaise(chEcon.shipping_paise + chEcon.expected_return_cost_paise)}</td>
                          <td className="py-3 px-3 font-bold text-[#146ef5]">{formatPaise(chEcon.net_contribution_paise)}</td>
                          <td className="py-3 px-3 font-semibold">
                            <span className={chEcon.margin_percent >= 25 ? 'text-emerald-700' : 'text-rose-700'}>
                              {chEcon.margin_percent.toFixed(1)}%
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            <span className={`px-2 py-0.5 rounded-[4px] text-[10px] font-semibold border ${badge.className}`}>
                              {badge.label}
                            </span>
                          </td>
                          <td className="py-3 px-3 text-right" onClick={(e) => e.stopPropagation()}>
                            {chEcon.decision !== 'HOLD' ? (
                              <Link
                                href="/listings"
                                className="px-2.5 py-1 text-[11px] font-medium bg-[#146ef5] text-white rounded-[4px] hover:bg-[#1366e2] inline-flex items-center gap-1"
                              >
                                <FileText className="w-3 h-3" />
                                <span>List Pack</span>
                              </Link>
                            ) : (
                              <Link
                                href="/sales-agent"
                                className="px-2 py-1 text-[11px] font-medium text-[#146ef5] hover:underline"
                              >
                                Direct Only
                              </Link>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* VIEW 3: SKU CROSS-CHANNEL MATRIX                                          */}
      {/* ========================================================================= */}
      {viewMode === 'SKU_MATRIX' && (
        <div className="studio-card overflow-hidden">
          <div className="p-4 border-b border-[#d8d8d8] flex items-center justify-between bg-[#f0f0f0]">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-[#080808]">
                Cross-Channel Economic Audit
              </h3>
              <p className="text-[11px] text-[#5a5a5a]">
                Compares unit contribution across all digital sales channels.
              </p>
            </div>
            <span className="text-xs font-mono text-[#5a5a5a]">{plan.length} SKUs Analyzed</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-[#ffffff] text-[#5a5a5a] font-semibold border-b border-[#d8d8d8]">
                <tr>
                  <th className="py-2.5 px-3">Product / SKU</th>
                  <th className="py-2.5 px-3">Price</th>
                  <th className="py-2.5 px-3">COGS</th>
                  <th className="py-2.5 px-3">Optimal Route</th>
                  <th className="py-2.5 px-3">Best Net</th>
                  <th className="py-2.5 px-3">Best Margin</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#d8d8d8]">
                {plan.map((item) => {
                  const badge = getDecisionBadge(item.top_recommendation);
                  return (
                    <tr
                      key={item.product_id}
                      onClick={() => setInspectedItem({ product: item, channel: item.channels?.[0] })}
                      className="hover:bg-[#f0f0f0] cursor-pointer transition-colors"
                    >
                      <td className="py-3 px-3">
                        <div className="font-semibold text-[#080808]">{item.product_name}</div>
                        <div className="font-mono text-[10px] text-[#5a5a5a]">{item.sku}</div>
                      </td>
                      <td className="py-3 px-3 font-medium text-[#080808]">{formatPaise(item.price_paise)}</td>
                      <td className="py-3 px-3 font-mono text-[#5a5a5a]">{formatPaise(item.cost_paise)}</td>
                      <td className="py-3 px-3 font-semibold text-[#080808]">{item.recommended_channel}</td>
                      <td className="py-3 px-3 font-bold text-[#146ef5]">
                        {formatPaise(Math.max(...(item.channels?.map((c: any) => c.net_contribution_paise) || [0])))}
                      </td>
                      <td className="py-3 px-3 font-bold text-emerald-700">
                        {Math.max(...(item.channels?.map((c: any) => c.margin_percent) || [0])).toFixed(1)}%
                      </td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded-[4px] text-[10px] font-semibold border ${badge.className}`}>
                          {badge.label}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <span className="text-[11px] font-medium text-[#146ef5]">Inspect Math &rarr;</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Selected SKU Audit Trace Drawer */}
      {inspectedItem && inspectedItem.product && (
        <div className="studio-card p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#d8d8d8]">
            <div>
              <div className="text-xs text-[#5a5a5a] font-mono">SELECTED SKU DEEP DIVE AUDIT</div>
              <h3 className="text-base font-semibold text-[#080808]">
                {inspectedItem.product.product_name} ({inspectedItem.product.sku})
              </h3>
            </div>
            <Link
              href="/listings"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[#146ef5] text-white rounded-[4px] hover:bg-[#1366e2] self-start sm:self-auto"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Generate Listing Pack for this SKU</span>
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {inspectedItem.product.channels?.map((c: any) => {
              const b = getDecisionBadge(c.decision);
              return (
                <div key={c.channel_id} className="p-4 border border-[#d8d8d8] rounded-[6px] bg-[#ffffff] space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="font-semibold text-xs text-[#080808]">{c.channel_name}</div>
                    <span className={`px-1.5 py-0.5 rounded-[2px] text-[9px] font-bold border ${b.className}`}>
                      {c.decision}
                    </span>
                  </div>

                  <div className="space-y-1 text-xs border-y border-[#d8d8d8] py-2">
                    <div className="flex justify-between">
                      <span className="text-[#5a5a5a]">Selling Price:</span>
                      <span className="font-medium text-[#080808]">{formatPaise(c.selling_price_paise)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#5a5a5a]">Channel Fees:</span>
                      <span className="text-rose-700">−{formatPaise(c.fees_paise)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#5a5a5a]">Shipping Allowance:</span>
                      <span className="text-rose-700">−{formatPaise(c.shipping_paise)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#5a5a5a]">Expected Return Cost:</span>
                      <span className="text-rose-700">−{formatPaise(c.expected_return_cost_paise)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[#5a5a5a]">Estimated Ad CAC:</span>
                      <span className="text-rose-700">−{formatPaise(c.ad_cost_paise)}</span>
                    </div>
                    <div className="flex justify-between font-bold pt-1 border-t border-[#d8d8d8]">
                      <span className="text-[#080808]">Net Contribution:</span>
                      <span className="text-[#146ef5]">{formatPaise(c.net_contribution_paise)}</span>
                    </div>
                    <div className="flex justify-between text-[11px]">
                      <span className="text-[#5a5a5a]">Net Margin %:</span>
                      <span className={c.margin_percent >= 25 ? 'font-semibold text-emerald-700' : 'font-semibold text-rose-700'}>
                        {c.margin_percent.toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  <p className="text-[11px] text-[#5a5a5a] leading-tight">
                    {c.rationale}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Channel Fee Matrix Modal */}
      {showAssumptionsModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white border border-[#d8d8d8] rounded-[8px] max-w-2xl w-full p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between pb-3 border-b border-[#d8d8d8]">
              <h3 className="font-semibold text-sm text-[#080808]">Channel Economic Assumptions</h3>
              <button
                onClick={() => setShowAssumptionsModal(false)}
                className="text-xs text-[#5a5a5a] hover:text-[#080808]"
              >
                Close
              </button>
            </div>

            <div className="overflow-x-auto max-h-96">
              <table className="w-full text-xs text-left">
                <thead className="bg-[#f0f0f0] text-[#080808] font-semibold border-b border-[#d8d8d8]">
                  <tr>
                    <th className="py-2 px-3">Channel</th>
                    <th className="py-2 px-3">Fee %</th>
                    <th className="py-2 px-3">Fixed Fee</th>
                    <th className="py-2 px-3">Shipping</th>
                    <th className="py-2 px-3">Return Rate</th>
                    <th className="py-2 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#d8d8d8]">
                  {channels.map((ch) => (
                    <tr key={ch.channel_id}>
                      <td className="py-2 px-3 font-semibold text-[#080808]">{ch.name}</td>
                      <td className="py-2 px-3">{ch.fee_percent}%</td>
                      <td className="py-2 px-3">{formatPaise(ch.fixed_fee_paise)}</td>
                      <td className="py-2 px-3">{formatPaise(ch.shipping_base_paise)}</td>
                      <td className="py-2 px-3 text-rose-700">{ch.return_rate_percent}%</td>
                      <td className="py-2 px-3">
                        <span className="px-1.5 py-0.5 rounded-[2px] font-mono text-[9px] bg-[#f0f0f0] border border-[#d8d8d8] text-[#5a5a5a]">
                          {ch.verification_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="text-[11px] text-[#5a5a5a] pt-2 border-t border-[#d8d8d8]">
              All marketplace assumptions are labeled <code>SAMPLE</code> or <code>VERIFY</code> and can be configured per merchant. Monies computed strictly in integer paise.
            </p>
          </div>
        </div>
      )}

      {/* Channel Analytics Modal */}
      {analyzingChannelData && (
        <ChannelAnalyticsModal
          isOpen={true}
          onClose={() => setAnalyzingChannelData(null)}
          channel={analyzingChannelData.channel}
          approvedProducts={analyzingChannelData.approved || []}
          heldProducts={analyzingChannelData.held || []}
          allOrders={orders}
        />
      )}
    </div>
  );
}
