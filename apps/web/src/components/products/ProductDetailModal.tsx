'use client';

import React, { useState } from 'react';
import {
  X,
  Sparkles,
  ShoppingBag,
  ExternalLink,
  Layers,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Tag,
  TrendingUp,
  Percent,
  Check,
  Package,
  Store,
  Share2,
  RefreshCw,
  Clock,
  Shirt
} from 'lucide-react';
import { formatPaise } from '@/lib/api';

interface ProductDetailModalProps {
  product: any | null;
  isOpen: boolean;
  onClose: () => void;
  onActionComplete?: (msg: string) => void;
}

export function ProductDetailModal({
  product,
  isOpen,
  onClose,
  onActionComplete
}: ProductDetailModalProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'marketplaces' | 'recommendations'>('overview');
  const [appliedActions, setAppliedActions] = useState<Record<string, boolean>>({});
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  if (!isOpen || !product) return null;

  const attrs = product.attributes || {};
  const marketplaces = attrs.marketplaces || [];
  const recommendations = attrs.recommendations || [];

  const imageUrl =
    attrs.refined_photo_url ||
    (product.name?.toLowerCase().includes('oxford') || product.name?.toLowerCase().includes('white')
      ? '/clothing/white_oxford.jpg'
      : product.name?.toLowerCase().includes('navy')
      ? '/clothing/navy_shirt.jpg'
      : product.name?.toLowerCase().includes('linen') || product.name?.toLowerCase().includes('olive')
      ? '/clothing/linen_shirt.jpg'
      : product.name?.toLowerCase().includes('khaki') || product.name?.toLowerCase().includes('chino')
      ? '/clothing/khaki_chino.jpg'
      : product.name?.toLowerCase().includes('grey') || product.name?.toLowerCase().includes('charcoal')
      ? '/clothing/grey_trouser.jpg'
      : '/clothing/black_trouser.jpg');

  const marginPct =
    product.price_paise > 0
      ? (((product.price_paise - product.cost_paise) / product.price_paise) * 100).toFixed(1)
      : '0.0';

  const handleExecuteAction = (recId: string, actionTitle: string) => {
    setActionLoading(recId);
    setTimeout(() => {
      setAppliedActions((prev) => ({ ...prev, [recId]: true }));
      setActionLoading(null);
      if (onActionComplete) {
        onActionComplete(`✓ Action executed: ${actionTitle}`);
      }
    }, 600);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity animate-fade-in"
        onClick={onClose}
      />

      {/* Modal / Sheet Container */}
      <div className="relative bg-white rounded-t-2xl sm:rounded-[16px] max-w-3xl w-full mx-auto shadow-2xl border border-[#D5DEE9] z-10 max-h-[92vh] flex flex-col overflow-hidden animate-slide-up">
        
        {/* Mobile Pull Handle */}
        <div className="w-12 h-1.5 bg-[#C4CFDC] rounded-full mx-auto mt-2.5 sm:hidden shrink-0" />

        {/* Modal Top Header Bar */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#C4CFDC] bg-[#E8EEF5] sticky top-0 z-20">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] font-bold bg-[#0F172A] text-white px-2 py-0.5 rounded">
              VYAPAR MITRA APPAREL
            </span>
            <span className="text-xs font-mono text-[#526176] font-medium">
              SKU: {product.sku}
            </span>
            {product.inventory_quantity <= 10 && (
              <span className="text-[10px] font-bold text-[#92400E] bg-[#FFF4DB] px-2 py-0.5 rounded border border-[#92400E]/30 animate-pulse">
                LOW STOCK ({product.inventory_quantity})
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-full hover:bg-white text-[#526176] hover:text-[#0F172A] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="overflow-y-auto p-5 sm:p-6 space-y-6">
          
          {/* Main Hero Card: Photo + Title + Key Economics */}
          <div className="grid grid-cols-1 sm:grid-cols-12 gap-5 p-4 rounded-[12px] bg-[#F8FAFC] border border-[#D5DEE9]">
            {/* Product Image */}
            <div className="sm:col-span-4 relative rounded-lg overflow-hidden bg-white border border-[#D5DEE9] aspect-square flex items-center justify-center p-2 shadow-2xs">
              <img
                src={imageUrl}
                alt={product.name}
                className="max-h-full max-w-full object-contain"
              />
            </div>

            {/* Title & Core Commercial Economics */}
            <div className="sm:col-span-8 flex flex-col justify-between space-y-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-[#0F172A] bg-white px-2 py-0.5 rounded border border-[#D5DEE9]">
                    Category: {product.category}
                  </span>
                  <span className="text-[10px] font-semibold text-[#067647] bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#067647]/30">
                    ✓ {product.is_active ? 'Active in Catalog' : 'Draft'}
                  </span>
                </div>
                <h2 className="text-base sm:text-lg font-bold text-[#0F172A] tracking-tight mt-1 leading-snug font-['Inter']">
                  {product.name}
                </h2>
                <p className="text-xs text-[#526176] mt-1 line-clamp-2 font-['Inter']">
                  {product.description}
                </p>
              </div>

              {/* Economic Numbers Grid */}
              <div className="grid grid-cols-3 gap-2.5 pt-2 border-t border-[#D5DEE9]">
                <div className="p-2 rounded-lg bg-white border border-[#D5DEE9]">
                  <div className="text-[10px] text-[#667085] font-medium font-['Inter']">Selling Price</div>
                  <div className="text-sm font-bold text-[#0F172A] mt-0.5 font-['Inter']">
                    {formatPaise(product.price_paise)}
                  </div>
                </div>
                <div className="p-2 rounded-lg bg-white border border-[#D5DEE9]">
                  <div className="text-[10px] text-[#667085] font-medium font-['Inter']">Wholesale COGS</div>
                  <div className="text-sm font-mono text-[#526176] mt-0.5">
                    {formatPaise(product.cost_paise)}
                  </div>
                </div>
                <div className="p-2 rounded-lg bg-white border border-[#D5DEE9]">
                  <div className="text-[10px] text-[#667085] font-medium font-['Inter']">Gross Margin</div>
                  <div className="text-sm font-bold text-[#067647] mt-0.5 font-mono">
                    {marginPct}%
                  </div>
                </div>
              </div>

              {/* Stock Levels */}
              <div className="flex items-center justify-between text-xs text-[#667085] px-1 font-['Inter']">
                <span>
                  Physical Inventory: <strong className="text-[#0F172A]">{product.inventory_quantity} units</strong>
                </span>
                <span>
                  Reserved for Orders: <strong className="text-[#0F172A]">{product.reserved_quantity || 0} units</strong>
                </span>
              </div>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center gap-1 border-b border-[#D5DEE9] pb-1">
            <button
              onClick={() => setActiveTab('overview')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                activeTab === 'overview'
                  ? 'bg-[#0F172A] text-white'
                  : 'text-[#526176] hover:text-[#0F172A] hover:bg-[#F8FAFC]'
              }`}
            >
              Complete Description & Specs
            </button>
            <button
              onClick={() => setActiveTab('marketplaces')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors flex items-center gap-1.5 ${
                activeTab === 'marketplaces'
                  ? 'bg-[#0F172A] text-white'
                  : 'text-[#526176] hover:text-[#0F172A] hover:bg-[#F8FAFC]'
              }`}
            >
              <span>Marketplace Channels</span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-[#F8FAFC] text-[#0F172A] border border-[#D5DEE9]">
                {marketplaces.length || 5}
              </span>
            </button>
            <button
              onClick={() => setActiveTab('recommendations')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors flex items-center gap-1.5 ${
                activeTab === 'recommendations'
                  ? 'bg-[#0F172A] text-white'
                  : 'text-[#526176] hover:text-[#0F172A] hover:bg-[#F8FAFC]'
              }`}
            >
              <Sparkles className="w-3 h-3 text-[#087F6B]" />
              <span>AI Recommendations</span>
              <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
                recommendations.length > 0
                  ? 'bg-[#FFF4DB] text-[#92400E] font-bold border border-[#92400E]/30'
                  : 'bg-[#F8FAFC] text-[#526176]'
              }`}>
                {recommendations.length > 0 ? recommendations.length : 'None'}
              </span>
            </button>
          </div>

          {/* TAB 1: Complete Description & Garment Specs */}
          {activeTab === 'overview' && (
            <div className="space-y-5 animate-fade-in">
              {/* Detailed Narrative */}
              <div className="p-4 rounded-xl bg-white border border-[#e4e4e7] space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#080808] flex items-center gap-1.5">
                  <Shirt className="w-3.5 h-3.5 text-[#146ef5]" />
                  <span>Garment Story & Description</span>
                </h4>
                <p className="text-xs text-[#3f3f46] leading-relaxed">
                  {product.description || 'Full handcrafted luxury garment tailored from pure natural fibers.'}
                </p>
              </div>

              {/* Apparel Specifications Matrix */}
              <div className="p-4 rounded-xl bg-white border border-[#e4e4e7] space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#080808]">
                  Technical Specifications & Fabric Craft
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className="p-2.5 rounded-lg bg-[#fafafa] border border-[#f4f4f5]">
                    <span className="text-[11px] text-[#71717a]">Fabric & Fiber</span>
                    <div className="font-semibold text-[#080808] mt-0.5">{attrs.fabric || '100% Cotton'}</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[#fafafa] border border-[#f4f4f5]">
                    <span className="text-[11px] text-[#71717a]">Weave & Weight</span>
                    <div className="font-semibold text-[#080808] mt-0.5">{attrs.weave || 'Fine Suiting Weave'}</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[#fafafa] border border-[#f4f4f5]">
                    <span className="text-[11px] text-[#71717a]">Fit & Silhouette</span>
                    <div className="font-semibold text-[#080808] mt-0.5">{attrs.fit || 'Tailored Fit'}</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[#fafafa] border border-[#f4f4f5]">
                    <span className="text-[11px] text-[#71717a]">Collar / Waist Band</span>
                    <div className="font-semibold text-[#080808] mt-0.5">{attrs.collar || attrs.waist || 'Structured Comfort Cut'}</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[#fafafa] border border-[#f4f4f5] sm:col-span-2">
                    <span className="text-[11px] text-[#71717a]">Wash & Garment Care</span>
                    <div className="font-semibold text-[#080808] mt-0.5">{attrs.care || 'Machine wash cold, gentle cycle, hang dry in shade.'}</div>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[#fafafa] border border-[#f4f4f5] sm:col-span-2">
                    <span className="text-[11px] text-[#71717a]">Production Origin</span>
                    <div className="font-semibold text-[#080808] mt-0.5">{attrs.origin || 'Made in India'}</div>
                  </div>
                </div>
              </div>

              {/* Sizes Available */}
              <div className="p-4 rounded-xl bg-white border border-[#e4e4e7] space-y-2">
                <span className="text-[11px] font-semibold text-[#71717a] uppercase tracking-wider">
                  Active Size Matrix:
                </span>
                <div className="flex flex-wrap gap-2 pt-1">
                  {(attrs.sizes || ['38', '40', '42', '44']).map((size: string) => (
                    <span
                      key={size}
                      className="px-3 py-1 bg-[#f4f4f5] hover:bg-[#e4e4e7] border border-[#d4d4d8] rounded-md text-xs font-semibold text-[#080808]"
                    >
                      {size}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Marketplaces Where Placed */}
          {activeTab === 'marketplaces' && (
            <div className="space-y-4 animate-fade-in">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[#080808]">
                    Marketplace Distribution & Channel Placement
                  </h4>
                  <p className="text-[11px] text-[#71717a] mt-0.5">
                    Live channel sync across Amazon, Flipkart, Myntra, Meesho, and Vastram Direct.
                  </p>
                </div>
                <span className="text-[11px] font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  ⚡ 5 Channels Connected
                </span>
              </div>

              <div className="space-y-2.5">
                {marketplaces.map((m: any) => {
                  const isAmazon = m.code === 'AMAZON';
                  const isFlipkart = m.code === 'FLIPKART';
                  const isMeesho = m.code === 'MEESHO';
                  const isMyntra = m.code === 'MYNTRA';
                  const isWhatsApp = m.code === 'WHATSAPP';

                  const badgeColor =
                    m.status.includes('ACTIVE')
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      : m.status.includes('PAUSED')
                      ? 'bg-amber-50 text-amber-800 border-amber-200'
                      : 'bg-[#f4f4f5] text-[#71717a] border-[#e4e4e7]';

                  return (
                    <div
                      key={m.code}
                      className="p-3.5 rounded-xl border border-[#e4e4e7] bg-white hover:border-[#146ef5] transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs"
                    >
                      {/* Marketplace Info */}
                      <div className="flex items-center gap-3">
                        <div className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs ${
                          isAmazon
                            ? 'bg-[#232f3e] text-amber-400'
                            : isFlipkart
                            ? 'bg-[#2874f0] text-yellow-300'
                            : isMeesho
                            ? 'bg-[#f43397] text-white'
                            : isMyntra
                            ? 'bg-[#ff3f6c] text-white'
                            : 'bg-[#25d366] text-white'
                        }`}>
                          {isAmazon ? 'a' : isFlipkart ? 'fk' : isMeesho ? 'M' : isMyntra ? 'My' : 'WA'}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h5 className="text-xs font-bold text-[#080808]">
                              {m.name}
                            </h5>
                            <span className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded border ${badgeColor}`}>
                              {m.status}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 text-[11px] text-[#71717a] mt-0.5">
                            <span className="font-mono">{m.listing_id}</span>
                            <span>•</span>
                            <span>Fee: <strong>{m.fee_percent}%</strong></span>
                            <span>•</span>
                            <span>{m.fulfillment}</span>
                          </div>
                        </div>
                      </div>

                      {/* Right: Listed Price + Orders Today */}
                      <div className="flex items-center justify-between sm:justify-end gap-4 border-t sm:border-t-0 pt-2 sm:pt-0 border-[#f4f4f5]">
                        <div className="text-left sm:text-right">
                          <div className="text-xs font-bold text-[#080808]">
                            {formatPaise(m.price_paise)}
                          </div>
                          <div className="text-[10px] text-[#71717a]">
                            Today: <strong>{m.orders_today} orders</strong>
                          </div>
                        </div>
                        <div className="text-right">
                          {m.status.includes('ACTIVE') ? (
                            <span className="text-[10px] text-emerald-700 font-semibold flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                              <span>Live</span>
                            </span>
                          ) : m.status.includes('PAUSED') ? (
                            <span className="text-[10px] text-amber-700 font-semibold">
                              Paused
                            </span>
                          ) : (
                            <span className="text-[10px] text-[#71717a] font-medium">
                              Not Listed
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 3: AI Recommendations for this Product */}
          {activeTab === 'recommendations' && (
            <div className="space-y-4 animate-fade-in">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[#080808] flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                    <span>Autonomous Product Growth Recommendations</span>
                  </h4>
                  <p className="text-[11px] text-[#71717a] mt-0.5">
                    Channel migration, pairing bundles, and price optimization tailored for this SKU.
                  </p>
                </div>
              </div>

              {/* If NO recommendations -> Show "None" as explicitly requested by user */}
              {recommendations.length === 0 ? (
                <div className="p-8 rounded-xl bg-[#fafafa] border border-[#e4e4e7] text-center space-y-3">
                  <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 mx-auto flex items-center justify-center shadow-2xs">
                    <CheckCircle2 className="w-6 h-6" />
                  </div>
                  <div className="space-y-1">
                    <div className="inline-block px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-900 border border-emerald-300">
                      Recommendations: None
                    </div>
                    <h5 className="text-sm font-bold text-[#080808] mt-2">
                      Channel Placement & Margin are Optimal
                    </h5>
                    <p className="text-xs text-[#71717a] max-w-md mx-auto leading-relaxed">
                      All marketplace placements across Amazon, Myntra, and WhatsApp Direct are currently performing at target equilibrium. Gross margin is stable at {marginPct}% with zero excess inventory exposure. No automated interventions required.
                    </p>
                  </div>
                </div>
              ) : (
                /* Active Recommendations List */
                <div className="space-y-3">
                  {recommendations.map((rec: any) => {
                    const isApplied = appliedActions[rec.id];
                    const isLoading = actionLoading === rec.id;

                    return (
                      <div
                        key={rec.id}
                        className={`p-4 rounded-xl border transition-all space-y-3 ${
                          isApplied
                            ? 'bg-emerald-50/70 border-emerald-300'
                            : 'bg-white border-[#e4e4e7] hover:border-[#146ef5] shadow-xs'
                        }`}
                      >
                        {/* Header: Badge + Impact */}
                        <div className="flex items-center justify-between">
                          <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                            rec.type === 'CHANNEL_SHIFT'
                              ? 'bg-blue-50 text-blue-800 border-blue-200'
                              : rec.type === 'BUNDLE_PAIR'
                              ? 'bg-purple-50 text-purple-800 border-purple-200'
                              : rec.type === 'INVENTORY_CRITICAL'
                              ? 'bg-rose-50 text-rose-800 border-rose-200'
                              : 'bg-emerald-50 text-emerald-800 border-emerald-200'
                          }`}>
                            {rec.badge}
                          </span>
                          <span className="text-xs font-bold text-emerald-700 font-mono">
                            {rec.impact}
                          </span>
                        </div>

                        {/* Title & Description */}
                        <div>
                          <h5 className="text-xs font-bold text-[#080808]">
                            {rec.title}
                          </h5>
                          <p className="text-xs text-[#52525b] mt-1 leading-relaxed">
                            {rec.description}
                          </p>
                        </div>

                        {/* If Pairing Bundle -> Show Paired Product Thumbnail */}
                        {rec.pair_sku && (
                          <div className="flex items-center gap-3 p-2.5 rounded-lg bg-[#fafafa] border border-[#e4e4e7]">
                            <img
                              src={rec.pair_image || '/clothing/khaki_chino.jpg'}
                              alt={rec.pair_name}
                              className="w-12 h-12 rounded-md object-cover bg-white border border-[#e4e4e7] shrink-0"
                            />
                            <div className="min-w-0 flex-1">
                              <span className="text-[10px] font-semibold text-[#146ef5] uppercase">
                                Recommended Pairing Item:
                              </span>
                              <div className="text-xs font-bold text-[#080808] truncate">
                                {rec.pair_name}
                              </div>
                              <div className="text-[11px] text-[#71717a] font-mono mt-0.5">
                                Combined Combo Price: <strong>{formatPaise(rec.pair_discount_price || 389900)}</strong>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Action Execution Button */}
                        <div className="pt-1">
                          {isApplied ? (
                            <div className="py-2 px-3 rounded-lg bg-emerald-100 text-emerald-800 text-xs font-bold flex items-center justify-center gap-1.5 border border-emerald-300">
                              <Check className="w-3.5 h-3.5" />
                              <span>Action Executed & Deployed to Channels</span>
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={() => handleExecuteAction(rec.id, rec.title)}
                              disabled={isLoading}
                              className={`w-full py-2.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition-all shadow-xs ${
                                rec.type === 'CHANNEL_SHIFT'
                                  ? 'bg-[#080808] text-white hover:bg-[#27272a]'
                                  : rec.type === 'BUNDLE_PAIR'
                                  ? 'bg-[#146ef5] text-white hover:bg-[#1366e2]'
                                  : rec.type === 'INVENTORY_CRITICAL'
                                  ? 'bg-rose-600 text-white hover:bg-rose-700'
                                  : 'bg-[#080808] text-white hover:bg-[#27272a]'
                              }`}
                            >
                              {isLoading ? (
                                <>
                                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                                  <span>Deploying to Channels...</span>
                                </>
                              ) : (
                                <>
                                  <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                                  <span>{rec.action_label || 'Apply Recommendation'}</span>
                                </>
                              )}
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

        </div>

        {/* Modal Bottom Footer Bar */}
        <div className="px-5 py-3 border-t border-[#f4f4f5] bg-[#fafafa] flex items-center justify-between">
          <div className="text-[11px] text-[#71717a]">
            Tap tabs above to view marketplaces or tailored recommendations.
          </div>
          <button
            onClick={onClose}
            className="py-1.5 px-4 text-xs font-semibold border border-[#d4d4d8] text-[#080808] rounded-lg hover:bg-white transition-colors"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
}
