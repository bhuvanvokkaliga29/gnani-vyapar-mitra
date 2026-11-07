'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Sparkles,
  Camera,
  Mic,
  ArrowRight,
  TrendingUp,
  Package,
  Layers,
  Wand2,
  CheckCircle2
} from 'lucide-react';
import { useMerchant } from '@/lib/MerchantContext';
import { AIProductStudioModal } from '@/components/products/AIProductStudioModal';

export default function StudioPage() {
  const { currentMerchant } = useMerchant();
  const [isModalOpen, setIsModalOpen] = useState(true);

  return (
    <div className="w-full px-2 sm:px-4 md:px-6 py-4 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#d8d8d8]">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-semibold text-[#146ef5] bg-[#eff6ff] px-2 py-0.5 rounded-[4px] border border-[#146ef5]/20">
              MULTIMODAL ONBOARDING ENGINE
            </span>
            <span className="text-xs text-[#5a5a5a]">
              Photo + Voice + Text Refinement
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-semibold text-[#080808] tracking-tight mt-1">
            AI Product Studio
          </h1>
          <p className="text-xs md:text-sm text-[#5a5a5a] mt-0.5 max-w-3xl leading-relaxed">
            Turn raw smartphone photos, voice descriptions, and rough cost notes into marketplace-ready products with studio-grade imagery and margin-guarded economics.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[#146ef5] text-white rounded-[6px] hover:bg-[#1366e2] text-xs font-semibold shadow-xs self-start md:self-auto transition-colors"
        >
          <Wand2 className="w-4 h-4 text-amber-300" />
          <span>Launch AI Creator Modal</span>
        </button>
      </div>

      {/* Feature Cards Showcase */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="studio-card p-6 space-y-3">
          <div className="w-10 h-10 rounded-full bg-[#eff6ff] text-[#146ef5] flex items-center justify-center">
            <Camera className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-sm text-[#080808]">1. Smartphone Photo Ingestion</h3>
          <p className="text-xs text-[#5a5a5a] leading-relaxed">
            Upload raw workshop or warehouse photos. The AI refines lighting, isolates foreground silhouettes, and renders high-definition studio e-commerce imagery.
          </p>
        </div>

        <div className="studio-card p-6 space-y-3">
          <div className="w-10 h-10 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center">
            <Mic className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-sm text-[#080808]">2. Voice Memo Transcription</h3>
          <p className="text-xs text-[#5a5a5a] leading-relaxed">
            Speak naturally about your prototype or wholesale batch. Real-time Web Speech recognition transcribes specs, materials, and pricing directly into catalog attributes.
          </p>
        </div>

        <div className="studio-card p-6 space-y-3">
          <div className="w-10 h-10 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <TrendingUp className="w-5 h-5" />
          </div>
          <h3 className="font-semibold text-sm text-[#080808]">3. Instant Unit Economics</h3>
          <p className="text-xs text-[#5a5a5a] leading-relaxed">
            Calculates exact integer paise margins, generates 5 marketplace-ready bullet points, and automatically routes the new SKU to the Channel Segregation Board.
          </p>
        </div>
      </div>

      {/* Quick Launch Panel */}
      <div className="p-8 rounded-[12px] bg-linear-to-r from-[#eff6ff] to-[#f8f9fa] border border-[#146ef5]/20 flex flex-col sm:flex-row items-center justify-between gap-6">
        <div className="space-y-1">
          <h3 className="text-base font-semibold text-[#080808]">
            Ready to create a new product for {currentMerchant.name}?
          </h3>
          <p className="text-xs text-[#5a5a5a]">
            Test with our sample prototype presets (Tactical Sling, Weatherproof Backpack, Tech Folio) or upload your own.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="px-5 py-2.5 bg-[#080808] hover:bg-[#222] text-white rounded-[6px] text-xs font-semibold flex items-center gap-2 whitespace-nowrap shadow-sm transition-colors"
        >
          <Sparkles className="w-4 h-4 text-amber-300" />
          <span>Open AI Creator</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* Modal */}
      <AIProductStudioModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onProductCreated={() => {
          window.location.href = '/products';
        }}
      />
    </div>
  );
}
