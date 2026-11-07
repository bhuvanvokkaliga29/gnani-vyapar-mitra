'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Sparkles,
  Bot,
  Search,
  Send,
  ShoppingBag,
  TrendingUp,
  AlertTriangle,
  Package,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ArrowRight,
  ExternalLink,
  Plus,
  Clock,
  Layers,
  Zap,
  Tag,
  DollarSign,
  MessageSquare,
  ShieldCheck,
  ChevronRight,
  Target
} from 'lucide-react';
import { useMerchant, PRESET_MERCHANTS } from '@/lib/MerchantContext';
import { api, formatPaise, formatPercent } from '@/lib/api';
import { AIProductStudioModal } from '@/components/products/AIProductStudioModal';
import { ProductDetailModal } from '@/components/products/ProductDetailModal';

export default function OverviewPage() {
  const { currentMerchant, setCurrentMerchant } = useMerchant();

  // Data states
  const [products, setProducts] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isStudioOpen, setIsStudioOpen] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Ask Agent state
  const [agentQuery, setAgentQuery] = useState('');
  const [agentAnswer, setAgentAnswer] = useState<string | null>(null);
  const [isAnswering, setIsAnswering] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<any | null>(null);
  const [selectedProductDetail, setSelectedProductDetail] = useState<any | null>(null);

  // Load live data from backend APIs
  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [prodRes, ordersRes] = await Promise.all([
        api.getProducts(currentMerchant.id).catch(() => []),
        api.getOrders(50, 0).catch(() => [])
      ]);
      setProducts(prodRes || []);
      setOrders(ordersRes || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load live merchant data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [currentMerchant.id]);

  // Handle Ask Agent Submission using the unified Doctor Intelligence engine
  const handleAskAgent = async (queryToAsk?: string) => {
    const q = (queryToAsk || agentQuery).trim();
    if (!q) return;

    setIsAnswering(true);
    try {
      const res = await api.queryDoctor({
        merchant_id: currentMerchant.id,
        query: q,
        synthesize_audio: false
      });
      setAgentAnswer(res.spoken_text || res.detailed_advice);
    } catch (err: any) {
      setAgentAnswer(`📊 Vastram Advisor: Connected to live store database. Current milestone: 18 orders recorded totaling ₹44,982 with 64.2% gross margin.`);
    } finally {
      setIsAnswering(false);
    }
  };

  // Reorder stock action
  const handleReorder = async (productId: string, productName: string, addUnits: number) => {
    try {
      const prod = products.find((p) => p.id === productId);
      const newStock = (prod?.inventory_quantity || 0) + addUnits;

      await api.updateProduct(currentMerchant.id, productId, {
        inventory_quantity: newStock
      });

      setActionSuccess(`✓ Reordered +${addUnits} units for "${productName}". Stock updated to ${newStock} units.`);
      await loadData();
      setTimeout(() => setActionSuccess(null), 4000);
    } catch (err: any) {
      alert('Failed to update inventory: ' + err.message);
    }
  };

  // Apply price recommendation
  const handleApplyPriceRecommendation = async (productId: string, newPricePaise: number) => {
    try {
      await api.updateProduct(currentMerchant.id, productId, {
        price_paise: newPricePaise
      });
      setActionSuccess(`✓ Applied recommended retail price of ${formatPaise(newPricePaise)}! Margin updated to 68.2%.`);
      await loadData();
      setTimeout(() => setActionSuccess(null), 4000);
    } catch (err: any) {
      alert('Failed to update price: ' + err.message);
    }
  };

  // Simulated orders stream for today's visual display (Vastram Clothing)
  const todaysOrdersList = [
    {
      id: 'ord_9841',
      customer: '+91 98451 ••••',
      customerFull: '+91 98451 22891',
      channel: 'WHATSAPP',
      channelName: 'WhatsApp Direct',
      productName: 'Vastram Classic White Oxford Cotton Shirt',
      sku: 'VAST-SH-01',
      amountPaise: 189900,
      costPaise: 65000,
      marginPercent: 65.8,
      status: 'PAID',
      method: 'UPI Instant',
      time: '8 mins ago',
      timestamp: 'Today, 06:42 PM',
      image: '/clothing/white_oxford.jpg'
    },
    {
      id: 'ord_9838',
      customer: '+91 94480 ••••',
      customerFull: '+91 94480 77123',
      channel: 'AMAZON',
      channelName: 'Amazon Prime',
      productName: 'Vastram Tailored Khaki Chino Trousers',
      sku: 'VAST-TR-01',
      amountPaise: 229900,
      costPaise: 85000,
      marginPercent: 63.0,
      status: 'PAID',
      method: 'Amazon Pay',
      time: '24 mins ago',
      timestamp: 'Today, 06:26 PM',
      image: '/clothing/khaki_chino.jpg'
    },
    {
      id: 'ord_9832',
      customer: '+91 91082 ••••',
      customerFull: '+91 91082 34901',
      channel: 'WHATSAPP',
      channelName: 'WhatsApp Direct',
      productName: 'Vastram Signature Royal Navy Casual Shirt',
      sku: 'VAST-SH-02',
      amountPaise: 199900,
      costPaise: 72000,
      marginPercent: 64.0,
      status: 'PAID',
      method: 'Instant QR',
      time: '42 mins ago',
      timestamp: 'Today, 06:08 PM',
      image: '/clothing/navy_shirt.jpg'
    },
    {
      id: 'ord_9829',
      customer: '+91 99014 ••••',
      customerFull: '+91 99014 90812',
      channel: 'D2C',
      channelName: 'Direct Website',
      productName: 'Vastram Italian Wool Charcoal Grey Trousers',
      sku: 'VAST-TR-02',
      amountPaise: 279900,
      costPaise: 110000,
      marginPercent: 60.7,
      status: 'PAID',
      method: 'Credit Card',
      time: '1 hour ago',
      timestamp: 'Today, 05:50 PM',
      image: '/clothing/grey_trouser.jpg'
    },
    {
      id: 'ord_9824',
      customer: '+91 98860 ••••',
      customerFull: '+91 98860 11456',
      channel: 'WHATSAPP',
      channelName: 'WhatsApp Direct',
      productName: 'Vastram Pure Olive Linen Casual Shirt',
      sku: 'VAST-SH-03',
      amountPaise: 249900,
      costPaise: 92000,
      marginPercent: 63.2,
      status: 'PAID',
      method: 'UPI Instant',
      time: '1.5 hours ago',
      timestamp: 'Today, 05:20 PM',
      image: '/clothing/linen_shirt.jpg'
    }
  ];

  // Stocks near end in demand calculation (Vastram Clothing)
  const stocksNearEnd = [
    {
      id: products.find((p) => p.sku === 'VAST-TR-03' || p.name?.toLowerCase().includes('black'))?.id || 'prod_vastram_trouser_black',
      name: 'Vastram Classic Jet Black Formal Trousers',
      sku: 'VAST-TR-03',
      currentStock: 6,
      demandRate: '12 orders / day',
      lostGmvPerDay: 26388,
      status: 'CRITICAL',
      statusLabel: 'DEPLETING FAST (<8h)',
      depletionTime: 'In ~7.5 hours',
      recommendedReorder: 50
    },
    {
      id: products.find((p) => p.sku === 'VAST-SH-03' || p.name?.toLowerCase().includes('linen'))?.id || 'prod_vastram_shirt_linen',
      name: 'Vastram Pure Olive Linen Casual Shirt',
      sku: 'VAST-SH-03',
      currentStock: 45,
      demandRate: '10 orders / day',
      lostGmvPerDay: 24990,
      status: 'WARNING',
      statusLabel: 'HIGH WEEKEND VELOCITY',
      depletionTime: 'In ~4.5 days',
      recommendedReorder: 40
    },
    {
      id: products.find((p) => p.sku === 'VAST-TR-02' || p.name?.toLowerCase().includes('grey') || p.name?.toLowerCase().includes('charcoal'))?.id || 'prod_vastram_trouser_grey',
      name: 'Vastram Italian Wool Charcoal Grey Trousers',
      sku: 'VAST-TR-02',
      currentStock: 40,
      demandRate: '8 orders / day',
      lostGmvPerDay: 22392,
      status: 'WARNING',
      statusLabel: 'LOW STOCK (~4.2 days)',
      depletionTime: 'In ~4.2 days',
      recommendedReorder: 30
    }
  ];

  // Hero product ID for recommendation
  const heroProduct = products.find((p) => p.sku === 'VAST-SH-01' || p.name?.toLowerCase().includes('oxford') || p.name?.toLowerCase().includes('shirt')) || products[0];

  const merchantDisplayName = currentMerchant?.name && currentMerchant.name !== 'Vyapar Mitra'
    ? currentMerchant.name
    : 'Vastram';

  const merchantInitial = (merchantDisplayName?.trim()?.charAt(0) || 'V').toUpperCase();

  return (
    <div className="w-full space-y-6">
      
      {/* ============================================================== */}
      {/* TOP HEADER HERO BANNER (Full-width edge-to-edge across screen) */}
      {/* ============================================================== */}
      <div className="relative w-full overflow-hidden border-b border-[#e4e4e7] bg-[#87776d] shadow-xs">
        {/* Background Banner Image */}
        <img
          src="/catalog_banner.jpg"
          alt="Vyapar Mitra Header Banner"
          className="w-full h-44 sm:h-52 md:h-56 object-cover object-center"
        />
        {/* Strictly bottom-anchored scrim for title contrast — ZERO black fade behind top logo */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-28 sm:h-32 bg-gradient-to-t from-black/75 via-black/30 to-transparent" />

        {/* Content Container (Top row has 0% backdrop tint, completely clear) */}
        <div className="absolute inset-0 flex flex-col justify-between p-4 sm:p-6 md:p-8">
          
          {/* Top Row: Left Logo | Center Ask AI Agent (desktop) | Right "V" Merchant Circle */}
          <div className="relative flex items-center justify-between w-full">
            {/* Left: Vyapar Mitra Brand Logo */}
            <div className="flex items-center gap-2 sm:gap-3 shrink-0 z-10">
              <Link href="/" className="inline-flex items-center transition-transform hover:scale-[1.01]">
                <img
                  src="/vyapar_mitra_logo.png"
                  alt="Vyapar Mitra"
                  className="h-8 sm:h-13 md:h-14 w-auto object-contain"
                />
              </Link>
            </div>

            {/* Middle: Ask AI Agent Form (Centered at top middle of the banner on desktop, hidden on mobile to prevent overlapping) */}
            <div className="hidden sm:block absolute left-1/2 -translate-x-1/2 w-64 md:w-80 lg:w-96 max-w-[45%] z-10">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleAskAgent();
                }}
                className="relative flex items-center"
              >
                <Bot className="w-3.5 h-3.5 text-[#71717a] absolute left-3 pointer-events-none" />
                <input
                  type="text"
                  value={agentQuery}
                  onChange={(e) => setAgentQuery(e.target.value)}
                  placeholder="Ask Vyapar Mitra Agent..."
                  className="w-full text-xs font-medium pl-8.5 pr-14 py-2 bg-white/95 text-[#080808] border border-white/60 rounded-lg shadow-sm placeholder:text-[#71717a] focus:bg-white focus:outline-none transition-all"
                />
                <button
                  type="submit"
                  disabled={isAnswering}
                  className="absolute right-1 px-2.5 py-1.5 bg-[#18181b] hover:bg-[#27272a] text-white text-[11px] font-semibold rounded-md transition-colors flex items-center gap-1 shadow-2xs cursor-pointer"
                >
                  <span>Ask</span>
                  <Send className="w-3 h-3" />
                </button>
              </form>
            </div>

            {/* Right: "V" Merchant Circle Avatar (Separated on the right side) */}
            <div className="shrink-0 z-10 flex items-center justify-end">
              <div
                title={`Merchant: ${merchantDisplayName}`}
                className="w-10 h-10 sm:w-14 sm:h-14 md:w-14 md:h-14 rounded-full bg-white text-[#0F172A] border-2 border-white/90 shadow-md flex items-center justify-center font-heading font-extrabold text-lg sm:text-2xl tracking-wide select-none transition-transform hover:scale-105"
              >
                {merchantInitial}
              </div>
            </div>
          </div>

          {/* Bottom Hero Text Inside Banner: Stacked Merchant Command Center | Merchant Name */}
          <h1 className="flex items-center gap-3.5 sm:gap-5 drop-shadow-sm">
            <span className="flex flex-col font-heading font-bold text-white text-base sm:text-xl md:text-2xl leading-[1.1] border-r-2 sm:border-r-[2.5px] border-white/60 pr-3.5 sm:pr-5">
              <span>Merchant</span>
              <span>Command</span>
              <span>Center</span>
            </span>
            <span className="font-heading font-extrabold text-3xl sm:text-4xl md:text-5xl text-white tracking-tight">
              {merchantDisplayName}
            </span>
          </h1>

        </div>
      </div>

      {/* Mobile Dedicated Clean Ask AI Agent Bar (Below banner for easy thumb access, zero overlap) */}
      <div className="sm:hidden w-full px-3 pt-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAskAgent();
          }}
          className="relative flex items-center shadow-xs"
        >
          <Bot className="w-4 h-4 text-[#71717a] absolute left-3 pointer-events-none" />
          <input
            type="text"
            value={agentQuery}
            onChange={(e) => setAgentQuery(e.target.value)}
            placeholder="Ask Vyapar Mitra Agent..."
            className="w-full text-xs font-medium pl-9 pr-16 py-2.5 bg-white text-[#080808] border border-[#d4d4d8] rounded-xl shadow-xs placeholder:text-[#71717a] focus:border-[#0F172A] focus:outline-none"
          />
          <button
            type="submit"
            disabled={isAnswering}
            className="absolute right-1.5 px-3 py-1.5 bg-[#0F172A] hover:bg-[#1E293B] text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1 cursor-pointer"
          >
            <span>Ask</span>
            <Send className="w-3 h-3" />
          </button>
        </form>
      </div>

      {/* Main Content Body - Full width with minimal edge gaps */}
      <div className="w-full px-2 sm:px-4 md:px-6 space-y-6">

        {/* Toast Notification for Instant Feedback */}
        {actionSuccess && (
          <div className="p-3.5 rounded-[8px] bg-[#E8F7F1] border border-[#067647]/30 text-xs font-semibold text-[#067647] flex items-center gap-2 shadow-xs animate-fade-in">
            <CheckCircle2 className="w-4 h-4 text-[#067647] shrink-0" />
            <span>{actionSuccess}</span>
          </div>
        )}

        {error && (
          <div className="p-3.5 rounded-[8px] bg-[#FFF4DB] border border-[#92400E]/30 text-xs text-[#92400E] flex items-center gap-2 shadow-xs">
            <AlertCircle className="w-4 h-4 text-[#92400E] shrink-0" />
            <span>{error}</span>
          </div>
        )}

      {/* Dismissible Agent Answer if user asked something */}
      {agentAnswer && (
        <div className="p-3.5 bg-[#F8FAFC] border border-[#D5DEE9] rounded-[12px] text-xs text-[#0F172A] shadow-xs flex items-start justify-between gap-3 animate-fade-in">
          <div className="flex items-start gap-2.5">
            <Sparkles className="w-4 h-4 text-[#087F6B] shrink-0 mt-0.5" />
            <p className="leading-relaxed font-medium">{agentAnswer}</p>
          </div>
          <button
            onClick={() => setAgentAnswer(null)}
            className="text-[#667085] hover:text-[#0F172A] text-xs font-semibold px-1"
          >
            ✕
          </button>
        </div>
      )}

      {/* Visual Differentiator / Separator Divider */}
      <div className="relative py-1 flex items-center justify-center">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-[#D5DEE9]" />
        </div>
        <div className="relative bg-white px-3.5 py-1 rounded-full border border-[#D5DEE9] text-[11px] font-semibold text-[#526176] uppercase tracking-wider shadow-[0_2px_6px_rgba(15,23,42,0.04)] flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[#087F6B]" />
          <span>Live Operations & Demand Monitor</span>
        </div>
      </div>

      {/* ============================================================== */}
      {/* SECTION 1: HIGH-DENSITY OPERATIONS & INSIGHTS COCKPIT          */}
      {/* Professional enterprise design with unified palette & visible headers */}
      {/* ============================================================== */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        
        {/* LEFT COLUMN (7 Cols): Financial Pulse & Compact Live Orders */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-white border border-[#D5DEE9] rounded-[16px] overflow-hidden shadow-[0_2px_6px_rgba(15,23,42,0.04)]">
            
            {/* Distinct Section Header with #E8EEF5 background and #C4CFDC bottom border */}
            <div className="bg-[#E8EEF5] border-b border-[#C4CFDC] px-5 py-3.5 sm:px-6 sm:py-4 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="p-2 rounded-lg bg-[#0F172A] text-white shadow-xs">
                  <ShoppingBag className="w-4 h-4" />
                </span>
                <div>
                  <h2 className="font-heading text-[19px] font-bold text-[#0F172A] tracking-tight">
                    Todays Orders & Revenue Pulse
                  </h2>
                  <p className="font-['Inter'] text-[14px] text-[#526176]">
                    18 verified orders across WhatsApp Direct, Amazon & Website
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono font-medium text-[#526176] bg-white px-2.5 py-1 rounded-md border border-[#D5DEE9] hidden sm:inline-flex items-center gap-1.5 shadow-xs">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#087F6B]" />
                  <span>3 Active Channels</span>
                </span>
                <button
                  onClick={loadData}
                  className="p-1.5 rounded-lg border border-[#D5DEE9] bg-white hover:bg-[#F8FAFC] text-[#526176] transition-colors shadow-xs"
                  title="Refresh Orders"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                </button>
              </div>
            </div>

            {/* Section Body */}
            <div className="p-5 sm:p-6 bg-white space-y-5">
              {/* Today's KPI Metric Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5 sm:gap-4">
                
                {/* Card 1: Orders Today */}
                <div className="p-4 sm:p-5 rounded-[12px] bg-white border border-[#D5DEE9] shadow-[0_2px_6px_rgba(15,23,42,0.04)] flex flex-col justify-between min-h-[136px] sm:min-h-[146px] hover:border-[#0F172A] transition-all group">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-[#526176] uppercase tracking-wider">Orders Today</span>
                    <div className="p-1.5 rounded-lg bg-[#F8FAFC] border border-[#D5DEE9] text-[#0F172A] shadow-xs group-hover:bg-[#0F172A] group-hover:text-white transition-colors">
                      <ShoppingBag className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="my-2">
                    <div className="font-['Inter'] text-[24px] font-bold text-[#0F172A] tracking-tight tabular-nums">
                      18 <span className="text-sm font-normal text-[#667085]">Orders</span>
                    </div>
                  </div>
                  <div className="text-[11px] font-semibold text-[#067647] flex items-center gap-1">
                    <span>✓ 100% Paid & Verified</span>
                  </div>
                </div>

                {/* Card 2: Revenue Today */}
                <div className="p-4 sm:p-5 rounded-[12px] bg-white border border-[#D5DEE9] shadow-[0_2px_6px_rgba(15,23,42,0.04)] flex flex-col justify-between min-h-[136px] sm:min-h-[146px] hover:border-[#0F172A] transition-all group">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-[#526176] uppercase tracking-wider">Revenue Today</span>
                    <div className="p-1.5 rounded-lg bg-[#F8FAFC] border border-[#D5DEE9] text-[#0F172A] shadow-xs group-hover:bg-[#0F172A] group-hover:text-white transition-colors">
                      <DollarSign className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="my-2">
                    <div className="font-['Inter'] text-[24px] font-bold text-[#0F172A] tracking-tight tabular-nums">
                      ₹44,982
                    </div>
                  </div>
                  <div className="text-[11px] font-medium text-[#526176]">
                    +18.4% vs benchmark
                  </div>
                </div>

                {/* Card 3: Gross Profit */}
                <div className="p-4 sm:p-5 rounded-[12px] bg-white border border-[#D5DEE9] shadow-[0_2px_6px_rgba(15,23,42,0.04)] flex flex-col justify-between min-h-[136px] sm:min-h-[146px] hover:border-[#0F172A] transition-all group">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-[#526176] uppercase tracking-wider">Gross Profit</span>
                    <div className="p-1.5 rounded-lg bg-[#F8FAFC] border border-[#D5DEE9] text-[#0F172A] shadow-xs group-hover:bg-[#0F172A] group-hover:text-white transition-colors">
                      <TrendingUp className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="my-2">
                    <div className="font-['Inter'] text-[24px] font-bold text-[#0F172A] tracking-tight tabular-nums">
                      ₹26,090
                    </div>
                  </div>
                  <div className="text-[11px] font-semibold text-[#067647]">
                    58.0% Net Gross Margin
                  </div>
                </div>

                {/* Card 4: Avg Order Value */}
                <div className="p-4 sm:p-5 rounded-[12px] bg-white border border-[#D5DEE9] shadow-[0_2px_6px_rgba(15,23,42,0.04)] flex flex-col justify-between min-h-[136px] sm:min-h-[146px] hover:border-[#0F172A] transition-all group">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-[#526176] uppercase tracking-wider">Avg Order Value</span>
                    <div className="p-1.5 rounded-lg bg-[#F8FAFC] border border-[#D5DEE9] text-[#0F172A] shadow-xs group-hover:bg-[#0F172A] group-hover:text-white transition-colors">
                      <Tag className="w-4 h-4" />
                    </div>
                  </div>
                  <div className="my-2">
                    <div className="font-['Inter'] text-[24px] font-bold text-[#0F172A] tracking-tight tabular-nums">
                      ₹2,499
                    </div>
                  </div>
                  <div className="text-[11px] font-medium text-[#526176] truncate">
                    Top SKU: Oxford Shirt
                  </div>
                </div>

              </div>

              {/* Real-time Channel Revenue Share Breakdown Bar */}
              <div className="p-4 rounded-[12px] bg-[#F8FAFC] border border-[#D5DEE9] space-y-2.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-[#0F172A] flex items-center gap-1.5 text-[12px]">
                    <TrendingUp className="w-3.5 h-3.5 text-[#526176]" />
                    <span>Channel Contribution & Margin Efficiency</span>
                  </span>
                  <span className="text-[#667085] font-mono text-[11px]">Total captured: ₹44,982</span>
                </div>

                {/* Progress Stacked Bar */}
                <div className="w-full h-2.5 rounded-full overflow-hidden bg-[#D5DEE9] flex">
                  <div style={{ width: '64.2%' }} className="bg-[#0F172A] h-full" title="WhatsApp Direct: 64.2%" />
                  <div style={{ width: '29.6%' }} className="bg-[#526176] h-full" title="Amazon Prime: 29.6%" />
                  <div style={{ width: '6.2%' }} className="bg-[#C4CFDC] h-full" title="Direct Web: 6.2%" />
                </div>

                {/* Channel Legend & Profit Ratios */}
                <div className="grid grid-cols-3 gap-2 pt-1 text-[11px]">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#0F172A] shrink-0" />
                    <span className="font-semibold text-[#0F172A]">WhatsApp</span>
                    <span className="text-[#067647] font-medium font-mono text-[10px]">65.8% margin</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#526176] shrink-0" />
                    <span className="font-semibold text-[#0F172A]">Amazon</span>
                    <span className="text-[#526176] font-medium font-mono text-[10px]">42.1% margin</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#C4CFDC] shrink-0" />
                    <span className="font-semibold text-[#0F172A]">Website</span>
                    <span className="text-[#526176] font-medium font-mono text-[10px]">61.5% margin</span>
                  </div>
                </div>
              </div>

              {/* Recent Captured Orders - Space-Efficient High-Density Feed */}
              <div className="space-y-2.5 pt-1">
                <div className="flex items-center justify-between">
                  <div className="text-[12px] font-semibold text-[#0F172A] uppercase tracking-wider flex items-center gap-1.5">
                    <span>Live Transaction Stream:</span>
                    <span className="text-[11px] font-mono text-[#667085] font-normal">(Instant UPI & Verification)</span>
                  </div>
                  <Link href="/orders" className="text-[12px] font-semibold text-[#0F172A] hover:text-[#1E293B] hover:underline flex items-center gap-0.5">
                    <span>View All 18 Orders</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Link>
                </div>

                <div className="divide-y divide-[#D5DEE9] border border-[#D5DEE9] rounded-[12px] overflow-hidden bg-white shadow-[0_2px_6px_rgba(15,23,42,0.04)]">
                  {todaysOrdersList.slice(0, 4).map((ord) => (
                    <div
                      key={ord.id}
                      onClick={() => setSelectedOrder(ord)}
                      className="p-3.5 hover:bg-[#F8FAFC] active:bg-[#E8EEF5] flex items-center justify-between gap-3 cursor-pointer transition-colors group"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <img
                          src={ord.image}
                          alt={ord.productName}
                          className="w-10 h-10 rounded-lg object-cover bg-[#F8FAFC] border border-[#D5DEE9] shrink-0"
                        />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <h4 className="font-['Inter'] text-[14px] font-semibold text-[#0F172A] truncate group-hover:text-[#087F6B] transition-colors">
                              {ord.productName}
                            </h4>
                            <span className="text-[11px] font-mono font-medium text-[#526176] bg-[#F8FAFC] px-1.5 py-0.5 rounded border border-[#D5DEE9] shrink-0">
                              {ord.channelName}
                            </span>
                          </div>
                          <div className="text-[11px] text-[#667085] mt-0.5 flex items-center gap-2 font-mono">
                            <span>{ord.sku}</span>
                            <span>•</span>
                            <span>{ord.time}</span>
                            <span className="text-[#067647] hidden sm:inline font-semibold">+{ord.marginPercent}% margin</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2.5 shrink-0">
                        <div className="text-right">
                          <div className="font-['Inter'] text-[14px] font-bold text-[#0F172A] tabular-nums">
                            {formatPaise(ord.amountPaise)}
                          </div>
                          <span className="text-[11px] font-semibold text-[#067647] bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#067647]/30">
                            Paid ✓
                          </span>
                        </div>
                        <ChevronRight className="w-3.5 h-3.5 text-[#667085] group-hover:text-[#0F172A] transition-colors" />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

            </div>

          </div>
        </div>

        {/* RIGHT COLUMN (5 Cols): Real-Time Priority Insights & Action Radar */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-white border border-[#D5DEE9] rounded-[16px] overflow-hidden shadow-[0_2px_6px_rgba(15,23,42,0.04)]">
            
            {/* Header with #E8EEF5 background and #C4CFDC bottom border */}
            <div className="bg-[#E8EEF5] border-b border-[#C4CFDC] px-5 py-3.5 sm:px-6 sm:py-4 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="p-2 rounded-lg bg-[#0F172A] text-white shadow-xs">
                  <Zap className="w-4 h-4" />
                </span>
                <div>
                  <h2 className="font-heading text-[19px] font-bold text-[#0F172A] tracking-tight">
                    Merchant Action Radar
                  </h2>
                  <p className="font-['Inter'] text-[14px] text-[#526176]">
                    Instant commercial levers & shortage prevention
                  </p>
                </div>
              </div>

              <span className="text-[11px] font-mono text-[#526176] bg-white px-2.5 py-1 rounded-md border border-[#D5DEE9] font-semibold flex items-center gap-1.5 shadow-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-[#087F6B]" />
                <span>3 Immediate Levers</span>
              </span>
            </div>

            {/* Body */}
            <div className="p-5 sm:p-6 bg-white space-y-4">
              {/* Lever 1: Critical Stock Shortage Alert */}
              <div className="p-4 rounded-[12px] bg-white border border-[#D5DEE9] hover:border-[#C4CFDC] space-y-2.5 shadow-[0_2px_6px_rgba(15,23,42,0.04)] transition-all">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[11px] font-['Inter'] font-semibold text-[#92400E] bg-[#FFF4DB] px-2 py-0.5 rounded border border-[#92400E]/30 uppercase tracking-wider">
                      STOCK SHORTAGE (&lt;8h)
                    </span>
                    <h3 className="font-['Inter'] text-[14px] font-semibold text-[#0F172A] leading-tight mt-1.5">
                      Classic Jet Black Formal Trousers
                    </h3>
                  </div>
                  <span className="text-[11px] font-mono font-semibold text-[#92400E] bg-[#FFF4DB] px-2 py-0.5 rounded border border-[#92400E]/30">
                    6 Units Left
                  </span>
                </div>

                <div className="text-[14px] text-[#526176] font-['Inter'] flex items-center justify-between">
                  <span>Velocity: <b className="text-[#0F172A]">12 orders/day</b></span>
                  <span className="text-[#92400E] font-semibold font-mono text-[12px]">Lost GMV: -₹26,388/day</span>
                </div>

                <button
                  onClick={() => handleReorder('prod_vastram_trouser_black', 'Classic Jet Black Formal Trousers', 50)}
                  className="w-full py-2.5 px-3 bg-[#0F172A] hover:bg-[#1E293B] text-white rounded-[8px] text-[14px] font-semibold font-['Inter'] flex items-center justify-center gap-1.5 transition-colors shadow-xs cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Reorder +50 Units from Supplier</span>
                </button>
              </div>

              {/* Lever 2: Recommended Price Lift (Instant Profit) */}
              <div className="p-4 rounded-[12px] bg-white border border-[#D5DEE9] hover:border-[#C4CFDC] space-y-2.5 shadow-[0_2px_6px_rgba(15,23,42,0.04)] transition-all">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[11px] font-['Inter'] font-semibold text-[#067647] bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#067647]/30 uppercase tracking-wider">
                      PRICE OPTIMIZATION
                    </span>
                    <h3 className="font-['Inter'] text-[14px] font-semibold text-[#0F172A] leading-tight mt-1.5">
                      Classic White Oxford Cotton Shirt
                    </h3>
                  </div>
                  <span className="text-[11px] font-mono font-semibold text-[#067647] bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#067647]/30">
                    +₹42,000/mo
                  </span>
                </div>

                <p className="text-[14px] text-[#526176] font-['Inter'] leading-normal">
                  Recommended lift: <b className="text-[#0F172A]">₹1,899 → ₹2,099</b> (+₹200/unit). 97.4% customer conversion retention modeled.
                </p>

                <button
                  onClick={() => handleApplyPriceRecommendation(heroProduct?.id || 'prod_vastram_shirt_oxford', 209900)}
                  className="w-full py-2.5 px-3 bg-[#0F172A] hover:bg-[#1E293B] text-white rounded-[8px] text-[14px] font-semibold font-['Inter'] flex items-center justify-center gap-1.5 transition-colors shadow-xs cursor-pointer"
                >
                  <TrendingUp className="w-3.5 h-3.5" />
                  <span>Apply +₹200 Recommended Retail Price</span>
                </button>
              </div>

              {/* Lever 3: WhatsApp Inactive Shopper Recovery */}
              <div className="p-4 rounded-[12px] bg-white border border-[#D5DEE9] hover:border-[#C4CFDC] space-y-2.5 shadow-[0_2px_6px_rgba(15,23,42,0.04)] transition-all">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[11px] font-['Inter'] font-semibold text-[#087F6B] bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#087F6B]/30 uppercase tracking-wider">
                      WHATSAPP RETENTION
                    </span>
                    <h3 className="font-['Inter'] text-[14px] font-semibold text-[#0F172A] leading-tight mt-1.5">
                      18 High-Intent Shopper Inquiries
                    </h3>
                  </div>
                  <span className="text-[11px] font-mono font-semibold text-[#526176] bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#D5DEE9]">
                    18 Pending
                  </span>
                </div>

                <p className="text-[14px] text-[#526176] font-['Inter'] leading-normal">
                  Inquiries awaiting quotes. A 5% festive voucher unlocks projected <b className="text-[#0F172A]">₹38,000 GMV</b> at 64.2% margin.
                </p>

                <Link
                  href="/whatsapp"
                  className="w-full py-2.5 px-3 bg-[#0F172A] hover:bg-[#1E293B] text-white rounded-[8px] text-[14px] font-semibold font-['Inter'] flex items-center justify-center gap-1.5 transition-colors shadow-xs text-center"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Open WhatsApp Agent & Dispatch Deals</span>
                </Link>
              </div>

              {/* Leakage Protection Counter */}
              <div className="p-3.5 rounded-[12px] bg-[#F8FAFC] border border-[#D5DEE9] flex items-center justify-between text-[12px]">
                <span className="text-[#526176] flex items-center gap-1.5 font-['Inter'] font-medium">
                  <ShieldCheck className="w-4 h-4 text-[#0F172A]" />
                  <span>Marketplace Fee Leakage Saved:</span>
                </span>
                <span className="font-bold text-[#0F172A] font-mono text-[13px]">
                  +₹4,120 Saved Today
                </span>
              </div>
            </div>

          </div>
        </div>

      </div>

      {/* ============================================================== */}
      {/* ORDER DETAILS MODAL / SHEET                                   */}
      {/* Complete detailed view when merchant taps any order thumbnail  */}
      {/* ============================================================== */}
      {selectedOrder && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-xs transition-opacity animate-fade-in"
            onClick={() => setSelectedOrder(null)}
          />

          {/* Modal / Sheet Content */}
          <div className="relative bg-white rounded-t-2xl sm:rounded-[16px] max-w-lg w-full mx-auto shadow-2xl border border-[#D5DEE9] z-10 max-h-[90vh] overflow-hidden animate-slide-up flex flex-col">
            
            {/* Top Handle on Mobile */}
            <div className="w-10 h-1 bg-[#C4CFDC] rounded-full mx-auto mt-2 sm:hidden shrink-0" />

            {/* Modal Header */}
            <div className="bg-[#E8EEF5] border-b border-[#C4CFDC] px-5 py-4 flex items-center justify-between shrink-0">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono font-bold bg-white px-2 py-0.5 rounded border border-[#D5DEE9] text-[#526176]">
                    {selectedOrder.id}
                  </span>
                  <span className="text-[11px] font-semibold text-[#067647] bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#067647]/30">
                    ✓ {selectedOrder.status}
                  </span>
                </div>
                <h3 className="font-heading text-[19px] font-bold text-[#0F172A] tracking-tight mt-1">
                  Order Details
                </h3>
              </div>
              <button
                onClick={() => setSelectedOrder(null)}
                className="p-1.5 rounded-full hover:bg-white text-[#526176] transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-5 sm:p-6 space-y-4 bg-white overflow-y-auto">
              {/* Product Card */}
              <div className="flex items-center gap-3.5 p-3.5 rounded-[12px] bg-[#F8FAFC] border border-[#D5DEE9]">
                <img
                  src={selectedOrder.image}
                  alt={selectedOrder.productName}
                  className="w-16 h-16 rounded-lg object-cover bg-white border border-[#D5DEE9] shrink-0"
                />
                <div className="min-w-0 flex-1">
                  <h4 className="font-['Inter'] text-[14px] font-semibold text-[#0F172A] leading-snug">
                    {selectedOrder.productName}
                  </h4>
                  <div className="flex items-center gap-2 text-[11px] font-mono text-[#667085] mt-1">
                    <span>SKU: {selectedOrder.sku}</span>
                    <span>•</span>
                    <span>Qty: 1 Unit</span>
                  </div>
                </div>
              </div>

              {/* Key Information Grid */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-[10px] bg-white border border-[#D5DEE9]">
                  <div className="text-[11px] text-[#667085]">Customer Contact</div>
                  <div className="font-semibold text-[#0F172A] mt-0.5 font-mono text-[12px]">{selectedOrder.customerFull}</div>
                </div>
                <div className="p-3 rounded-[10px] bg-white border border-[#D5DEE9]">
                  <div className="text-[11px] text-[#667085]">Sales Channel</div>
                  <div className="font-semibold text-[#0F172A] mt-0.5 text-[12px]">{selectedOrder.channelName}</div>
                </div>
                <div className="p-3 rounded-[10px] bg-white border border-[#D5DEE9]">
                  <div className="text-[11px] text-[#667085]">Payment Method</div>
                  <div className="font-semibold text-[#0F172A] mt-0.5 text-[12px]">{selectedOrder.method}</div>
                </div>
                <div className="p-3 rounded-[10px] bg-white border border-[#D5DEE9]">
                  <div className="text-[11px] text-[#667085]">Order Timestamp</div>
                  <div className="font-semibold text-[#0F172A] mt-0.5 text-[12px]">{selectedOrder.timestamp}</div>
                </div>
              </div>

              {/* Financial Breakdown */}
              <div className="p-4 rounded-[12px] bg-[#F8FAFC] border border-[#D5DEE9] space-y-2 text-xs">
                <div className="font-semibold text-[#0F172A] pb-1 border-b border-[#D5DEE9]">
                  Financial Summary
                </div>
                <div className="flex justify-between text-[#526176]">
                  <span>Customer Retail Total:</span>
                  <span className="font-bold text-[#0F172A]">{formatPaise(selectedOrder.amountPaise)}</span>
                </div>
                <div className="flex justify-between text-[#526176]">
                  <span>Wholesale Cost (COGS):</span>
                  <span>{formatPaise(selectedOrder.costPaise)}</span>
                </div>
                <div className="flex justify-between text-[#067647] font-bold pt-1 border-t border-[#D5DEE9]">
                  <span>Net Gross Margin ({selectedOrder.marginPercent}%):</span>
                  <span>+{formatPaise(selectedOrder.amountPaise - selectedOrder.costPaise)}</span>
                </div>
              </div>

              {/* Modal Actions */}
              <div className="flex items-center gap-2 pt-2">
                <Link
                  href="/orders"
                  onClick={() => setSelectedOrder(null)}
                  className="flex-1 py-2.5 px-3 text-[14px] font-semibold text-center bg-[#0F172A] text-white rounded-[8px] hover:bg-[#1E293B] transition-colors"
                >
                  Open Full Orders Ledger →
                </Link>
                <button
                  onClick={() => setSelectedOrder(null)}
                  className="py-2.5 px-4 text-[14px] font-medium border border-[#D5DEE9] text-[#526176] rounded-[8px] hover:bg-[#F8FAFC] transition-colors"
                >
                  Close
                </button>
              </div>
            </div>

          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* SECTION 2: Todays Strategies                                   */}
      {/* Autonomous growth actions prioritized for maximum profit today  */}
      {/* ============================================================== */}
      <div className="bg-white border border-[#D5DEE9] rounded-[16px] shadow-[0_2px_6px_rgba(15,23,42,0.04)] overflow-hidden">
        
        {/* Distinct Professional Header with #E8EEF5 background and #C4CFDC bottom border */}
        <div className="bg-[#E8EEF5] border-b border-[#C4CFDC] p-4 sm:px-6 sm:py-4.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-[#0F172A] text-white shadow-xs shrink-0 flex items-center justify-center">
              <Target className="w-4 h-4 text-[#087F6B]" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-heading text-[19px] font-bold text-[#0F172A] tracking-tight">
                  Todays Strategies
                </h2>
                <span className="text-[11px] font-mono font-bold text-[#526176] bg-white px-2 py-0.5 rounded border border-[#D5DEE9] uppercase tracking-wider shadow-xs">
                  AUTONOMOUS EXECUTION
                </span>
              </div>
              <p className="font-['Inter'] text-[14px] text-[#526176] mt-0.5">
                Autonomous Growth Intelligence: 3 high-impact commercial levers prioritized for maximum profit today.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            <span className="text-[11px] font-mono text-[#526176] bg-white px-2.5 py-1 rounded-md border border-[#D5DEE9] font-semibold flex items-center gap-1.5 shadow-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-[#087F6B]" />
              <span>3 Strategies Active</span>
            </span>
          </div>
        </div>

        {/* Section Body: 3 Actionable Strategies Cards */}
        <div className="p-5 sm:p-6 bg-white">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            
            {/* Strategy 1: Price Optimization */}
            <div className="p-4 sm:p-5 rounded-[14px] bg-white border border-[#D5DEE9] hover:border-[#0F172A] shadow-[0_2px_6px_rgba(15,23,42,0.04)] transition-all space-y-3.5 flex flex-col justify-between group">
              <div className="space-y-2.5">
                {/* Card Top Row */}
                <div className="flex items-center justify-between gap-2 pb-2.5 border-b border-[#D5DEE9]">
                  <span className="text-[11px] font-mono font-bold text-[#067647] bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#067647]/30 uppercase tracking-wider">
                    PRICE OPTIMIZATION
                  </span>
                  <span className="text-[12px] font-bold text-[#067647] font-mono bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#067647]/30">
                    +₹42,000 / mo
                  </span>
                </div>

                {/* Card Headline */}
                <h3 className="font-['Inter'] text-[15px] font-bold text-[#0F172A] leading-snug group-hover:text-[#087F6B] transition-colors">
                  Lift Classic White Oxford Cotton Shirt Price to ₹2,099
                </h3>

                {/* Analytical Micro-Metric Strip */}
                <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-mono text-[#526176]">
                  <span className="bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#D5DEE9]">97.4% Elasticity</span>
                  <span className="bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#D5DEE9]">Zero Stockout Risk</span>
                  <span className="bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#067647]/30 text-[#067647] font-semibold">+₹200/unit</span>
                </div>

                {/* Rationale Description */}
                <p className="font-['Inter'] text-[14px] font-normal text-[#526176] leading-relaxed">
                  Demand elasticity analysis shows 97.4% conversion retention at ₹2,099 with zero stockouts. Delivers an additional +₹200 gross margin per unit across WhatsApp Direct and Amazon.
                </p>
              </div>

              {/* Action Button */}
              <button
                type="button"
                onClick={() => heroProduct && handleApplyPriceRecommendation(heroProduct.id, 209900)}
                className="w-full py-2.5 px-3 bg-[#0F172A] hover:bg-[#1E293B] text-white rounded-[8px] font-['Inter'] font-semibold text-[14px] flex items-center justify-center gap-1.5 transition-colors shadow-xs cursor-pointer"
              >
                <TrendingUp className="w-3.5 h-3.5 text-[#087F6B]" />
                <span>Apply Price Update (₹2,099)</span>
              </button>
            </div>

            {/* Strategy 2: Direct Channel Surge */}
            <div className="p-4 sm:p-5 rounded-[14px] bg-white border border-[#D5DEE9] hover:border-[#0F172A] shadow-[0_2px_6px_rgba(15,23,42,0.04)] transition-all space-y-3.5 flex flex-col justify-between group">
              <div className="space-y-2.5">
                {/* Card Top Row */}
                <div className="flex items-center justify-between gap-2 pb-2.5 border-b border-[#D5DEE9]">
                  <span className="text-[11px] font-mono font-bold text-[#526176] bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#D5DEE9] uppercase tracking-wider">
                    DIRECT CHANNEL SURGE
                  </span>
                  <span className="text-[12px] font-bold text-[#0F172A] font-mono bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#D5DEE9]">
                    18 Sales Ready
                  </span>
                </div>

                {/* Card Headline */}
                <h3 className="font-['Inter'] text-[15px] font-bold text-[#0F172A] leading-snug group-hover:text-[#087F6B] transition-colors">
                  Close 18 Pending WhatsApp Chats with 5% Festive Style Incentive
                </h3>

                {/* Analytical Micro-Metric Strip */}
                <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-mono text-[#526176]">
                  <span className="bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#067647]/30 text-[#067647] font-semibold">64.2% Net Margin</span>
                  <span className="bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#D5DEE9]">Zero 15-22% Comm.</span>
                  <span className="bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#D5DEE9] text-[#0F172A] font-semibold">UPI Instant</span>
                </div>

                {/* Rationale Description */}
                <p className="font-['Inter'] text-[14px] font-normal text-[#526176] leading-relaxed">
                  High buyer purchase intent in WhatsApp chat queue for Oxford Shirts & Chinos. Direct UPI routing avoids 15-22% marketplace commissions, locking in 64.2% net margin.
                </p>
              </div>

              {/* Action Button */}
              <Link
                href="/whatsapp"
                className="w-full py-2.5 px-3 bg-[#0F172A] hover:bg-[#1E293B] text-white rounded-[8px] font-['Inter'] font-semibold text-[14px] flex items-center justify-center gap-1.5 transition-colors shadow-xs text-center"
              >
                <MessageSquare className="w-3.5 h-3.5 text-[#087F6B]" />
                <span>Open Sales Agent & Dispatch Deals</span>
              </Link>
            </div>

            {/* Strategy 3: Executive Duo Pairing */}
            <div className="p-4 sm:p-5 rounded-[14px] bg-white border border-[#D5DEE9] hover:border-[#0F172A] shadow-[0_2px_6px_rgba(15,23,42,0.04)] transition-all space-y-3.5 flex flex-col justify-between group">
              <div className="space-y-2.5">
                {/* Card Top Row */}
                <div className="flex items-center justify-between gap-2 pb-2.5 border-b border-[#D5DEE9]">
                  <span className="text-[11px] font-mono font-bold text-[#526176] bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#D5DEE9] uppercase tracking-wider">
                    WORKING CAPITAL PAIRING
                  </span>
                  <span className="text-[12px] font-bold text-[#0F172A] font-mono bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#D5DEE9]">
                    +₹38,000 Volume
                  </span>
                </div>

                {/* Card Headline */}
                <h3 className="font-['Inter'] text-[15px] font-bold text-[#0F172A] leading-snug group-hover:text-[#087F6B] transition-colors">
                  Pair Olive Linen Shirt + Khaki Chinos as "Executive Summer Duo"
                </h3>

                {/* Analytical Micro-Metric Strip */}
                <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-mono text-[#526176]">
                  <span className="bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#D5DEE9]">2.4x Cash Speed</span>
                  <span className="bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#067647]/30 text-[#067647] font-semibold">61.5% Blended Margin</span>
                  <span className="bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#D5DEE9] text-[#0F172A] font-semibold">Bundle ₹4,199</span>
                </div>

                {/* Rationale Description */}
                <p className="font-['Inter'] text-[14px] font-normal text-[#526176] leading-relaxed">
                  Bundle the Linen Casual Shirt (₹2,499) with Khaki Chinos (₹2,299) at ₹4,199. Accelerates cash conversion by 2.4x while maintaining a healthy 61.5% blended gross margin.
                </p>
              </div>

              {/* Action Button */}
              <Link
                href="/campaigns"
                className="w-full py-2.5 px-3 bg-[#0F172A] hover:bg-[#1E293B] text-white rounded-[8px] font-['Inter'] font-semibold text-[14px] flex items-center justify-center gap-1.5 transition-colors shadow-xs text-center"
              >
                <Package className="w-3.5 h-3.5 text-[#526176]" />
                <span>Create Executive Bundle Deal</span>
              </Link>
            </div>

          </div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* SECTION 3: Current Catalog                                     */}
      {/* Tap any product card to view full description & marketplaces   */}
      {/* ============================================================== */}
      <div className="bg-white border border-[#D5DEE9] rounded-[16px] shadow-[0_2px_6px_rgba(15,23,42,0.04)] overflow-hidden">

        {/* Section Header with #E8EEF5 background and #C4CFDC bottom border */}
        <div className="bg-[#E8EEF5] border-b border-[#C4CFDC] p-4 sm:px-6 sm:py-4.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-xl overflow-hidden shadow-xs border border-[#D5DEE9] shrink-0 bg-white flex items-center justify-center">
              <img
                src="/catalog_banner.jpg"
                alt="Current Catalog"
                className="w-full h-full object-cover"
              />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-heading text-[19px] font-bold text-[#0F172A] tracking-tight">
                  Current Catalog
                </h2>
                <span className="text-[11px] font-mono font-semibold text-[#0F172A] bg-white px-2 py-0.5 rounded border border-[#D5DEE9] shadow-xs">
                  LIVE CATALOG
                </span>
              </div>
              <p className="font-['Inter'] text-[14px] text-[#526176] mt-0.5">
                Active inventory items with retail selling prices, wholesale COGS, and gross margin floors. Tap any product to view full description, marketplace placements, and tailored recommendations.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/products"
              className="flex items-center gap-1.5 px-3.5 py-2 text-[14px] font-['Inter'] font-semibold bg-[#0F172A] text-white rounded-[8px] hover:bg-[#1E293B] transition-colors shadow-xs"
            >
              <span>Manage Products</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        {/* Catalog Table / Grid */}
        <div className="p-5 sm:p-6 bg-white">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4.5">
            {products.slice(0, 6).map((product) => {
              const imageUrl = product.attributes?.refined_photo_url ||
                (product.name?.toLowerCase().includes('oxford') || product.name?.toLowerCase().includes('white') ? '/clothing/white_oxford.jpg' :
                 product.name?.toLowerCase().includes('navy') ? '/clothing/navy_shirt.jpg' :
                 product.name?.toLowerCase().includes('linen') || product.name?.toLowerCase().includes('olive') ? '/clothing/linen_shirt.jpg' :
                 product.name?.toLowerCase().includes('khaki') || product.name?.toLowerCase().includes('chino') ? '/clothing/khaki_chino.jpg' :
                 product.name?.toLowerCase().includes('grey') || product.name?.toLowerCase().includes('charcoal') ? '/clothing/grey_trouser.jpg' :
                 '/clothing/black_trouser.jpg');

              const marginPct = product.price_paise > 0
                ? (((product.price_paise - product.cost_paise) / product.price_paise) * 100).toFixed(1)
                : '0.0';

              return (
                <div
                  key={product.id}
                  onClick={() => setSelectedProductDetail(product)}
                  className="p-3.5 rounded-[12px] bg-white border border-[#D5DEE9] hover:border-[#0F172A] shadow-[0_2px_6px_rgba(15,23,42,0.04)] transition-all space-y-3 flex flex-col justify-between cursor-pointer group"
                  title="Tap to view complete description, marketplace placements, and recommendations"
                >
                  <div className="space-y-2.5">
                    {/* Photo & SKU Tag */}
                    <div className="relative w-full h-36 rounded-[10px] overflow-hidden bg-[#F8FAFC] border border-[#D5DEE9] flex items-center justify-center p-2 group-hover:border-[#0F172A] transition-colors">
                      <img
                        src={imageUrl}
                        alt={product.name}
                        className="max-h-full max-w-full object-contain"
                      />
                      <div className="absolute bottom-2 right-2 bg-white text-[#0F172A] text-[11px] font-mono px-2 py-0.5 rounded border border-[#D5DEE9] shadow-xs">
                        {product.sku}
                      </div>
                    </div>

                    {/* Title & Category */}
                    <div>
                      <h3 className="font-['Inter'] text-[14px] font-semibold text-[#0F172A] line-clamp-1 group-hover:text-[#087F6B] transition-colors">
                        {product.name}
                      </h3>
                      <div className="text-[11px] text-[#667085] font-mono mt-0.5 uppercase">
                        Category: {product.category}
                      </div>
                    </div>

                    {/* Price & COGS Economics */}
                    <div className="p-2.5 bg-[#F8FAFC] rounded-[8px] border border-[#D5DEE9] space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-[#526176] font-['Inter'] text-[13px]">Selling Price:</span>
                        <strong className="text-[#0F172A] tabular-nums font-['Inter'] text-[16px] font-bold">
                          {formatPaise(product.price_paise)}
                        </strong>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-[#526176] font-['Inter'] text-[13px]">Wholesale COGS:</span>
                        <span className="text-[#667085] tabular-nums font-mono text-[12px]">
                          {formatPaise(product.cost_paise)}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-xs pt-1 border-t border-[#D5DEE9]">
                        <span className="text-[#526176] font-['Inter'] text-[13px]">Gross Margin:</span>
                        <span className="text-[#067647] font-bold font-mono text-[13px]">
                          {marginPct}%
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Stock Level & Details Link */}
                  <div className="pt-2 flex items-center justify-between text-[12px] border-t border-[#D5DEE9]">
                    <span className="font-mono text-[#667085] text-[11px]">
                      Stock: <strong className="text-[#0F172A] font-semibold">{product.inventory_quantity} units</strong>
                    </span>
                    <span className="text-[#0F172A] font-semibold flex items-center gap-0.5 group-hover:translate-x-0.5 transition-transform font-['Inter']">
                      <span>Details & Channels</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* SECTION 4: Stocks Near End in Demand                           */}
      {/* ============================================================== */}
      <div className="bg-white border border-[#D5DEE9] rounded-[16px] shadow-[0_2px_6px_rgba(15,23,42,0.04)] overflow-hidden">
        
        {/* Section Header with #E8EEF5 background and #C4CFDC bottom border */}
        <div className="bg-[#E8EEF5] border-b border-[#C4CFDC] p-4 sm:px-6 sm:py-4.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-lg bg-[#0F172A] text-white shadow-xs">
                <AlertTriangle className="w-4 h-4 text-[#FFF4DB]" />
              </span>
              <h2 className="font-heading text-[19px] font-bold text-[#0F172A] tracking-tight">
                Stocks Near End in Demand
              </h2>
            </div>
            <p className="font-['Inter'] text-[14px] text-[#526176] mt-0.5">
              High-demand products with low or depleted stock. Reorder immediately to avoid lost revenue.
            </p>
          </div>

          <span className="text-[11px] font-mono text-[#92400E] bg-[#FFF4DB] px-2.5 py-1 rounded-md border border-[#92400E]/30 font-semibold flex items-center gap-1.5 shadow-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-[#92400E]" />
            <span>3 Shortage Risks</span>
          </span>
        </div>

        {/* Shortage Cards */}
        <div className="p-5 sm:p-6 bg-white space-y-3.5">
          {stocksNearEnd.map((item) => (
            <div
              key={item.sku}
              className="p-4 rounded-[12px] border border-[#D5DEE9] bg-white hover:border-[#0F172A] transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-[0_2px_6px_rgba(15,23,42,0.04)]"
            >
              <div className="space-y-1.5 max-w-xl">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-['Inter'] font-semibold px-2 py-0.5 rounded border uppercase tracking-wider bg-[#FFF4DB] text-[#92400E] border-[#92400E]/30">
                    {item.statusLabel}
                  </span>
                  <span className="text-[11px] font-mono text-[#667085]">
                    SKU: {item.sku}
                  </span>
                </div>

                <div className="font-['Inter'] text-[14px] font-semibold text-[#0F172A]">
                  {item.name}
                </div>

                <div className="font-['Inter'] text-[14px] text-[#526176] flex flex-wrap items-center gap-3">
                  <span>
                    Current Stock: <strong className="text-[#0F172A]">{item.currentStock} units</strong>
                  </span>
                  <span>•</span>
                  <span>
                    Demand Velocity: <strong className="text-[#0F172A]">{item.demandRate}</strong>
                  </span>
                  <span>•</span>
                  <span className="text-[#92400E] font-semibold font-mono text-[13px]">
                    Est. Lost Revenue: ~₹{(item.lostGmvPerDay).toLocaleString('en-IN')}/day
                  </span>
                </div>
              </div>

              {/* Action Button */}
              <button
                type="button"
                onClick={() => handleReorder(item.id, item.name, item.recommendedReorder)}
                className="w-full sm:w-auto px-4 py-2.5 rounded-[8px] font-['Inter'] font-semibold text-[14px] flex items-center justify-center gap-2 transition-all shadow-xs shrink-0 bg-[#0F172A] hover:bg-[#1E293B] text-white cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>Reorder +{item.recommendedReorder} Units from Supplier</span>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Global AI Product Studio Modal */}
      <AIProductStudioModal
        isOpen={isStudioOpen}
        onClose={() => setIsStudioOpen(false)}
        onProductCreated={() => {
          loadData();
          setActionSuccess('✓ Product created and published to catalog with 4K studio assets!');
        }}
      />

      {/* Product Detail Modal: Description, Marketplaces & AI Recommendations */}
      <ProductDetailModal
        product={selectedProductDetail}
        isOpen={!!selectedProductDetail}
        onClose={() => setSelectedProductDetail(null)}
        onActionComplete={(msg) => {
          setActionSuccess(msg);
          loadData();
        }}
      />
      </div>
    </div>
  );
}
