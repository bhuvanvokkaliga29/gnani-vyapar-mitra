'use client';

import React, { useState, useEffect } from 'react';
import {
  FileText,
  Sparkles,
  Download,
  Copy,
  Check,
  RefreshCw,
  Camera,
  Layers,
  Tag,
  Info
} from 'lucide-react';
import { useMerchant } from '@/lib/MerchantContext';
import { api, formatPaise } from '@/lib/api';

export default function ListingsPage() {
  const { currentMerchant } = useMerchant();
  const [products, setProducts] = useState<any[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<string>('');
  const [selectedChannel, setSelectedChannel] = useState<string>('AMAZON');
  const [listingPack, setListingPack] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [copiedOndc, setCopiedOndc] = useState(false);

  useEffect(() => {
    // Fetch products
    api.getProducts(currentMerchant.id)
      .then((res) => {
        const items = res.products || res || [];
        setProducts(items);
        if (items.length > 0) {
          setSelectedProductId(items[0].id);
          generatePack(items[0].id, 'AMAZON');
        }
      })
      .catch((err) => console.error(err));
  }, [currentMerchant.id]);

  const generatePack = async (prodId: string, channel: string) => {
    if (!prodId) return;
    setLoading(true);
    try {
      const pack = await api.generateListing(currentMerchant.id, prodId, channel);
      setListingPack(pack);
    } catch (err: any) {
      alert('Failed to generate listing pack: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleProductChange = (prodId: string) => {
    setSelectedProductId(prodId);
    generatePack(prodId, selectedChannel);
  };

  const handleChannelChange = (ch: string) => {
    setSelectedChannel(ch);
    generatePack(selectedProductId, ch);
  };

  const copyOndcJson = () => {
    if (!listingPack?.ondc_export_json) return;
    navigator.clipboard.writeText(JSON.stringify(listingPack.ondc_export_json, null, 2));
    setCopiedOndc(true);
    setTimeout(() => setCopiedOndc(false), 2000);
  };

  return (
    <div className="w-full px-2 sm:px-4 md:px-6 py-4 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#d8d8d8]">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-semibold text-[#146ef5] bg-[#eff6ff] px-2 py-0.5 rounded-[4px] border border-[#146ef5]/20">
              CATALOG SYNDICATION
            </span>
            <span className="text-xs text-[#5a5a5a]">
              Zero-Hallucination Marketplace & ONDC Packs
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-semibold text-[#080808] tracking-tight mt-1">
            Product Listing & ONDC Generator
          </h1>
          <p className="text-xs md:text-sm text-[#5a5a5a] mt-0.5 max-w-3xl leading-relaxed">
            Generates standardized titles, verified attribute bullets, photo checklists, and ONDC Beckn schemas directly from real merchant product data.
          </p>
        </div>

        {/* Product & Channel Selectors */}
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={selectedProductId}
            onChange={(e) => handleProductChange(e.target.value)}
            className="studio-input px-3 py-1.5 text-xs font-medium text-[#080808]"
          >
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.sku})
              </option>
            ))}
          </select>

          <select
            value={selectedChannel}
            onChange={(e) => handleChannelChange(e.target.value)}
            className="studio-input px-3 py-1.5 text-xs font-medium text-[#080808]"
          >
            <option value="AMAZON">Amazon India</option>
            <option value="FLIPKART">Flipkart</option>
            <option value="ONDC">ONDC Open Network</option>
            <option value="MEESHO">Meesho</option>
          </select>
        </div>
      </div>

      {loading && (
        <div className="p-12 text-center text-xs text-[#5a5a5a]">
          <RefreshCw className="w-5 h-5 mx-auto animate-spin text-[#146ef5] mb-2" />
          <span>Generating verified listing pack...</span>
        </div>
      )}

      {listingPack && !loading && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Main Listing Fields (Col 8) */}
          <div className="lg:col-span-8 space-y-6">
            {/* Title */}
            <div className="studio-card p-6 space-y-2">
              <span className="text-[11px] font-semibold text-[#5a5a5a] uppercase tracking-wider block">
                Channel Title
              </span>
              <p className="text-base font-semibold text-[#080808] leading-snug">
                {listingPack.title}
              </p>
            </div>

            {/* Bullets */}
            <div className="studio-card p-6 space-y-3">
              <span className="text-[11px] font-semibold text-[#5a5a5a] uppercase tracking-wider block">
                Verified Attribute Bullet Points (No Hallucinations)
              </span>
              <ul className="space-y-2 text-xs text-[#080808]">
                {listingPack.bullet_points.map((b: string, i: number) => (
                  <li key={i} className="flex items-start gap-2 leading-relaxed">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#146ef5] mt-1.5 shrink-0" />
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Description */}
            <div className="studio-card p-6 space-y-2">
              <span className="text-[11px] font-semibold text-[#5a5a5a] uppercase tracking-wider block">
                Product Description
              </span>
              <p className="text-xs text-[#5a5a5a] leading-relaxed">
                {listingPack.description}
              </p>
            </div>

            {/* Search Terms */}
            <div className="studio-card p-6 space-y-2">
              <span className="text-[11px] font-semibold text-[#5a5a5a] uppercase tracking-wider block">
                Search Terms & Keywords
              </span>
              <div className="p-3 bg-[#f0f0f0] border border-[#d8d8d8] rounded-[4px] font-mono text-xs text-[#080808]">
                {listingPack.search_terms}
              </div>
            </div>
          </div>

          {/* Right Column: Required Attributes, Photo Checklist & ONDC Export (Col 4) */}
          <div className="lg:col-span-4 space-y-6">
            {/* Required Attributes */}
            <div className="studio-card p-6 space-y-3">
              <span className="text-[11px] font-semibold text-[#5a5a5a] uppercase tracking-wider block">
                Required Attributes
              </span>
              <div className="space-y-1.5 text-xs">
                {Object.entries(listingPack.required_attributes || {}).map(([k, v]: [string, any]) => (
                  <div key={k} className="flex justify-between py-1 border-b border-[#d8d8d8]">
                    <span className="text-[#5a5a5a] uppercase text-[10px]">{k.replace(/_/g, ' ')}:</span>
                    <span className="font-semibold text-[#080808]">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Photo Checklist */}
            <div className="studio-card p-6 space-y-3">
              <div className="flex items-center gap-2">
                <Camera className="w-4 h-4 text-[#146ef5]" />
                <span className="text-[11px] font-semibold text-[#5a5a5a] uppercase tracking-wider">
                  Photo Checklist
                </span>
              </div>
              <ul className="space-y-2 text-xs text-[#5a5a5a]">
                {listingPack.photo_checklist.map((p: string, i: number) => (
                  <li key={i} className="flex items-start gap-2 leading-relaxed">
                    <span className="text-emerald-700 font-bold shrink-0">✓</span>
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* ONDC Beckn Export */}
            <div className="studio-card p-6 space-y-3 bg-[#eff6ff] border-[#146ef5]/30">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#146ef5]" />
                  <span className="font-semibold text-xs text-[#146ef5]">ONDC Beckn v1.2</span>
                </div>
                <button
                  onClick={copyOndcJson}
                  className="px-2.5 py-1 text-xs font-medium bg-[#146ef5] text-white rounded-[4px] hover:bg-[#1366e2] flex items-center gap-1"
                >
                  {copiedOndc ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedOndc ? 'Copied' : 'Copy JSON'}</span>
                </button>
              </div>

              <p className="text-[11px] text-[#5a5a5a] leading-tight">
                Export-ready JSON conforming to the Open Network for Digital Commerce (ONDC) Beckn protocol.
              </p>

              <div className="p-2.5 bg-white border border-[#d8d8d8] rounded-[4px] max-h-48 overflow-y-auto font-mono text-[10px] text-[#080808]">
                <pre>{JSON.stringify(listingPack.ondc_export_json, null, 2)}</pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
