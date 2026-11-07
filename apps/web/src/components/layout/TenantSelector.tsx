'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Building2, ChevronDown, Check } from 'lucide-react';
import { useMerchant, PRESET_MERCHANTS, MerchantInfo } from '@/lib/MerchantContext';

export function TenantSelector() {
  const { currentMerchant, setCurrentMerchant, setCustomMerchantId } = useMerchant();
  const [isOpen, setIsOpen] = useState(false);
  const [customInput, setCustomInput] = useState('');
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);

  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const optionsRef = useRef<(HTMLButtonElement | null)[]>([]);

  // Close dropdown on click outside or Escape key
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        e.preventDefault();
        setIsOpen(false);
        setTimeout(() => {
          triggerRef.current?.focus();
        }, 0);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  // Reset focus index when dropdown opens
  useEffect(() => {
    if (isOpen) {
      const selectedIndex = PRESET_MERCHANTS.findIndex((m) => m.id === currentMerchant.id);
      setFocusedIndex(selectedIndex >= 0 ? selectedIndex : 0);
    } else {
      setFocusedIndex(-1);
    }
  }, [isOpen, currentMerchant.id]);

  // Focus the active option when focusedIndex changes
  useEffect(() => {
    if (isOpen && focusedIndex >= 0 && optionsRef.current[focusedIndex]) {
      optionsRef.current[focusedIndex]?.focus();
    }
  }, [focusedIndex, isOpen]);

  const handleSelect = useCallback(
    (merchant: MerchantInfo) => {
      setCurrentMerchant(merchant);
      setIsOpen(false);
      triggerRef.current?.focus();
    },
    [setCurrentMerchant]
  );

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = customInput.trim();
    if (!trimmed) return;
    setCustomMerchantId(trimmed);
    setIsOpen(false);
    setCustomInput('');
    triggerRef.current?.focus();
  };

  const handleKeyDownMenu = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setFocusedIndex((prev) => (prev < PRESET_MERCHANTS.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setFocusedIndex((prev) => (prev > 0 ? prev - 1 : PRESET_MERCHANTS.length - 1));
    } else if (e.key === 'Home') {
      e.preventDefault();
      setFocusedIndex(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      setFocusedIndex(PRESET_MERCHANTS.length - 1);
    }
  };

  return (
    <div className="relative" ref={containerRef}>
      {/* Trigger Button */}
      <button
        ref={triggerRef}
        type="button"
        id="tenant-selector-trigger"
        onClick={() => setIsOpen(!isOpen)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls="tenant-selector-menu"
        aria-label={`Current tenant: ${currentMerchant.name} (${currentMerchant.id}). Click to switch tenant scope.`}
        className="h-8 flex items-center gap-2 text-xs font-normal text-[#061b31] hover:bg-[#f8fafd] px-3 rounded-md border border-[#e5edf5] hover:border-[#b9b9f9] focus-visible:ring-2 focus-visible:ring-[#533afd] focus-visible:outline-none transition-all max-w-[260px] sm:max-w-[320px]"
      >
        <Building2 className="w-3.5 h-3.5 text-[#533afd] shrink-0" />
        <span className="font-semibold text-[#061b31] truncate whitespace-nowrap">{currentMerchant.name}</span>
        <span className="text-[#64748d] font-mono text-[10px] shrink-0 hidden sm:inline">({currentMerchant.id})</span>
        <ChevronDown
          className={`w-3.5 h-3.5 text-[#64748d] shrink-0 transition-transform duration-150 ${
            isOpen ? 'rotate-180 text-[#533afd]' : ''
          }`}
        />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          id="tenant-selector-menu"
          role="listbox"
          aria-label="Select Tenant Scope"
          tabIndex={-1}
          onKeyDown={handleKeyDownMenu}
          className="absolute -right-2 sm:right-auto sm:left-0 top-full mt-1.5 w-[300px] sm:w-[350px] max-w-[calc(100vw-24px)] bg-white border border-[#e5edf5] rounded-lg shadow-xl p-2 z-50 animate-in fade-in zoom-in-95 duration-100 focus:outline-none"
        >
          {/* Header */}
          <div className="text-[10px] font-bold text-[#64748d] px-2.5 py-1 uppercase tracking-wider">
            Select Tenant Scope
          </div>

          {/* Tenant Options */}
          <div className="space-y-1 mt-1">
            {PRESET_MERCHANTS.map((m, idx) => {
              const isSelected = m.id === currentMerchant.id;
              return (
                <button
                  key={m.id}
                  ref={(el) => {
                    optionsRef.current[idx] = el;
                  }}
                  type="button"
                  role="option"
                  id={`tenant-option-${m.id}`}
                  aria-selected={isSelected}
                  onClick={() => handleSelect(m)}
                  className={`w-full text-left px-3 py-2 text-xs rounded-md flex items-center justify-between transition-colors outline-none ${
                    isSelected
                      ? 'bg-[#f4f5fe] border border-[#d6d9fc] text-[#533afd]'
                      : 'hover:bg-[#f8fafd] focus:bg-[#f8fafd] border border-transparent text-[#061b31]'
                  }`}
                >
                  <div className="min-w-0 pr-2">
                    {/* Merchant Name: whitespace-nowrap, semibold, single line */}
                    <div className="font-semibold text-[#061b31] whitespace-nowrap text-xs leading-snug">
                      {m.name}
                    </div>
                    {/* Tenant ID and Category subline */}
                    <div className="flex items-center gap-1.5 mt-0.5 text-[11px] leading-tight">
                      <span className="font-mono text-[#64748d] shrink-0">{m.id}</span>
                      <span className="text-[#839bc8] truncate text-[10px]">• {m.category}</span>
                    </div>
                  </div>
                  {isSelected && (
                    <Check className="w-4 h-4 text-[#533afd] shrink-0" aria-label="Selected" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Custom Tenant ID Footer / Go Control */}
          <div className="border-t border-[#e5edf5] mt-2 pt-2 px-1">
            <div className="text-[10px] font-medium text-[#64748d] mb-1.5 px-1">
              Switch to custom tenant ID
            </div>
            <form onSubmit={handleCustomSubmit} className="flex gap-1.5">
              <input
                type="text"
                placeholder="e.g. merch_custom_123"
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
                aria-label="Custom merchant ID"
                className="flex-1 min-w-0 text-xs px-2.5 py-1.5 border border-[#e5edf5] rounded-md font-mono bg-[#f8fafd] focus:bg-white focus:outline-none focus:border-[#533afd] transition-all"
              />
              <button
                type="submit"
                disabled={!customInput.trim()}
                className="text-xs font-medium bg-[#533afd] hover:bg-[#432ee0] disabled:opacity-40 text-white px-3 py-1.5 rounded-md transition-colors shrink-0"
              >
                Go
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
