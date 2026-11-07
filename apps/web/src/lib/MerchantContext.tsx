'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';

export interface MerchantInfo {
  id: string;
  name: string;
  category: string;
  minimum_margin_percent?: number;
}

export const PRESET_MERCHANTS: MerchantInfo[] = [
  { id: 'merch_atlas_travel', name: 'Vastram', category: 'Premium Apparel & Lifestyle' },
  { id: 'merch_alpha', name: 'Alpha Outfitters', category: 'Outdoor Gear' },
  { id: 'merch_95_alpha', name: 'Alpha Electronics', category: 'Electronics & Audio' },
];

interface MerchantContextType {
  currentMerchant: MerchantInfo;
  setCurrentMerchant: (merchant: MerchantInfo) => void;
  setCustomMerchantId: (id: string) => void;
}

const MerchantContext = createContext<MerchantContextType | undefined>(undefined);

export function MerchantProvider({ children }: { children: React.ReactNode }) {
  const [currentMerchant, setCurrentMerchant] = useState<MerchantInfo>(PRESET_MERCHANTS[0]);

  useEffect(() => {
    const saved = localStorage.getItem('active_merchant_id');
    if (saved) {
      const match = PRESET_MERCHANTS.find(m => m.id === saved);
      if (match) {
        setCurrentMerchant(match);
      } else {
        setCurrentMerchant({ id: saved, name: `Merchant (${saved})`, category: 'Custom Tenant' });
      }
    }
  }, []);

  const handleSetMerchant = (merchant: MerchantInfo) => {
    setCurrentMerchant(merchant);
    localStorage.setItem('active_merchant_id', merchant.id);
  };

  const setCustomMerchantId = (id: string) => {
    const match = PRESET_MERCHANTS.find(m => m.id === id);
    if (match) {
      handleSetMerchant(match);
    } else {
      const custom: MerchantInfo = { id, name: `Tenant ${id}`, category: 'Custom Scope' };
      handleSetMerchant(custom);
    }
  };

  return (
    <MerchantContext.Provider value={{ currentMerchant, setCurrentMerchant: handleSetMerchant, setCustomMerchantId }}>
      {children}
    </MerchantContext.Provider>
  );
}

export function useMerchant() {
  const ctx = useContext(MerchantContext);
  if (!ctx) throw new Error('useMerchant must be used within a MerchantProvider');
  return ctx;
}
