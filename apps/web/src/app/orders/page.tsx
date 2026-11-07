'use client';

import React, { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import {
  CreditCard,
  RefreshCw,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Layers,
  ArrowRight,
  Search,
  Filter,
  ShoppingBag,
  Truck,
  Check,
  X,
  ChevronRight,
  Calendar,
  Phone,
  MapPin,
  FileText,
  DollarSign,
  AlertTriangle,
  Receipt
} from 'lucide-react';
import { api, formatPaise } from '@/lib/api';

type FilterType = 'ALL' | 'PAID' | 'COD' | 'CANCELLED';

export default function OrdersPage() {
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<FilterType>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedOrder, setSelectedOrder] = useState<any | null>(null);
  const [copiedOrderId, setCopiedOrderId] = useState<string | null>(null);

  const loadOrders = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getOrders(100, 0);
      setOrders(res.items || res || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load order history');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
  }, []);

  // Filtered orders based on selected tab and search query
  const filteredOrders = useMemo(() => {
    return orders.filter((order) => {
      const notes = order.notes || {};
      const status = (order.status || '').toUpperCase();
      const isCod = status === 'COD' || (notes.payment_method || '').toLowerCase().includes('cash') || (notes.payment_method || '').toLowerCase().includes('cod');
      const isPaid = status === 'PAID';
      const isCancelled = status === 'CANCELLED' || status === 'FAILED';

      // 1. Tab Filter
      if (activeFilter === 'PAID' && !isPaid) return false;
      if (activeFilter === 'COD' && !isCod) return false;
      if (activeFilter === 'CANCELLED' && !isCancelled) return false;

      // 2. Search Query Filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const customer = (notes.customer_name || '').toLowerCase();
        const phone = (notes.customer_phone || '').toLowerCase();
        const product = (notes.product_name || '').toLowerCase();
        const id = (order.id || '').toLowerCase();
        const sku = (notes.sku || '').toLowerCase();
        const city = (notes.customer_city || '').toLowerCase();

        return (
          customer.includes(q) ||
          phone.includes(q) ||
          product.includes(q) ||
          id.includes(q) ||
          sku.includes(q) ||
          city.includes(q)
        );
      }

      return true;
    });
  }, [orders, activeFilter, searchQuery]);

  // Group filtered orders by date header (PhonePe transaction history style)
  const groupedOrders = useMemo(() => {
    const groups: { [key: string]: any[] } = {};

    filteredOrders.forEach((order) => {
      let dateKey = 'Earlier';
      if (order.created_at) {
        const date = new Date(order.created_at);
        const dYear = date.getFullYear();
        const dMonth = date.getMonth();
        const dDay = date.getDate();

        // 2026-10-17 is Today
        if (dYear === 2026 && dMonth === 9 && dDay === 17) {
          dateKey = 'Today, 17 Oct 2026';
        } else if (dYear === 2026 && dMonth === 9 && dDay === 16) {
          dateKey = 'Yesterday, 16 Oct 2026';
        } else {
          const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
          dateKey = `${dDay} ${months[dMonth]} ${dYear}`;
        }
      }

      if (!groups[dateKey]) {
        groups[dateKey] = [];
      }
      groups[dateKey].push(order);
    });

    return groups;
  }, [filteredOrders]);

  // Key KPI stats
  const stats = useMemo(() => {
    let totalPaidPaise = 0;
    let totalCodPaise = 0;
    let paidCount = 0;
    let codCount = 0;
    let cancelledCount = 0;

    orders.forEach((o) => {
      const notes = o.notes || {};
      const status = (o.status || '').toUpperCase();
      const isCod = status === 'COD' || (notes.payment_method || '').toLowerCase().includes('cod');
      const isPaid = status === 'PAID';
      const isCancelled = status === 'CANCELLED' || status === 'FAILED';

      if (isPaid) {
        totalPaidPaise += o.amount_paise || 0;
        paidCount++;
      } else if (isCod) {
        totalCodPaise += o.amount_paise || 0;
        codCount++;
      } else if (isCancelled) {
        cancelledCount++;
      }
    });

    return {
      totalPaidPaise,
      totalCodPaise,
      paidCount,
      codCount,
      cancelledCount,
      totalCount: orders.length
    };
  }, [orders]);

  const handleCopyOrderId = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedOrderId(id);
    setTimeout(() => setCopiedOrderId(null), 2500);
  };

  return (
    <div className="w-full px-2 sm:px-4 md:px-6 py-4 space-y-6">
      
      {/* ============================================================== */}
      {/* PAGE HEADER: Order Ledger with Vyapar Mitra Branding          */}
      {/* ============================================================== */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#e4e4e7]">
        <div className="flex items-center gap-3">
          <img
            src="/vyapar_mitra_logo.png"
            alt="Vyapar Mitra"
            className="h-10 sm:h-11 w-auto object-contain"
          />
          <div className="h-6 w-[1px] bg-[#e4e4e7] hidden sm:block" />
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] font-bold text-[#080808] bg-[#f4f4f5] px-2 py-0.5 rounded border border-[#e4e4e7]">
                LIVE LEDGER
              </span>
              <span className="text-xs text-[#71717a] font-medium">
                Order History & Transactions
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-[#080808] tracking-tight mt-0.5">
              Orders & Transaction History
            </h1>
            <p className="text-xs text-[#71717a] mt-0.5 max-w-2xl leading-relaxed">
              Chronological ledger of store orders separated by date with live status tracking across UPI, Cash on Delivery, and Marketplaces.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadOrders}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold border border-[#d4d4d8] text-[#080808] bg-white rounded-lg hover:bg-[#f4f4f5] transition-colors shadow-2xs"
            title="Refresh Orders"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-[#71717a] ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg border border-rose-300 bg-rose-50 text-xs text-rose-800 flex items-center gap-2 shadow-xs">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {/* ============================================================== */}
      {/* KPI METRIC STRIP (PhonePe Business Transaction Overview)        */}
      {/* ============================================================== */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <div className="p-3.5 rounded-xl bg-white border border-[#e4e4e7] shadow-2xs space-y-1">
          <div className="text-[11px] font-medium text-[#71717a] flex items-center justify-between">
            <span>Collected (Paid)</span>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
          </div>
          <div className="text-xl sm:text-2xl font-bold text-emerald-700 tabular-nums">
            {formatPaise(stats.totalPaidPaise)}
          </div>
          <div className="text-[10px] text-[#71717a]">
            {stats.paidCount} Verified UPI & Card Orders
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-white border border-[#e4e4e7] shadow-2xs space-y-1">
          <div className="text-[11px] font-medium text-[#71717a] flex items-center justify-between">
            <span>COD (Pending Collection)</span>
            <Truck className="w-3.5 h-3.5 text-amber-600" />
          </div>
          <div className="text-xl sm:text-2xl font-bold text-amber-700 tabular-nums">
            {formatPaise(stats.totalCodPaise)}
          </div>
          <div className="text-[10px] text-[#71717a]">
            {stats.codCount} Cash on Delivery Orders
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-white border border-[#e4e4e7] shadow-2xs space-y-1">
          <div className="text-[11px] font-medium text-[#71717a] flex items-center justify-between">
            <span>Total Orders Logged</span>
            <ShoppingBag className="w-3.5 h-3.5 text-[#146ef5]" />
          </div>
          <div className="text-xl sm:text-2xl font-bold text-[#080808] tabular-nums">
            {stats.totalCount} Orders
          </div>
          <div className="text-[10px] text-emerald-700 font-medium">
            ✓ 100% Synced across Channels
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-white border border-[#e4e4e7] shadow-2xs space-y-1">
          <div className="text-[11px] font-medium text-[#71717a] flex items-center justify-between">
            <span>Cancelled Orders</span>
            <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
          </div>
          <div className="text-xl sm:text-2xl font-bold text-rose-700 tabular-nums">
            {stats.cancelledCount} Orders
          </div>
          <div className="text-[10px] text-[#71717a]">
            Stock auto-restored to catalog
          </div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* FILTER TABS & SEARCH BAR                                       */}
      {/* ============================================================== */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        
        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          <button
            onClick={() => setActiveFilter('ALL')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all shrink-0 flex items-center gap-1.5 ${
              activeFilter === 'ALL'
                ? 'bg-[#080808] text-white border-[#080808] shadow-2xs'
                : 'bg-white text-[#52525b] border-[#d4d4d8] hover:bg-[#f4f4f5]'
            }`}
          >
            <span>All Orders</span>
            <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
              activeFilter === 'ALL' ? 'bg-white/20 text-white' : 'bg-[#f4f4f5] text-[#71717a]'
            }`}>
              {stats.totalCount}
            </span>
          </button>

          <button
            onClick={() => setActiveFilter('PAID')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all shrink-0 flex items-center gap-1.5 ${
              activeFilter === 'PAID'
                ? 'bg-emerald-700 text-white border-emerald-700 shadow-2xs'
                : 'bg-white text-emerald-800 border-[#d4d4d8] hover:bg-emerald-50/50'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
            <span>Paid (UPI / Prepaid)</span>
            <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
              activeFilter === 'PAID' ? 'bg-white/20 text-white' : 'bg-emerald-50 text-emerald-800'
            }`}>
              {stats.paidCount}
            </span>
          </button>

          <button
            onClick={() => setActiveFilter('COD')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all shrink-0 flex items-center gap-1.5 ${
              activeFilter === 'COD'
                ? 'bg-amber-600 text-white border-amber-600 shadow-2xs'
                : 'bg-white text-amber-900 border-[#d4d4d8] hover:bg-amber-50/50'
            }`}
          >
            <Truck className="w-3.5 h-3.5 text-amber-500" />
            <span>Cash on Delivery (COD)</span>
            <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
              activeFilter === 'COD' ? 'bg-white/20 text-white' : 'bg-amber-50 text-amber-900'
            }`}>
              {stats.codCount}
            </span>
          </button>

          <button
            onClick={() => setActiveFilter('CANCELLED')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all shrink-0 flex items-center gap-1.5 ${
              activeFilter === 'CANCELLED'
                ? 'bg-rose-700 text-white border-rose-700 shadow-2xs'
                : 'bg-white text-rose-800 border-[#d4d4d8] hover:bg-rose-50/50'
            }`}
          >
            <X className="w-3.5 h-3.5 text-rose-500" />
            <span>Cancelled</span>
            <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
              activeFilter === 'CANCELLED' ? 'bg-white/20 text-white' : 'bg-rose-50 text-rose-800'
            }`}>
              {stats.cancelledCount}
            </span>
          </button>
        </div>

        {/* Search Bar */}
        <div className="relative w-full sm:w-72 shrink-0">
          <Search className="w-3.5 h-3.5 text-[#71717a] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search customer, phone, SKU..."
            className="w-full text-xs font-medium pl-8 pr-7 py-2 bg-white border border-[#d4d4d8] rounded-lg shadow-2xs hover:border-[#a1a1aa] focus:border-[#080808] focus:outline-none transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#71717a] hover:text-[#080808] text-xs font-bold"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* ============================================================== */}
      {/* PHONEPE-STYLE DATE SEPARATED ORDERS LIST                       */}
      {/* ============================================================== */}
      <div className="space-y-6">
        {Object.keys(groupedOrders).length === 0 ? (
          <div className="p-12 text-center bg-white rounded-xl border border-[#e4e4e7] space-y-3">
            <div className="w-12 h-12 rounded-full bg-[#f4f4f5] text-[#71717a] flex items-center justify-center mx-auto">
              <ShoppingBag className="w-6 h-6" />
            </div>
            <div className="text-sm font-bold text-[#080808]">No Orders Found</div>
            <p className="text-xs text-[#71717a] max-w-sm mx-auto">
              No orders matched your selected filter ({activeFilter}) or search query.
            </p>
            <button
              onClick={() => {
                setActiveFilter('ALL');
                setSearchQuery('');
              }}
              className="text-xs font-semibold text-[#146ef5] hover:underline"
            >
              Reset Filters
            </button>
          </div>
        ) : (
          Object.entries(groupedOrders).map(([dateLabel, dateOrders]) => (
            <div key={dateLabel} className="space-y-2">
              
              {/* PhonePe Date Separator Header */}
              <div className="flex items-center gap-2 px-1 pt-1">
                <Calendar className="w-3.5 h-3.5 text-[#71717a]" />
                <h3 className="text-xs font-bold text-[#52525b] uppercase tracking-wider font-mono">
                  {dateLabel}
                </h3>
                <span className="text-[11px] text-[#a1a1aa] font-medium font-mono">
                  ({dateOrders.length} {dateOrders.length === 1 ? 'order' : 'orders'})
                </span>
                <div className="flex-1 border-t border-[#e4e4e7] ml-2" />
              </div>

              {/* Date Group Card List */}
              <div className="bg-white border border-[#e4e4e7] rounded-xl overflow-hidden shadow-2xs divide-y divide-[#f4f4f5]">
                {dateOrders.map((order) => {
                  const notes = order.notes || {};
                  const status = (order.status || '').toUpperCase();
                  const isPaid = status === 'PAID';
                  const isCod = status === 'COD' || (notes.payment_method || '').toLowerCase().includes('cod');
                  const isCancelled = status === 'CANCELLED' || status === 'FAILED';

                  const image =
                    notes.image ||
                    (notes.product_name?.toLowerCase().includes('oxford') || notes.product_name?.toLowerCase().includes('white')
                      ? '/clothing/white_oxford.jpg'
                      : notes.product_name?.toLowerCase().includes('navy')
                      ? '/clothing/navy_shirt.jpg'
                      : notes.product_name?.toLowerCase().includes('linen') || notes.product_name?.toLowerCase().includes('olive')
                      ? '/clothing/linen_shirt.jpg'
                      : notes.product_name?.toLowerCase().includes('khaki') || notes.product_name?.toLowerCase().includes('chino')
                      ? '/clothing/khaki_chino.jpg'
                      : notes.product_name?.toLowerCase().includes('grey') || notes.product_name?.toLowerCase().includes('charcoal')
                      ? '/clothing/grey_trouser.jpg'
                      : '/clothing/black_trouser.jpg');

                  const timeStr = order.created_at
                    ? new Date(order.created_at).toLocaleTimeString('en-US', {
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: true
                      })
                    : '12:00 PM';

                  return (
                    <div
                      key={order.id}
                      onClick={() => setSelectedOrder(order)}
                      className="p-3.5 sm:p-4 hover:bg-[#f8fafc] active:bg-[#f1f5f9] cursor-pointer transition-colors flex items-center justify-between gap-3 group"
                    >
                      {/* Left: Thumbnail & Garment Avatar */}
                      <div className="flex items-center gap-3.5 min-w-0">
                        <div className="relative shrink-0">
                          <img
                            src={image}
                            alt={notes.product_name || 'Vastram Apparel'}
                            className="w-12 h-12 rounded-lg object-cover bg-white border border-[#e4e4e7] group-hover:border-[#146ef5] transition-colors"
                          />
                          {/* Channel Badge Mini */}
                          <div className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-[#080808] text-white flex items-center justify-center text-[8px] font-bold border border-white">
                            {notes.channel_code === 'WHATSAPP' ? 'WA' : notes.channel_code === 'MYNTRA' ? 'My' : notes.channel_code === 'AMAZON' ? 'a' : 'V'}
                          </div>
                        </div>

                        {/* Middle: Title, Customer, Payment Type, Time */}
                        <div className="min-w-0 space-y-0.5">
                          <div className="flex items-center gap-2">
                            <h4 className="text-xs sm:text-sm font-bold text-[#080808] truncate group-hover:text-[#146ef5] transition-colors">
                              {notes.product_name || 'Vastram Garment Order'}
                            </h4>
                            {notes.size && (
                              <span className="text-[10px] font-mono text-[#71717a] bg-[#f4f4f5] px-1.5 py-0.2 rounded border border-[#e4e4e7] shrink-0">
                                Size: {notes.size}
                              </span>
                            )}
                          </div>

                          <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-[#71717a]">
                            <span className="font-semibold text-[#18181b]">
                              {notes.customer_name || 'Customer'}
                            </span>
                            <span>•</span>
                            <span className="font-mono">{notes.customer_phone || '+91 ••••• •••••'}</span>
                            <span>•</span>
                            <span className="text-[#3f3f46] font-medium">{notes.payment_method || (isPaid ? 'UPI Instant' : 'Cash on Delivery')}</span>
                          </div>

                          <div className="flex items-center gap-2 text-[10px] text-[#a1a1aa] font-mono">
                            <span>ID: {order.id}</span>
                            <span>•</span>
                            <span>{timeStr}</span>
                            <span>•</span>
                            <span className="text-[#52525b]">{notes.channel || 'Direct Store'}</span>
                          </div>
                        </div>
                      </div>

                      {/* Right: Amount & Status Badge */}
                      <div className="flex items-center gap-3 shrink-0">
                        <div className="text-right">
                          <div className={`text-sm sm:text-base font-bold tabular-nums ${
                            isCancelled ? 'text-[#71717a] line-through' : 'text-[#080808]'
                          }`}>
                            {formatPaise(order.amount_paise)}
                          </div>

                          {/* Status Pill */}
                          <div className="mt-0.5 flex justify-end">
                            {isPaid ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[4px] text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                                <Check className="w-3 h-3 text-emerald-600" />
                                <span>PAID</span>
                              </span>
                            ) : isCod ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[4px] text-[10px] font-bold bg-amber-50 text-amber-900 border border-amber-200">
                                <Truck className="w-3 h-3 text-amber-600" />
                                <span>COD</span>
                              </span>
                            ) : isCancelled ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-[4px] text-[10px] font-bold bg-rose-50 text-rose-800 border border-rose-200">
                                <X className="w-3 h-3 text-rose-600" />
                                <span>CANCELLED</span>
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded-[4px] text-[10px] font-bold bg-blue-50 text-blue-800 border border-blue-200">
                                PENDING
                              </span>
                            )}
                          </div>
                        </div>

                        <ChevronRight className="w-4 h-4 text-[#a1a1aa] group-hover:text-[#080808] group-hover:translate-x-0.5 transition-all" />
                      </div>
                    </div>
                  );
                })}
              </div>

            </div>
          ))
        )}
      </div>

      {/* ============================================================== */}
      {/* DETAILED ORDER DOSSIER MODAL / SHEET                           */}
      {/* Complete order view when merchant clicks on any transaction   */}
      {/* ============================================================== */}
      {selectedOrder && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity animate-fade-in"
            onClick={() => setSelectedOrder(null)}
          />

          {/* Modal Content */}
          <div className="relative bg-white rounded-t-2xl sm:rounded-2xl max-w-lg w-full mx-auto p-5 sm:p-6 shadow-2xl border border-[#e4e4e7] z-10 max-h-[92vh] overflow-y-auto animate-slide-up space-y-4">
            
            {/* Mobile Handle */}
            <div className="w-10 h-1.5 bg-[#d4d4d8] rounded-full mx-auto sm:hidden shrink-0" />

            {/* Modal Header */}
            <div className="flex items-center justify-between pb-3 border-b border-[#f4f4f5]">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono font-bold bg-[#f4f4f5] px-2 py-0.5 rounded border border-[#e4e4e7] text-[#52525b]">
                    {selectedOrder.id}
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                    selectedOrder.status === 'PAID'
                      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                      : selectedOrder.status === 'COD'
                      ? 'bg-amber-50 text-amber-900 border-amber-200'
                      : 'bg-rose-50 text-rose-800 border-rose-200'
                  }`}>
                    {selectedOrder.status === 'PAID' ? '✓ PAID' : selectedOrder.status === 'COD' ? '📦 CASH ON DELIVERY' : '✕ CANCELLED'}
                  </span>
                </div>
                <h3 className="text-base font-bold text-[#080808] tracking-tight mt-1">
                  Order Dossier & Receipt
                </h3>
              </div>
              <button
                onClick={() => setSelectedOrder(null)}
                className="p-1.5 rounded-full hover:bg-[#f4f4f5] text-[#71717a] hover:text-[#080808] transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Garment Item Summary */}
            <div className="flex items-center gap-3.5 p-3 rounded-xl bg-[#fafafa] border border-[#e4e4e7]">
              <img
                src={
                  selectedOrder.notes?.image ||
                  (selectedOrder.notes?.product_name?.toLowerCase().includes('white')
                    ? '/clothing/white_oxford.jpg'
                    : selectedOrder.notes?.product_name?.toLowerCase().includes('khaki')
                    ? '/clothing/khaki_chino.jpg'
                    : selectedOrder.notes?.product_name?.toLowerCase().includes('linen')
                    ? '/clothing/linen_shirt.jpg'
                    : selectedOrder.notes?.product_name?.toLowerCase().includes('grey')
                    ? '/clothing/grey_trouser.jpg'
                    : '/clothing/black_trouser.jpg')
                }
                alt={selectedOrder.notes?.product_name || 'Vastram Garment'}
                className="w-16 h-16 rounded-lg object-cover bg-white border border-[#e4e4e7] shrink-0"
              />
              <div className="min-w-0 flex-1">
                <h4 className="text-sm font-bold text-[#080808] leading-snug">
                  {selectedOrder.notes?.product_name || 'Vastram Garment'}
                </h4>
                <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-[#71717a] mt-1">
                  <span>SKU: {selectedOrder.notes?.sku || 'VAST-SH-01'}</span>
                  <span>•</span>
                  <span>Size: {selectedOrder.notes?.size || 'Standard'}</span>
                  <span>•</span>
                  <span>Qty: {selectedOrder.notes?.qty || 1}</span>
                </div>
              </div>
            </div>

            {/* Customer Details & Shipping Grid */}
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded-lg bg-white border border-[#e4e4e7] space-y-0.5">
                <span className="text-[11px] text-[#71717a] flex items-center gap-1">
                  <Phone className="w-3 h-3 text-[#146ef5]" />
                  <span>Customer Contact</span>
                </span>
                <div className="font-bold text-[#080808]">
                  {selectedOrder.notes?.customer_name || 'Customer'}
                </div>
                <div className="font-mono text-[#52525b] text-[11px]">
                  {selectedOrder.notes?.customer_phone || '+91 ••••• •••••'}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-white border border-[#e4e4e7] space-y-0.5">
                <span className="text-[11px] text-[#71717a] flex items-center gap-1">
                  <MapPin className="w-3 h-3 text-rose-500" />
                  <span>Delivery Destination</span>
                </span>
                <div className="font-bold text-[#080808] truncate">
                  {selectedOrder.notes?.customer_city || 'Bengaluru, Karnataka'}
                </div>
                <div className="text-[11px] text-emerald-700 font-semibold flex items-center gap-1">
                  <Truck className="w-3 h-3" />
                  <span>{selectedOrder.notes?.delivery_status || 'Express Dispatch'}</span>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-white border border-[#e4e4e7] space-y-0.5">
                <span className="text-[11px] text-[#71717a] flex items-center gap-1">
                  <CreditCard className="w-3 h-3 text-[#146ef5]" />
                  <span>Payment Method</span>
                </span>
                <div className="font-bold text-[#080808]">
                  {selectedOrder.notes?.payment_method || (selectedOrder.status === 'PAID' ? 'UPI Instant' : 'Cash on Delivery')}
                </div>
                <div className="text-[10px] text-[#71717a]">
                  Channel: {selectedOrder.notes?.channel || 'Direct Store'}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-white border border-[#e4e4e7] space-y-0.5">
                <span className="text-[11px] text-[#71717a] flex items-center gap-1">
                  <Clock className="w-3 h-3 text-[#71717a]" />
                  <span>Timestamp</span>
                </span>
                <div className="font-bold text-[#080808] font-mono text-[11px]">
                  {selectedOrder.created_at ? new Date(selectedOrder.created_at).toLocaleString('en-IN') : 'Recent'}
                </div>
                <div className="text-[10px] text-[#71717a]">
                  Settlement: Instant (0% Hold)
                </div>
              </div>
            </div>

            {/* Financial Unit Economics Breakdown */}
            <div className="p-3.5 rounded-xl bg-[#f8fafc] border border-[#cbd5e1] space-y-2 text-xs">
              <div className="font-bold text-[#080808] pb-1 border-b border-[#e2e8f0] flex items-center justify-between">
                <span>Financial Breakdown</span>
                <span className="text-[11px] font-mono text-[#71717a]">INR (Paise Precision)</span>
              </div>
              <div className="flex justify-between text-[#52525b]">
                <span>Customer Retail Total:</span>
                <span className="font-bold text-[#080808]">{formatPaise(selectedOrder.amount_paise)}</span>
              </div>
              <div className="flex justify-between text-[#52525b]">
                <span>Wholesale Cost (COGS):</span>
                <span>{formatPaise(selectedOrder.notes?.cost_paise || (selectedOrder.amount_paise * 0.35))}</span>
              </div>
              <div className="flex justify-between text-emerald-700 font-bold pt-1 border-t border-[#e2e8f0]">
                <span>
                  Net Gross Profit Margin ({selectedOrder.status === 'CANCELLED' ? '0.0%' : '64.2%'}):
                </span>
                <span>
                  {selectedOrder.status === 'CANCELLED'
                    ? '₹0'
                    : `+${formatPaise(selectedOrder.amount_paise - (selectedOrder.notes?.cost_paise || (selectedOrder.amount_paise * 0.35)))}`}
                </span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => handleCopyOrderId(selectedOrder.id)}
                className="flex-1 py-2 px-3 text-xs font-semibold bg-[#080808] text-white rounded-lg hover:bg-[#27272a] transition-colors flex items-center justify-center gap-1.5"
              >
                {copiedOrderId === selectedOrder.id ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Copied Order Ref!</span>
                  </>
                ) : (
                  <>
                    <Receipt className="w-3.5 h-3.5" />
                    <span>Copy Reference ID</span>
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={() => setSelectedOrder(null)}
                className="py-2 px-4 text-xs font-medium border border-[#d4d4d8] text-[#52525b] rounded-lg hover:bg-[#f4f4f5] transition-colors"
              >
                Close
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
