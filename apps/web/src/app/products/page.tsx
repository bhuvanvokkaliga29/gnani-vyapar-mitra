'use client';

import React, { useState, useEffect, useMemo } from 'react';
import {
  Package,
  RefreshCw,
  AlertCircle,
  Tag,
  Lock,
  ArrowRight,
  Wand2,
  Sparkles,
  CheckCircle2,
  Search,
  SlidersHorizontal,
  Clock,
  Shirt,
  Scissors
} from 'lucide-react';
import { useMerchant } from '@/lib/MerchantContext';
import { api, formatPaise } from '@/lib/api';
import { AIProductStudioModal } from '@/components/products/AIProductStudioModal';
import { ProductDetailModal } from '@/components/products/ProductDetailModal';

// Complete Vastram Apparel Baseline with T-Shirts, Full Sleeve Shirts, Polos, Chinos & Trousers
const BASELINE_APPAREL = [
  {
    id: 'prod_vastram_tshirt_black',
    sku: 'VAST-TS-01',
    name: 'Vastram Luxury Supima Cotton Crewneck T-Shirt',
    description: 'Extra-long staple 220 GSM American Supima cotton t-shirt. Pre-shrunk with anti-pilling bio-wash finish and ribbed crew collar.',
    category: 'T-SHIRTS',
    sub_category: 'T-SHIRT',
    sleeve: 'Half Sleeve',
    price_paise: 129900,
    cost_paise: 42000,
    currency: 'INR',
    inventory_quantity: 110,
    reserved_quantity: 4,
    is_active: 1,
    is_recent: true,
    added_tag: 'Just Added (2h ago)',
    attributes: {
      fabric: '220 GSM Supima Cotton',
      fit: 'Regular Comfort Fit',
      color: 'Pitch Black',
      sleeve: 'Half Sleeve',
      type: 'T-Shirt',
      refined_photo_url: '/clothing/tshirt_black.jpg'
    }
  },
  {
    id: 'prod_vastram_polo_navy',
    sku: 'VAST-PO-01',
    name: 'Vastram Signature Honeycomb Pique Polo T-Shirt',
    description: 'Double-mercerized Egyptian cotton pique polo with tipped knit collar and mother-of-pearl placket. Breathable textured knit.',
    category: 'T-SHIRTS',
    sub_category: 'POLO',
    sleeve: 'Half Sleeve',
    price_paise: 159900,
    cost_paise: 54000,
    currency: 'INR',
    inventory_quantity: 65,
    reserved_quantity: 2,
    is_active: 1,
    is_recent: true,
    added_tag: 'New Collection',
    attributes: {
      fabric: 'Honeycomb Pique Knit',
      fit: 'Tailored Sport Fit',
      color: 'Navy Blue',
      sleeve: 'Half Sleeve',
      type: 'Polo T-Shirt',
      refined_photo_url: '/clothing/polo_navy.jpg'
    }
  },
  {
    id: 'prod_vastram_shirt_white',
    sku: 'VAST-SH-01',
    name: 'Vastram Classic White Oxford Cotton Shirt',
    description: '100% Egyptian Giza cotton formal shirt with spread collar and mother-of-pearl buttons. Tailored slim fit with full sleeves.',
    category: 'SHIRTS',
    sub_category: 'FULL_SLEEVE',
    sleeve: 'Full Sleeve',
    price_paise: 189900,
    cost_paise: 65000,
    currency: 'INR',
    inventory_quantity: 85,
    reserved_quantity: 0,
    is_active: 1,
    is_recent: true,
    added_tag: 'Restocked',
    attributes: {
      fabric: '100% Giza Oxford Cotton',
      fit: 'Slim Fit',
      color: 'White',
      sleeve: 'Full Sleeve',
      type: 'Formal Shirt',
      refined_photo_url: '/clothing/white_oxford.jpg'
    }
  },
  {
    id: 'prod_vastram_shirt_navy',
    sku: 'VAST-SH-02',
    name: 'Vastram Signature Royal Navy Casual Shirt',
    description: 'Pre-washed rich indigo dyed pure cotton casual shirt. Soft-brushed finish for all-day comfort with tailored full sleeves.',
    category: 'SHIRTS',
    sub_category: 'FULL_SLEEVE',
    sleeve: 'Full Sleeve',
    price_paise: 199900,
    cost_paise: 72000,
    currency: 'INR',
    inventory_quantity: 60,
    reserved_quantity: 0,
    is_active: 1,
    is_recent: false,
    attributes: {
      fabric: 'Brushed Cotton',
      fit: 'Regular Fit',
      color: 'Navy Blue',
      sleeve: 'Full Sleeve',
      type: 'Casual Shirt',
      refined_photo_url: '/clothing/navy_shirt.jpg'
    }
  },
  {
    id: 'prod_vastram_shirt_linen',
    sku: 'VAST-SH-03',
    name: 'Vastram Pure Olive Linen Casual Shirt',
    description: 'Breathable French flax pure linen casual shirt in earthy sage green. Relaxed weekend spread collar with rollable full sleeves.',
    category: 'SHIRTS',
    sub_category: 'CASUAL_LINEN',
    sleeve: 'Full Sleeve',
    price_paise: 249900,
    cost_paise: 92000,
    currency: 'INR',
    inventory_quantity: 45,
    reserved_quantity: 0,
    is_active: 1,
    is_recent: false,
    attributes: {
      fabric: 'French Linen',
      fit: 'Relaxed Fit',
      color: 'Sage Olive',
      sleeve: 'Full Sleeve',
      type: 'Linen Shirt',
      refined_photo_url: '/clothing/linen_shirt.jpg'
    }
  },
  {
    id: 'prod_vastram_trouser_khaki',
    sku: 'VAST-TR-01',
    name: 'Vastram Tailored Khaki Chino Trousers',
    description: '98% premium stretch twill cotton chinos. Clean flat front with tailored taper and reinforced pocketing.',
    category: 'TROUSERS',
    sub_category: 'CHINOS_PANTS',
    sleeve: 'N/A',
    price_paise: 229900,
    cost_paise: 85000,
    currency: 'INR',
    inventory_quantity: 70,
    reserved_quantity: 0,
    is_active: 1,
    is_recent: false,
    attributes: {
      fabric: 'Stretch Twill Cotton',
      fit: 'Tailored Fit',
      color: 'Beige Khaki',
      type: 'Chinos',
      refined_photo_url: '/clothing/khaki_chino.jpg'
    }
  },
  {
    id: 'prod_vastram_trouser_grey',
    sku: 'VAST-TR-02',
    name: 'Vastram Italian Wool Charcoal Grey Trousers',
    description: 'Fine tropical wool blend formal trousers with sharp creases and internal shirt-gripper waistband.',
    category: 'TROUSERS',
    sub_category: 'FORMAL_TROUSERS',
    sleeve: 'N/A',
    price_paise: 279900,
    cost_paise: 110000,
    currency: 'INR',
    inventory_quantity: 40,
    reserved_quantity: 0,
    is_active: 1,
    is_recent: false,
    attributes: {
      fabric: 'Tropical Wool Blend',
      fit: 'Slim Formal',
      color: 'Charcoal Grey',
      type: 'Formal Trousers',
      refined_photo_url: '/clothing/grey_trouser.jpg'
    }
  },
  {
    id: 'prod_vastram_trouser_black',
    sku: 'VAST-TR-03',
    name: 'Vastram Classic Jet Black Formal Trousers',
    description: 'Deep fade-resistant black formal trousers. Non-crease poly-viscose blend with flexible comfort waistband.',
    category: 'TROUSERS',
    sub_category: 'FORMAL_TROUSERS',
    sleeve: 'N/A',
    price_paise: 219900,
    cost_paise: 79000,
    currency: 'INR',
    inventory_quantity: 6,
    reserved_quantity: 0,
    is_active: 1,
    is_recent: false,
    attributes: {
      fabric: 'Poly-Viscose',
      fit: 'Regular Fit',
      color: 'Jet Black',
      type: 'Formal Trousers',
      refined_photo_url: '/clothing/black_trouser.jpg'
    }
  }
];

export default function ProductsPage() {
  const { currentMerchant } = useMerchant();
  const [products, setProducts] = useState<any[]>(BASELINE_APPAREL);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Filtering state: Main Category + Sub-style filter + Search keyword
  const [selectedMainCat, setSelectedMainCat] = useState<string>('ALL');
  const [selectedSubFilter, setSelectedSubFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  
  const [isStudioOpen, setIsStudioOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<any | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const loadProducts = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getProducts(currentMerchant.id);
      const apiItems = Array.isArray(res) ? res : res.products || [];
      
      if (apiItems.length > 0) {
        // Deep merge API products with our rich baseline to preserve T-shirts, sleeves, and recent tags
        const merged = apiItems.map((apiP: any) => {
          const match = BASELINE_APPAREL.find((b) => b.sku === apiP.sku || b.id === apiP.id);
          if (match) {
            return {
              ...match,
              ...apiP,
              sleeve: apiP.sleeve || match.sleeve,
              is_recent: apiP.is_recent ? true : (match.is_recent ?? false),
              added_tag: apiP.added_tag || match.added_tag,
              attributes: {
                ...match.attributes,
                ...(apiP.attributes || {})
              }
            };
          }
          return apiP;
        });

        for (const base of BASELINE_APPAREL) {
          const exists = merged.some((p: any) => p.sku === base.sku || p.id === base.id);
          if (!exists) {
            merged.push(base);
          }
        }
        setProducts(merged);
      } else {
        setProducts(BASELINE_APPAREL);
      }
    } catch (err: any) {
      // Graceful fallback to baseline items
      setProducts(BASELINE_APPAREL);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProducts();
  }, [currentMerchant.id]);

  // Extract 3-4 Recently Added Products
  const recentlyAdded = useMemo(() => {
    return products.filter((p) => p.is_recent || p.added_tag).slice(0, 3);
  }, [products]);

  // Filter products based on Main Category, Sub-Filter, and Search Query
  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      const name = (p.name || '').toLowerCase();
      const sku = (p.sku || '').toLowerCase();
      const cat = (p.category || '').toUpperCase();
      const desc = (p.description || '').toLowerCase();
      const fabric = (p.attributes?.fabric || '').toLowerCase();
      const sleeve = (p.sleeve || p.attributes?.sleeve || '').toLowerCase();

      // 1. Search Query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesQuery = name.includes(q) || sku.includes(q) || fabric.includes(q) || desc.includes(q);
        if (!matchesQuery) return false;
      }

      // 2. Main Category Filter
      if (selectedMainCat === 'SHIRTS') {
        const isShirt = cat === 'SHIRTS' || (name.includes('shirt') && !name.includes('t-shirt') && !name.includes('polo'));
        if (!isShirt) return false;
      } else if (selectedMainCat === 'T_SHIRTS') {
        const isTShirt = cat === 'T-SHIRTS' || name.includes('t-shirt') || name.includes('polo') || name.includes('crewneck');
        if (!isTShirt) return false;
      } else if (selectedMainCat === 'TROUSERS') {
        const isTrouser = cat === 'TROUSERS' || name.includes('trouser') || name.includes('chino') || name.includes('pants');
        if (!isTrouser) return false;
      }

      // 3. Sub-Filter (Full Sleeve, Casual, T-Shirt, Polo, Formal Trousers, Chinos & Pants)
      if (selectedSubFilter === 'FULL_SLEEVE') {
        const isFullSleeve = sleeve.includes('full') || (name.includes('shirt') && !name.includes('t-shirt') && !name.includes('polo'));
        if (!isFullSleeve) return false;
      } else if (selectedSubFilter === 'CASUAL_LINEN') {
        const isCasualLinen = name.includes('casual') || name.includes('linen') || fabric.includes('linen');
        if (!isCasualLinen) return false;
      } else if (selectedSubFilter === 'TSHIRTS') {
        const isTee = name.includes('t-shirt') || name.includes('crewneck') || (cat === 'T-SHIRTS' && !name.includes('polo'));
        if (!isTee) return false;
      } else if (selectedSubFilter === 'POLOS') {
        const isPolo = name.includes('polo') || fabric.includes('pique');
        if (!isPolo) return false;
      } else if (selectedSubFilter === 'FORMAL_TROUSERS') {
        const isFormalTrouser = name.includes('formal') || name.includes('wool') || fabric.includes('wool') || name.includes('black formal');
        if (!isFormalTrouser) return false;
      } else if (selectedSubFilter === 'CHINOS_PANTS') {
        const isChinoOrPants = name.includes('chino') || name.includes('pants') || name.includes('denim') || fabric.includes('twill');
        if (!isChinoOrPants) return false;
      } else if (selectedSubFilter === 'WOOL_TROUSERS') {
        const isWool = name.includes('wool') || fabric.includes('wool');
        if (!isWool) return false;
      } else if (selectedSubFilter === 'FORMAL_SHIRTS') {
        const isFormalShirt = name.includes('oxford') || (name.includes('shirt') && name.includes('formal'));
        if (!isFormalShirt) return false;
      }

      return true;
    });
  }, [products, selectedMainCat, selectedSubFilter, searchQuery]);

  // Dynamic count badges for filters
  const counts = useMemo(() => {
    return {
      all: products.length,
      shirts: products.filter((p) => p.category === 'SHIRTS' || (p.name.toLowerCase().includes('shirt') && !p.name.toLowerCase().includes('t-shirt') && !p.name.toLowerCase().includes('polo'))).length,
      tshirts: products.filter((p) => p.category === 'T-SHIRTS' || p.name.toLowerCase().includes('t-shirt') || p.name.toLowerCase().includes('polo')).length,
      trousers: products.filter((p) => p.category === 'TROUSERS' || p.name.toLowerCase().includes('trouser') || p.name.toLowerCase().includes('chino') || p.name.toLowerCase().includes('pants')).length,
      fullSleeve: products.filter((p) => (p.sleeve || p.attributes?.sleeve || '').toLowerCase().includes('full') || (p.name.toLowerCase().includes('shirt') && !p.name.toLowerCase().includes('t-shirt') && !p.name.toLowerCase().includes('polo'))).length,
      casualLinen: products.filter((p) => p.name.toLowerCase().includes('casual') || p.name.toLowerCase().includes('linen') || (p.attributes?.fabric || '').toLowerCase().includes('linen')).length,
      formalShirts: products.filter((p) => p.name.toLowerCase().includes('oxford') || (p.name.toLowerCase().includes('formal') && p.name.toLowerCase().includes('shirt'))).length,
      crewneckTees: products.filter((p) => p.name.toLowerCase().includes('crewneck') || (p.category === 'T-SHIRTS' && !p.name.toLowerCase().includes('polo'))).length,
      poloShirts: products.filter((p) => p.name.toLowerCase().includes('polo')).length,
      chinosPants: products.filter((p) => p.name.toLowerCase().includes('chino') || p.name.toLowerCase().includes('pants') || p.name.toLowerCase().includes('denim')).length,
      formalTrousers: products.filter((p) => p.name.toLowerCase().includes('formal') || p.name.toLowerCase().includes('wool')).length,
      woolTrousers: products.filter((p) => p.name.toLowerCase().includes('wool') || (p.attributes?.fabric || '').toLowerCase().includes('wool')).length,
    };
  }, [products]);

  return (
    <div className="w-full px-2 sm:px-4 md:px-6 py-4 space-y-6">
      
      {/* Top Header with Vyapar Mitra Branding & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#D5DEE9]">
        <div className="flex items-center gap-3">
          <img
            src="/vyapar_mitra_logo.png"
            alt="Vyapar Mitra"
            className="h-10 sm:h-11 w-auto object-contain"
          />
          <div className="h-6 w-[1px] bg-[#D5DEE9] hidden sm:block" />
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] font-semibold text-[#0F172A] bg-white px-2 py-0.5 rounded border border-[#D5DEE9] shadow-xs">
                LIVE INVENTORY
              </span>
              <span className="text-xs text-[#526176]">
                Wholesale & Margins
              </span>
            </div>
            <h1 className="font-heading text-xl sm:text-2xl font-bold text-[#0F172A] tracking-tight mt-0.5">
              Product Catalog
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsStudioOpen(true)}
            className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 py-2.5 text-[14px] font-['Inter'] font-semibold bg-[#0F172A] text-white rounded-[8px] hover:bg-[#1E293B] transition-all shadow-xs cursor-pointer"
          >
            <Wand2 className="w-4 h-4 text-[#087F6B]" />
            <span>+ Add New Product via AI Studio</span>
          </button>
          <button
            onClick={loadProducts}
            disabled={loading}
            className="p-2.5 sm:px-3 sm:py-2.5 text-xs font-medium border border-[#D5DEE9] bg-white text-[#526176] rounded-[8px] hover:bg-[#F8FAFC] transition-colors shadow-xs"
            title="Refresh Catalog"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Banner Strip (Preserved as requested) */}
      <div className="relative w-full h-24 sm:h-32 rounded-[12px] overflow-hidden border border-[#D5DEE9] shadow-xs">
        <img
          src="/catalog_banner.jpg"
          alt="Vyapar Mitra Apparel Collection"
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-black/50 to-transparent flex flex-col justify-center px-5 sm:px-8 text-white">
          <span className="text-[10px] font-mono tracking-widest text-[#FFF4DB] uppercase font-semibold">
            Merchant Inventory & Economics
          </span>
          <h2 className="text-base sm:text-xl font-bold tracking-tight text-white mt-0.5 font-heading">
            Active Catalog — Vyapar Mitra Collection
          </h2>
        </div>
      </div>

      {toastMsg && (
        <div className="p-3.5 rounded-[8px] bg-[#E8F7F1] border border-[#067647]/30 text-xs font-semibold text-[#067647] flex items-center gap-2 shadow-xs animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-[#067647] shrink-0" />
          <span>{toastMsg}</span>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-[8px] border border-[#92400E]/30 bg-[#FFF4DB] text-xs text-[#92400E] flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-[#92400E]" />
          <span>{error}</span>
        </div>
      )}

      {/* ============================================================== */}
      {/* RECENTLY ADDED SECTION (Positioned right below header banner)   */}
      {/* ============================================================== */}
      <div className="bg-white border border-[#D5DEE9] rounded-[16px] shadow-[0_2px_6px_rgba(15,23,42,0.04)] overflow-hidden">
        
        {/* Section Header with #E8EEF5 background and #C4CFDC bottom border */}
        <div className="bg-[#E8EEF5] border-b border-[#C4CFDC] px-5 py-3.5 sm:px-6 sm:py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="p-2 rounded-lg bg-[#0F172A] text-white shadow-xs">
              <Clock className="w-4 h-4 text-[#087F6B]" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-heading text-[19px] font-bold text-[#0F172A] tracking-tight">
                  Recently Added Products
                </h2>
                <span className="text-[11px] font-mono font-bold text-[#067647] bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#067647]/30 uppercase tracking-wider shadow-xs">
                  NEW ARRIVALS ({recentlyAdded.length})
                </span>
              </div>
              <p className="font-['Inter'] text-[14px] text-[#526176] mt-0.5">
                Fresh catalog additions with automated 4K studio photography, category classification & margin protection.
              </p>
            </div>
          </div>

          <button
            onClick={() => setIsStudioOpen(true)}
            className="self-start sm:self-auto text-xs font-semibold text-[#0F172A] hover:text-[#087F6B] hover:underline flex items-center gap-1 font-['Inter']"
          >
            <span>Generate Asset in Studio</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Recently Added Cards Grid */}
        <div className="p-5 sm:p-6 bg-white">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4.5">
            {recentlyAdded.map((item) => {
              const marginPct = item.price_paise > 0
                ? (((item.price_paise - item.cost_paise) / item.price_paise) * 100).toFixed(1)
                : '0.0';
              const imageUrl = item.attributes?.refined_photo_url ||
                (item.category === 'T-SHIRTS' ? '/clothing/tshirt_black.jpg' :
                 item.name.toLowerCase().includes('polo') ? '/clothing/polo_navy.jpg' :
                 '/clothing/white_oxford.jpg');

              return (
                <div
                  key={item.sku}
                  onClick={() => setSelectedProduct(item)}
                  className="p-4 rounded-[12px] bg-white border border-[#D5DEE9] hover:border-[#0F172A] shadow-[0_2px_6px_rgba(15,23,42,0.04)] transition-all space-y-3 flex flex-col justify-between cursor-pointer group"
                >
                  <div className="space-y-3">
                    {/* Image with "NEW" and SKU tag */}
                    <div className="relative w-full h-40 rounded-[10px] overflow-hidden bg-[#F8FAFC] border border-[#D5DEE9] flex items-center justify-center p-2 group-hover:border-[#0F172A] transition-colors">
                      <img
                        src={imageUrl}
                        alt={item.name}
                        className="max-h-full max-w-full object-contain"
                      />
                      <span className="absolute top-2 left-2 bg-[#E8F7F1] text-[#067647] border border-[#067647]/30 text-[10px] font-['Inter'] font-bold px-2 py-0.5 rounded shadow-xs flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#067647]" />
                        <span>{item.added_tag || 'NEW'}</span>
                      </span>
                      <span className="absolute bottom-2 right-2 bg-white text-[#0F172A] text-[11px] font-mono px-2 py-0.5 rounded border border-[#D5DEE9] shadow-xs">
                        {item.sku}
                      </span>
                    </div>

                    {/* Product Name & Category */}
                    <div>
                      <h3 className="font-['Inter'] text-[14px] font-semibold text-[#0F172A] line-clamp-1 group-hover:text-[#087F6B] transition-colors">
                        {item.name}
                      </h3>
                      <div className="text-[11px] font-mono text-[#667085] mt-0.5 flex items-center gap-2">
                        <span>{item.category}</span>
                        <span>•</span>
                        <span>{item.sleeve || item.attributes?.sleeve || 'Garment'}</span>
                      </div>
                    </div>

                    {/* Pricing & Margin Summary */}
                    <div className="p-2.5 bg-[#F8FAFC] rounded-[8px] border border-[#D5DEE9] space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-[#526176] font-['Inter'] text-[13px]">Retail Price:</span>
                        <strong className="text-[#0F172A] tabular-nums font-['Inter'] text-[16px] font-bold">
                          {formatPaise(item.price_paise)}
                        </strong>
                      </div>
                      <div className="flex items-center justify-between text-xs pt-1 border-t border-[#D5DEE9]">
                        <span className="text-[#526176] font-['Inter'] text-[13px]">Gross Margin:</span>
                        <span className="text-[#067647] font-bold font-mono text-[13px]">
                          {marginPct}% Net Margin
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Stock and Action Button */}
                  <div className="pt-2 flex items-center justify-between border-t border-[#D5DEE9]">
                    <span className="text-[11px] font-mono text-[#667085]">
                      Stock: <strong className="text-[#0F172A] font-semibold">{item.inventory_quantity} units</strong>
                    </span>
                    <button
                      type="button"
                      className="px-3 py-1.5 bg-[#0F172A] group-hover:bg-[#1E293B] text-white text-xs font-semibold rounded-[6px] transition-colors flex items-center gap-1 shadow-xs"
                    >
                      <span>Details</span>
                      <ArrowRight className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* ACTIVE MERCHANT PRODUCTS WITH RICH APPAREL FILTERS              */}
      {/* T-Shirts, Shirts, Full Sleeve, Casual, Trousers, Chinos & Pants */}
      {/* ============================================================== */}
      <div className="bg-white border border-[#D5DEE9] rounded-[16px] shadow-[0_2px_6px_rgba(15,23,42,0.04)] overflow-hidden">
        
        {/* Section Header with #E8EEF5 background and #C4CFDC bottom border */}
        <div className="bg-[#E8EEF5] border-b border-[#C4CFDC] p-4 sm:px-6 sm:py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-heading text-[19px] font-bold text-[#0F172A] tracking-tight">
                Active Merchant Products ({filteredProducts.length})
              </h2>
              <span className="text-[11px] font-mono font-semibold text-[#0F172A] bg-white px-2 py-0.5 rounded border border-[#D5DEE9] shadow-xs">
                {selectedMainCat === 'ALL' ? 'ALL APPAREL' : selectedMainCat}
              </span>
            </div>
            <p className="font-['Inter'] text-[14px] text-[#526176] mt-0.5">
              Tap any product row to review wholesale COGS, marketplace channel placements, and AI profit recommendations.
            </p>
          </div>

          <div className="flex items-center gap-1.5 text-xs text-[#526176] bg-white px-3 py-1.5 rounded-md border border-[#D5DEE9] shadow-xs shrink-0 self-start sm:self-auto">
            <Lock className="w-3.5 h-3.5 text-[#92400E]" />
            <span className="font-semibold text-[#92400E] font-['Inter']">COGS Firewalled from AI Buyers</span>
          </div>
        </div>

        {/* Filter Bar: Main Category Tabs + Apparel Sub-Filters + Search Box */}
        <div className="p-4 sm:px-6 bg-[#F8FAFC] border-b border-[#D5DEE9] space-y-3.5">
          
          {/* Row 1: Primary Category Tabs */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-[#526176] uppercase tracking-wider mr-1 font-['Inter'] flex items-center gap-1">
                <SlidersHorizontal className="w-3.5 h-3.5" />
                <span>Category:</span>
              </span>

              {/* All Products */}
              <button
                onClick={() => {
                  setSelectedMainCat('ALL');
                  setSelectedSubFilter('ALL');
                }}
                className={`px-3.5 py-1.5 text-xs rounded-[8px] font-semibold transition-all border shadow-xs ${
                  selectedMainCat === 'ALL'
                    ? 'bg-[#0F172A] text-white border-[#0F172A]'
                    : 'bg-white text-[#526176] border-[#D5DEE9] hover:border-[#0F172A] hover:text-[#0F172A]'
                }`}
              >
                All Products ({counts.all})
              </button>

              {/* Shirts */}
              <button
                onClick={() => {
                  setSelectedMainCat('SHIRTS');
                  setSelectedSubFilter('ALL');
                }}
                className={`px-3.5 py-1.5 text-xs rounded-[8px] font-semibold transition-all border shadow-xs ${
                  selectedMainCat === 'SHIRTS'
                    ? 'bg-[#0F172A] text-white border-[#0F172A]'
                    : 'bg-white text-[#526176] border-[#D5DEE9] hover:border-[#0F172A] hover:text-[#0F172A]'
                }`}
              >
                Shirts ({counts.shirts})
              </button>

              {/* T-Shirts & Polos */}
              <button
                onClick={() => {
                  setSelectedMainCat('T_SHIRTS');
                  setSelectedSubFilter('ALL');
                }}
                className={`px-3.5 py-1.5 text-xs rounded-[8px] font-semibold transition-all border shadow-xs ${
                  selectedMainCat === 'T_SHIRTS'
                    ? 'bg-[#0F172A] text-white border-[#0F172A]'
                    : 'bg-white text-[#526176] border-[#D5DEE9] hover:border-[#0F172A] hover:text-[#0F172A]'
                }`}
              >
                T-Shirts & Polos ({counts.tshirts})
              </button>

              {/* Trousers & Pants */}
              <button
                onClick={() => {
                  setSelectedMainCat('TROUSERS');
                  setSelectedSubFilter('ALL');
                }}
                className={`px-3.5 py-1.5 text-xs rounded-[8px] font-semibold transition-all border shadow-xs ${
                  selectedMainCat === 'TROUSERS'
                    ? 'bg-[#0F172A] text-white border-[#0F172A]'
                    : 'bg-white text-[#526176] border-[#D5DEE9] hover:border-[#0F172A] hover:text-[#0F172A]'
                }`}
              >
                Trousers & Pants ({counts.trousers})
              </button>
            </div>

            {/* Instant Search Box */}
            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 text-[#667085] absolute left-3 top-2.5 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search name, SKU, or fabric..."
                className="w-full text-xs font-medium pl-8.5 pr-3 py-1.5 bg-white text-[#0F172A] border border-[#D5DEE9] rounded-[8px] shadow-xs placeholder:text-[#667085] focus:outline-none focus:border-[#0F172A] transition-all"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 top-2 text-xs text-[#667085] hover:text-[#0F172A]"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* Row 2: Context-Aware Sub-Filters tailored strictly to selected category */}
          <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-[#D5DEE9]/70 text-[11px]">
            <span className="font-semibold text-[#667085] uppercase tracking-wider mr-1">
              {selectedMainCat === 'TROUSERS' ? 'Trouser Style:' :
               selectedMainCat === 'SHIRTS' ? 'Shirt Style:' :
               selectedMainCat === 'T_SHIRTS' ? 'T-Shirt & Polo Style:' :
               'Style & Sleeve:'}
            </span>

            {/* If TROUSERS selected: ONLY show Trouser & Pants filters */}
            {selectedMainCat === 'TROUSERS' && (
              <>
                <button
                  onClick={() => setSelectedSubFilter('ALL')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
                    selectedSubFilter === 'ALL'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  All Trousers & Pants ({counts.trousers})
                </button>
                <button
                  onClick={() => setSelectedSubFilter('FORMAL_TROUSERS')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'FORMAL_TROUSERS'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Formal Trousers</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.formalTrousers})</span>
                </button>
                <button
                  onClick={() => setSelectedSubFilter('CHINOS_PANTS')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'CHINOS_PANTS'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Chinos & Pants</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.chinosPants})</span>
                </button>
                <button
                  onClick={() => setSelectedSubFilter('WOOL_TROUSERS')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'WOOL_TROUSERS'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Italian Wool Trousers</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.woolTrousers})</span>
                </button>
              </>
            )}

            {/* If SHIRTS selected: ONLY show Shirt filters */}
            {selectedMainCat === 'SHIRTS' && (
              <>
                <button
                  onClick={() => setSelectedSubFilter('ALL')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
                    selectedSubFilter === 'ALL'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  All Shirts ({counts.shirts})
                </button>
                <button
                  onClick={() => setSelectedSubFilter('FULL_SLEEVE')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'FULL_SLEEVE'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Full Sleeve Shirts</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.fullSleeve})</span>
                </button>
                <button
                  onClick={() => setSelectedSubFilter('CASUAL_LINEN')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'CASUAL_LINEN'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Casual & Linen Shirts</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.casualLinen})</span>
                </button>
                <button
                  onClick={() => setSelectedSubFilter('FORMAL_SHIRTS')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'FORMAL_SHIRTS'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Formal Oxford Shirts</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.formalShirts})</span>
                </button>
              </>
            )}

            {/* If T_SHIRTS selected: ONLY show T-Shirt & Polo filters */}
            {selectedMainCat === 'T_SHIRTS' && (
              <>
                <button
                  onClick={() => setSelectedSubFilter('ALL')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
                    selectedSubFilter === 'ALL'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  All T-Shirts & Polos ({counts.tshirts})
                </button>
                <button
                  onClick={() => setSelectedSubFilter('TSHIRTS')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'TSHIRTS'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Crewneck T-Shirts</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.crewneckTees})</span>
                </button>
                <button
                  onClick={() => setSelectedSubFilter('POLOS')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'POLOS'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Polo Shirts</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.poloShirts})</span>
                </button>
              </>
            )}

            {/* If ALL selected: Show comprehensive multi-apparel style filters */}
            {selectedMainCat === 'ALL' && (
              <>
                <button
                  onClick={() => setSelectedSubFilter('ALL')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors ${
                    selectedSubFilter === 'ALL'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  All Styles ({counts.all})
                </button>
                <button
                  onClick={() => setSelectedSubFilter('FULL_SLEEVE')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'FULL_SLEEVE'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Full Sleeve Shirts</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.fullSleeve})</span>
                </button>
                <button
                  onClick={() => setSelectedSubFilter('CASUAL_LINEN')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'CASUAL_LINEN'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Casual & Linen Shirts</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.casualLinen})</span>
                </button>
                <button
                  onClick={() => setSelectedSubFilter('TSHIRTS')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'TSHIRTS'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Crewneck T-Shirts</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.crewneckTees})</span>
                </button>
                <button
                  onClick={() => setSelectedSubFilter('POLOS')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'POLOS'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Polo Shirts</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.poloShirts})</span>
                </button>
                <button
                  onClick={() => setSelectedSubFilter('FORMAL_TROUSERS')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'FORMAL_TROUSERS'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Formal Trousers</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.formalTrousers})</span>
                </button>
                <button
                  onClick={() => setSelectedSubFilter('CHINOS_PANTS')}
                  className={`px-2.5 py-1 rounded-md font-medium border transition-colors flex items-center gap-1 ${
                    selectedSubFilter === 'CHINOS_PANTS'
                      ? 'bg-[#0F172A] text-white border-[#0F172A]'
                      : 'bg-white text-[#526176] border-[#D5DEE9] hover:bg-[#E8EEF5]'
                  }`}
                >
                  <span>Chinos & Pants</span>
                  <span className="font-mono text-[10px] opacity-80">({counts.chinosPants})</span>
                </button>
              </>
            )}
          </div>
        </div>

        {/* Catalog Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-[#F8FAFC] text-[#526176] font-semibold border-b border-[#D5DEE9]">
              <tr>
                <th className="py-3 px-4 font-['Inter']">SKU & Product Name</th>
                <th className="py-3 px-3 font-['Inter']">Category & Style</th>
                <th className="py-3 px-3 font-['Inter']">Physical Stock</th>
                <th className="py-3 px-3 font-['Inter']">Reserved</th>
                <th className="py-3 px-3 font-['Inter']">List Price</th>
                <th className="py-3 px-3 font-['Inter']">Wholesale COGS</th>
                <th className="py-3 px-3 font-['Inter']">Gross Margin</th>
                <th className="py-3 px-4 text-right font-['Inter']">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#D5DEE9] bg-white">
              {filteredProducts.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-[#526176]">
                    <div className="space-y-1">
                      <p className="font-semibold text-[#0F172A]">No products matched your filter</p>
                      <p className="text-xs">Try selecting 'All Products' or clearing the search query.</p>
                      <button
                        onClick={() => {
                          setSelectedMainCat('ALL');
                          setSelectedSubFilter('ALL');
                          setSearchQuery('');
                        }}
                        className="mt-2 text-xs font-semibold text-[#087F6B] hover:underline"
                      >
                        Reset All Filters
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredProducts.map((p) => {
                  const margin = p.price_paise > 0
                    ? ((p.price_paise - p.cost_paise) / p.price_paise) * 100
                    : 0;
                  const imageUrl = p.attributes?.refined_photo_url ||
                    (p.category === 'T-SHIRTS' ? '/clothing/tshirt_black.jpg' :
                     p.name.toLowerCase().includes('polo') ? '/clothing/polo_navy.jpg' :
                     p.name.toLowerCase().includes('oxford') || p.name.toLowerCase().includes('white') ? '/clothing/white_oxford.jpg' :
                     p.name.toLowerCase().includes('navy') ? '/clothing/navy_shirt.jpg' :
                     p.name.toLowerCase().includes('linen') || p.name.toLowerCase().includes('olive') ? '/clothing/linen_shirt.jpg' :
                     p.name.toLowerCase().includes('khaki') || p.name.toLowerCase().includes('chino') ? '/clothing/khaki_chino.jpg' :
                     p.name.toLowerCase().includes('grey') || p.name.toLowerCase().includes('charcoal') ? '/clothing/grey_trouser.jpg' :
                     '/clothing/black_trouser.jpg');

                  return (
                    <tr
                      key={p.id || p.sku}
                      onClick={() => setSelectedProduct(p)}
                      className="hover:bg-[#F8FAFC] active:bg-[#E8EEF5] cursor-pointer transition-colors group"
                      title="Click to view complete description, marketplaces, and AI recommendations"
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <img
                            src={imageUrl}
                            alt={p.name}
                            className="w-11 h-11 rounded-[8px] object-cover bg-[#F8FAFC] border border-[#D5DEE9] shrink-0 group-hover:border-[#0F172A] transition-colors"
                          />
                          <div>
                            <div className="font-['Inter'] font-semibold text-[14px] text-[#0F172A] group-hover:text-[#087F6B] transition-colors line-clamp-1">
                              {p.name}
                            </div>
                            <div className="font-mono text-[11px] text-[#667085] mt-0.5 flex items-center gap-1.5">
                              <span>{p.sku}</span>
                              {p.is_recent && (
                                <span className="bg-[#E8F7F1] text-[#067647] font-semibold text-[9px] px-1.5 py-0.2 rounded border border-[#067647]/30">
                                  NEW
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <span className="font-mono text-[11px] font-medium text-[#526176] bg-[#F8FAFC] px-2 py-0.5 rounded border border-[#D5DEE9]">
                          {p.category}
                        </span>
                        <div className="text-[10px] text-[#667085] mt-1 font-['Inter'] font-medium">
                          {p.sleeve && p.sleeve !== 'N/A'
                            ? `${p.sleeve}${p.attributes?.type ? ` • ${p.attributes.type}` : ''}`
                            : (p.attributes?.type || 'Standard')}
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <span className="font-semibold text-[#0F172A] font-mono text-[12px]">
                          {p.inventory_quantity} units
                        </span>
                        {p.inventory_quantity <= 10 && (
                          <div className="text-[10px] font-bold text-[#92400E] font-mono mt-0.5">
                            LOW STOCK
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-3 font-mono text-[12px] text-[#526176]">
                        {p.reserved_quantity || 0}
                      </td>
                      <td className="py-3 px-3 font-['Inter'] font-bold text-[14px] text-[#0F172A] tabular-nums">
                        {formatPaise(p.price_paise)}
                      </td>
                      <td className="py-3 px-3 font-mono text-[12px] text-[#667085] tabular-nums">
                        {formatPaise(p.cost_paise)}
                      </td>
                      <td className="py-3 px-3">
                        <span className="font-mono font-bold text-[12px] text-[#067647] bg-[#E8F7F1] px-2 py-0.5 rounded border border-[#067647]/30">
                          {margin.toFixed(1)}%
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <span className="inline-flex items-center gap-1 text-[12px] font-semibold text-[#0F172A] bg-[#F8FAFC] px-2.5 py-1 rounded-[6px] border border-[#D5DEE9] group-hover:bg-[#0F172A] group-hover:text-white transition-all shadow-xs">
                          <span>Details</span>
                          <ArrowRight className="w-3 h-3" />
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Product Detail Modal: Description, Marketplaces & AI Recommendations */}
      <ProductDetailModal
        product={selectedProduct}
        isOpen={!!selectedProduct}
        onClose={() => setSelectedProduct(null)}
        onActionComplete={(msg) => {
          setToastMsg(msg);
          loadProducts();
        }}
      />

      {/* Multimodal AI Product Studio Modal */}
      <AIProductStudioModal
        isOpen={isStudioOpen}
        onClose={() => setIsStudioOpen(false)}
        onProductCreated={loadProducts}
      />
    </div>
  );
}
