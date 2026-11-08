'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  Package,
  Stethoscope,
  Mic,
  Grid,
  TrendingUp,
  FileText,
  Users,
  MessageSquare,
  ShieldCheck,
  CreditCard,
  History,
  Sparkles,
  X,
  AlertTriangle,
  CheckCircle2,
  ChevronRight
} from 'lucide-react';
import { api } from '@/lib/api';

// 5 Primary Bottom Navigation Tabs (Instagram style)
const BOTTOM_NAV_ITEMS = [
  { href: '/', label: 'Overview', icon: LayoutDashboard },
  { href: '/products', label: 'Products', icon: Package },
  { href: '/doctor', label: 'Doctor', icon: Stethoscope },
  { href: '/voice-agent', label: 'Voice Agent', icon: Mic },
];

// Remaining features accessible via "More" / "Others" drawer
const MORE_FEATURES = [
  {
    href: '/channels',
    label: 'Channel Intelligence',
    icon: TrendingUp,
    description: 'Amazon, WhatsApp & Blinkit margin metrics',
    color: 'bg-emerald-50 text-emerald-600 border-emerald-200'
  },
  {
    href: '/listings',
    label: 'Listings',
    icon: FileText,
    description: 'Multi-channel catalog & inventory sync',
    color: 'bg-blue-50 text-blue-600 border-blue-200'
  },
  {
    href: '/campaigns',
    label: 'Campaigns',
    icon: Users,
    description: 'Automated WhatsApp promo & discount blasts',
    color: 'bg-purple-50 text-purple-600 border-purple-200'
  },
  {
    href: '/whatsapp',
    label: 'WhatsApp Live Agent',
    icon: MessageSquare,
    description: 'Meta Business Platform, phone simulator & webhook audits',
    color: 'bg-emerald-50 text-emerald-600 border-emerald-200'
  },
  {
    href: '/sales-agent',
    label: 'Sales Agent',
    icon: MessageSquare,
    description: 'Autonomous customer chat negotiations',
    color: 'bg-amber-50 text-amber-600 border-amber-200'
  },
  {
    href: '/policies',
    label: 'Policies & Approvals',
    icon: ShieldCheck,
    description: 'Margin protection & autonomous governance rules',
    color: 'bg-rose-50 text-rose-600 border-rose-200'
  },
  {
    href: '/orders',
    label: 'Orders & Payments',
    icon: CreditCard,
    description: 'Customer checkouts & verified payment receipts',
    color: 'bg-indigo-50 text-indigo-600 border-indigo-200'
  },
  {
    href: '/decisions',
    label: 'Decision Ledger',
    icon: History,
    description: 'Auditable traces of agent actions & auto-orders',
    color: 'bg-teal-50 text-teal-600 border-teal-200'
  },
  {
    href: '/learning',
    label: 'Learning Center',
    icon: Sparkles,
    description: 'Merchant AI memory, benchmarks & feedback loops',
    color: 'bg-orange-50 text-orange-600 border-orange-200'
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [resetSuccess, setResetSuccess] = useState(false);

  const handleResetDemo = async () => {
    setIsResetting(true);
    try {
      await api.resetDemoData('merch_atlas_travel');
      setResetSuccess(true);
      setTimeout(() => {
        setIsResetModalOpen(false);
        setResetSuccess(false);
        setIsMoreOpen(false);
        window.location.reload();
      }, 1000);
    } catch (err) {
      alert('Failed to reset demo data: ' + err);
    } finally {
      setIsResetting(false);
    }
  };

  // Determine if active route is inside the "More" drawer
  const isMoreActive = MORE_FEATURES.some(
    (item) => pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href))
  );

  const isVoicePage = pathname.startsWith('/voice-agent');

  return (
    <div className={`text-[#0F172A] flex flex-col font-sans max-w-full ${
      isVoicePage
        ? 'h-[100dvh] max-h-[100dvh] overflow-hidden bg-black select-none'
        : 'min-h-screen bg-[#F4F6FA] overflow-x-hidden'
    }`}>
      {/* Content Viewport with constrained height on Voice Agent to prevent outer scroll */}
      <main className={`flex-1 min-w-0 ${
        isVoicePage
          ? 'h-[calc(100dvh-3.75rem)] max-h-[calc(100dvh-3.75rem)] overflow-hidden bg-black'
          : 'bg-[#F4F6FA] pb-24 md:pb-20'
      }`}>
        {children}
      </main>

      {/* ============================================================== */}
      {/* INSTAGRAM-STYLE BOTTOM NAVIGATION (5 ITEMS)                    */}
      {/* 1: Overview | 2: Products | 3: Doctor | 4: Gnani Voice Agent | 5: More */}
      {/* ============================================================== */}
      <nav className="fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur-md border-t border-[#D5DEE9] px-2 py-1.5 shadow-[0_-4px_20px_rgba(15,23,42,0.06)] overflow-visible">
        <div className="max-w-xl mx-auto grid grid-cols-5 items-end pb-0.5">
          
          {/* Tab 1: Overview */}
          <Link
            href="/"
            onClick={() => setIsMoreOpen(false)}
            className={`flex flex-col items-center justify-center py-1 px-1 rounded-lg transition-all ${
              pathname === '/'
                ? 'text-[#0F172A] font-bold scale-105'
                : 'text-[#526176] hover:text-[#0F172A] font-medium'
            }`}
          >
            <div className={`p-1.5 rounded-full ${pathname === '/' ? 'bg-[#0F172A] text-white shadow-xs' : ''}`}>
              <LayoutDashboard className="w-4 h-4" />
            </div>
            <span className="text-[10px] tracking-tight mt-0.5">Overview</span>
          </Link>

          {/* Tab 2: Products */}
          <Link
            href="/products"
            onClick={() => setIsMoreOpen(false)}
            className={`flex flex-col items-center justify-center py-1 px-1 rounded-lg transition-all ${
              pathname.startsWith('/products')
                ? 'text-[#0F172A] font-bold scale-105'
                : 'text-[#526176] hover:text-[#0F172A] font-medium'
            }`}
          >
            <div className={`p-1.5 rounded-full ${pathname.startsWith('/products') ? 'bg-[#0F172A] text-white shadow-xs' : ''}`}>
              <Package className="w-4 h-4" />
            </div>
            <span className="text-[10px] tracking-tight mt-0.5">Products</span>
          </Link>

          {/* Tab 3: Growth Doctor */}
          <Link
            href="/doctor"
            onClick={() => setIsMoreOpen(false)}
            className={`flex flex-col items-center justify-center py-1 px-1 rounded-lg transition-all ${
              pathname.startsWith('/doctor')
                ? 'text-[#0F172A] font-bold scale-105'
                : 'text-[#526176] hover:text-[#0F172A] font-medium'
            }`}
          >
            <div className={`p-1.5 rounded-full ${pathname.startsWith('/doctor') ? 'bg-[#0F172A] text-white shadow-xs' : ''}`}>
              <Stethoscope className="w-4 h-4" />
            </div>
            <span className="text-[10px] tracking-tight mt-0.5">Doctor</span>
          </Link>

          {/* Tab 4: Gnani AI Voice Agent (Hero Prominence & Glowing Highlight) */}
          <Link
            href="/voice-agent"
            onClick={() => setIsMoreOpen(false)}
            aria-label="Gnani AI Voice Agent"
            className="relative flex flex-col items-center justify-end -mt-5 sm:-mt-6 pb-0.5 px-0.5 group transition-all transform hover:scale-105 cursor-pointer z-10"
          >
            {/* Subtle Pulsing Ambient Glowing Aura */}
            <span className="absolute top-0 w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-gradient-to-tr from-[#FF6F00] via-amber-400 to-[#FF6F00] opacity-75 blur-xs animate-pulse pointer-events-none" />

            {/* Circular Highlight / Glowing Ring Container around Microphone Icon */}
            <div
              className={`relative flex items-center justify-center w-12 h-12 sm:w-14 sm:h-14 rounded-full shadow-lg transition-all ${
                pathname.startsWith('/voice-agent')
                  ? 'bg-gradient-to-br from-[#0F172A] via-[#1E293B] to-[#0F172A] text-white ring-4 ring-[#FF6F00] shadow-[#FF6F00]/40'
                  : 'bg-gradient-to-br from-[#0F172A] via-[#1E293B] to-[#0F172A] text-white ring-4 ring-[#FF6F00]/70 hover:ring-[#FF6F00] shadow-black/25 hover:shadow-[#FF6F00]/30'
              } ring-offset-2 ring-offset-white`}
            >
              <Mic className="w-6 h-6 sm:w-7 sm:h-7 text-white transition-transform group-hover:scale-110" />

              {/* Active Audio Indicator Dot */}
              <span className="absolute top-1 right-1 w-2.5 h-2.5 rounded-full bg-[#00C853] border-2 border-white animate-ping" />
              <span className="absolute top-1 right-1 w-2.5 h-2.5 rounded-full bg-[#00C853] border-2 border-white" />
            </div>

            {/* Bold High-Contrast Label */}
            <span className="text-[9px] sm:text-[10.5px] font-black tracking-tight text-[#0F172A] text-center uppercase mt-1 leading-tight drop-shadow-xs whitespace-nowrap">
              GNANI VOICE AGENT
            </span>

            {/* Small Badge: POWERED BY GNANI AI */}
            <span className="inline-flex items-center px-1.5 py-0.5 text-[6.5px] sm:text-[7.5px] font-extrabold uppercase tracking-wider bg-gradient-to-r from-[#FF6F00] to-amber-500 text-white rounded-full shadow-xs mt-0.5 leading-none whitespace-nowrap">
              POWERED BY GNANI AI
            </span>
          </Link>

          {/* Tab 5: More / Others (Opens Remaining Features Drawer) */}
          <button
            onClick={() => setIsMoreOpen(!isMoreOpen)}
            className={`flex flex-col items-center justify-center py-1 px-1 rounded-lg transition-all ${
              isMoreOpen || isMoreActive
                ? 'text-[#0F172A] font-bold scale-105'
                : 'text-[#526176] hover:text-[#0F172A] font-medium'
            }`}
          >
            <div className={`p-1.5 rounded-full ${isMoreOpen || isMoreActive ? 'bg-[#0F172A] text-white shadow-xs' : ''}`}>
              <Grid className="w-4 h-4" />
            </div>
            <span className="text-[10px] tracking-tight mt-0.5">Others</span>
          </button>

        </div>
      </nav>

      {/* ============================================================== */}
      {/* "OTHERS / MORE" BOTTOM SHEET MODAL (SLIDE-UP DRAWER)           */}
      {/* Channels, Listings, Campaigns, Sales Agent, Policies, Orders   */}
      {/* ============================================================== */}
      {isMoreOpen && (
        <div className="fixed inset-0 z-50 flex flex-col justify-end">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity animate-fade-in"
            onClick={() => setIsMoreOpen(false)}
          />

          {/* Sheet Container */}
          <div className="relative bg-white rounded-t-2xl max-w-lg w-full mx-auto p-4 sm:p-5 shadow-2xl border-t border-[#D5DEE9] z-10 max-h-[85vh] overflow-y-auto animate-slide-up space-y-4">
            
            {/* Top Drag Handle */}
            <div className="w-10 h-1 bg-[#C4CFDC] rounded-full mx-auto" />

            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-[#D5DEE9]">
              <div className="flex items-center gap-3">
                <img
                  src="/vyapar_mitra_logo.png"
                  alt="Vyapar Mitra"
                  className="h-8 w-auto object-contain"
                />
                <div className="h-5 w-[1px] bg-[#D5DEE9]" />
                <div>
                  <h3 className="text-sm font-bold text-[#0F172A] tracking-tight">
                    Merchant Operations Suite
                  </h3>
                  <p className="text-[11px] text-[#526176]">
                    Channels, campaigns, policies, and ledger
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsMoreOpen(false)}
                className="p-1.5 rounded-full hover:bg-[#F8FAFC] text-[#526176] transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Features List */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {MORE_FEATURES.map((item) => {
                const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setIsMoreOpen(false)}
                    className={`flex items-start gap-3 p-3 rounded-xl border transition-all ${
                      active
                        ? 'border-[#0F172A] bg-[#E8EEF5] shadow-xs'
                        : 'border-[#D5DEE9] bg-white hover:border-[#C4CFDC] hover:bg-[#F8FAFC]'
                    }`}
                  >
                    <div className={`p-2 rounded-lg border ${item.color} shrink-0`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className={`text-xs font-bold truncate ${active ? 'text-[#0F172A]' : 'text-[#0F172A]'}`}>
                          {item.label}
                        </span>
                        <ChevronRight className="w-3.5 h-3.5 text-[#667085] shrink-0" />
                      </div>
                      <p className="text-[10px] text-[#526176] leading-snug line-clamp-2 mt-0.5">
                        {item.description}
                      </p>
                    </div>
                  </Link>
                );
              })}
            </div>

            {/* Reset Demo Quick Action */}
            <div className="pt-2 border-t border-[#D5DEE9] flex items-center justify-between">
              <span className="text-[10px] font-mono text-[#667085]">
                Vyapar Mitra AI Operations Engine
              </span>
              <button
                onClick={() => {
                  setIsMoreOpen(false);
                  setIsResetModalOpen(true);
                }}
                className="text-[11px] font-semibold text-rose-600 hover:text-rose-700 hover:underline"
              >
                Reset Demo Data
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset Demo Modal */}
      {isResetModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white border border-[#D5DEE9] rounded-[16px] max-w-md w-full p-6 space-y-4 shadow-[0_2px_6px_rgba(15,23,42,0.04)]">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="font-semibold text-sm text-[#0F172A]">Reset Demo Data</h3>
                <p className="text-xs text-[#526176] mt-1">
                  This will re-initialize Growth Doctor findings, channel allocations, and sample contacts for merchant{' '}
                  <code className="font-mono text-[#0F172A]">Vyapar Mitra</code> to their baseline benchmark state.
                </p>
              </div>
            </div>

            {resetSuccess && (
              <div className="p-3 bg-[#E8F7F1] border border-[#067647]/30 text-[#067647] text-xs rounded-[8px] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-[#067647] shrink-0" />
                <span>Demo data reset successfully. Reloading view...</span>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2 border-t border-[#D5DEE9]">
              <button
                onClick={() => setIsResetModalOpen(false)}
                disabled={isResetting}
                className="px-3 py-1.5 text-xs font-medium border border-[#D5DEE9] rounded-[8px] text-[#526176] hover:bg-[#F8FAFC]"
              >
                Cancel
              </button>
              <button
                onClick={handleResetDemo}
                disabled={isResetting}
                className="px-3.5 py-1.5 text-xs font-medium bg-[#0F172A] text-white rounded-[8px] hover:bg-[#1E293B]"
              >
                {isResetting ? 'Resetting...' : 'Confirm Reset'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
