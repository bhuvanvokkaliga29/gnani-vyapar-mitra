'use client';

import React, { useState, useEffect } from 'react';
import {
  Users,
  Send,
  Plus,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  ShieldCheck,
  TrendingUp,
  Tag,
  Clock,
  Sparkles
} from 'lucide-react';
import { useMerchant } from '@/lib/MerchantContext';
import { api, formatPaise, formatPercent } from '@/lib/api';

export default function CampaignsPage() {
  const { currentMerchant } = useMerchant();
  const [activeTab, setActiveTab] = useState<'WINBACK' | 'GROUP_DEALS'>('WINBACK');
  const [contacts, setContacts] = useState<any[]>([]);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [groupDeals, setGroupDeals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New campaign form state
  const [campaignName, setCampaignName] = useState('Monsoon Travel Win-Back');
  const [discountPercent, setDiscountPercent] = useState(8.0);
  const [creatingCampaign, setCreatingCampaign] = useState(false);

  // New group deal form state
  const [groupName, setGroupName] = useState('Prestige Tech Park Techies');
  const [groupThreshold, setGroupThreshold] = useState(10);
  const [groupPricePaise, setGroupPricePaise] = useState(269900); // ₹2,699
  const [creatingGroupDeal, setCreatingGroupDeal] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [contactsRes, campRes, dealsRes] = await Promise.all([
        api.getContacts(currentMerchant.id),
        api.getCampaigns(currentMerchant.id),
        api.getGroupDeals(currentMerchant.id)
      ]);
      setContacts(contactsRes.contacts || []);
      setCampaigns(campRes.campaigns || []);
      setGroupDeals(dealsRes.deals || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load campaigns');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [currentMerchant.id]);

  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingCampaign(true);
    try {
      await api.createCampaign(currentMerchant.id, campaignName, discountPercent);
      await loadData();
    } catch (err: any) {
      alert('Failed to create campaign: ' + err.message);
    } finally {
      setCreatingCampaign(false);
    }
  };

  const handleDispatch = async (campaignId: string) => {
    try {
      await api.dispatchCampaign(currentMerchant.id, campaignId);
      await loadData();
    } catch (err: any) {
      alert('Failed to dispatch campaign: ' + err.message);
    }
  };

  const handleOptOut = async (phone: string) => {
    try {
      await api.optOutContact(currentMerchant.id, phone);
      await loadData();
    } catch (err: any) {
      alert('Failed to update consent: ' + err.message);
    }
  };

  const handleCreateGroupDeal = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingGroupDeal(true);
    try {
      await api.createGroupDeal(
        currentMerchant.id,
        groupName,
        'prod_travel_backpack',
        groupThreshold,
        groupPricePaise
      );
      await loadData();
    } catch (err: any) {
      alert('Failed to create group deal: ' + err.message);
    } finally {
      setCreatingGroupDeal(false);
    }
  };

  const handlePledge = async (dealId: string) => {
    try {
      await api.pledgeGroupDeal(dealId, 1);
      await loadData();
    } catch (err: any) {
      alert('Failed to pledge unit: ' + err.message);
    }
  };

  const optedInCount = contacts.filter((c) => c.is_opted_in).length;

  return (
    <div className="w-full px-2 sm:px-4 md:px-6 py-4 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#d8d8d8]">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] font-semibold text-[#146ef5] bg-[#eff6ff] px-2 py-0.5 rounded-[4px] border border-[#146ef5]/20">
              RETENTION & GROUP COMMERCE
            </span>
            <span className="text-xs text-[#5a5a5a]">
              Consent-Safe Customer Retention
            </span>
          </div>
          <h1 className="text-2xl md:text-3xl font-semibold text-[#080808] tracking-tight mt-1">
            Customer Win-Back & Group Deals
          </h1>
          <p className="text-xs md:text-sm text-[#5a5a5a] mt-0.5 max-w-3xl leading-relaxed">
            Recover inactive shoppers with policy-governed incentives and activate hyper-local volume deals with deterministic margin floor protection.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center border border-[#d8d8d8] rounded-[4px] p-0.5 bg-[#ffffff]">
          <button
            onClick={() => setActiveTab('WINBACK')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-[2px] transition-colors ${
              activeTab === 'WINBACK' ? 'bg-[#146ef5] text-white' : 'text-[#5a5a5a] hover:text-[#080808]'
            }`}
          >
            Win-Back Campaigns
          </button>
          <button
            onClick={() => setActiveTab('GROUP_DEALS')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-[2px] transition-colors ${
              activeTab === 'GROUP_DEALS' ? 'bg-[#146ef5] text-white' : 'text-[#5a5a5a] hover:text-[#080808]'
            }`}
          >
            Community Group Deals
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-[4px] border border-rose-300 bg-rose-50 text-xs text-rose-800 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}

      {activeTab === 'WINBACK' ? (
        <div className="space-y-6">
          {/* Top Metric Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="studio-card p-4">
              <span className="text-[11px] font-semibold text-[#5a5a5a] uppercase tracking-wider block">
                Opted-in Customer Contacts
              </span>
              <div className="text-2xl font-bold text-[#080808] mt-1">
                {optedInCount} <span className="text-xs font-normal text-[#5a5a5a]">/ {contacts.length} total</span>
              </div>
              <p className="text-[11px] text-emerald-700 mt-1 font-medium">Consent strictly verified</p>
            </div>

            <div className="studio-card p-4">
              <span className="text-[11px] font-semibold text-[#5a5a5a] uppercase tracking-wider block">
                Max Allowable Discount
              </span>
              <div className="text-2xl font-bold text-[#146ef5] mt-1">
                8.0%
              </div>
              <p className="text-[11px] text-[#5a5a5a] mt-1">Owner-configured ceiling</p>
            </div>

            <div className="studio-card p-4">
              <span className="text-[11px] font-semibold text-[#5a5a5a] uppercase tracking-wider block">
                Simulator Mode
              </span>
              <div className="text-2xl font-bold text-amber-700 mt-1">
                ACTIVE
              </div>
              <p className="text-[11px] text-[#5a5a5a] mt-1">Simulated sends clearly labeled</p>
            </div>
          </div>

          {/* Create Campaign & Dispatched Campaigns */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Create Campaign Form (Col 5) */}
            <div className="lg:col-span-5 studio-card p-6 space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-[#080808]">Create Win-Back Campaign</h3>
                <p className="text-xs text-[#5a5a5a]">
                  Re-engage inactive customers without eroding margin.
                </p>
              </div>

              <form onSubmit={handleCreateCampaign} className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-[#080808] mb-1">
                    Campaign Name
                  </label>
                  <input
                    type="text"
                    value={campaignName}
                    onChange={(e) => setCampaignName(e.target.value)}
                    className="w-full studio-input px-3 py-1.5 text-xs text-[#080808]"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-[#080808] mb-1">
                    Incentive Discount (%)
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    max="8.0"
                    min="1.0"
                    value={discountPercent}
                    onChange={(e) => setDiscountPercent(parseFloat(e.target.value))}
                    className="w-full studio-input px-3 py-1.5 text-xs text-[#080808]"
                    required
                  />
                  <span className="text-[10px] text-[#5a5a5a] mt-0.5 block">
                    Must not exceed 8.0% merchant maximum discount ceiling.
                  </span>
                </div>

                <div>
                  <label className="block text-xs font-medium text-[#080808] mb-1">
                    Target Segment
                  </label>
                  <select className="w-full studio-input px-3 py-1.5 text-xs text-[#080808]">
                    <option value="INACTIVE_60_DAYS">Inactive Shoppers (&gt; 60 days since order)</option>
                    <option value="ALL_OPTED_IN">All Opted-in Contacts ({optedInCount})</option>
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={creatingCampaign}
                  className="w-full btn-primary py-2 text-xs font-semibold"
                >
                  {creatingCampaign ? 'Validating...' : 'Create Campaign Proposal'}
                </button>
              </form>
            </div>

            {/* Campaign History & Simulated Metrics (Col 7) */}
            <div className="lg:col-span-7 studio-card p-6 space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-[#080808]">Campaign History</h3>
                <p className="text-xs text-[#5a5a5a]">
                  Governed marketing actions with simulated performance tracking.
                </p>
              </div>

              <div className="space-y-3">
                {campaigns.map((c) => (
                  <div key={c.id} className="p-4 border border-[#d8d8d8] rounded-[6px] space-y-3 bg-[#ffffff]">
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-semibold text-xs text-[#080808]">{c.name}</div>
                        <div className="text-[11px] text-[#5a5a5a]">
                          {c.recipient_count} recipients • {c.offered_discount_percent}% incentive
                        </div>
                      </div>
                      <span className="px-2 py-0.5 rounded-[4px] text-[10px] font-semibold bg-[#f0f0f0] border border-[#d8d8d8] text-[#5a5a5a]">
                        {c.status}
                      </span>
                    </div>

                    <div className="p-2.5 bg-[#f0f0f0] rounded-[4px] text-xs font-mono text-[#080808]">
                      {c.message_template}
                    </div>

                    {c.status === 'DISPATCHED' && (
                      <div className="grid grid-cols-3 gap-2 pt-1 border-t border-[#d8d8d8] text-xs">
                        <div>
                          <span className="text-[10px] text-[#5a5a5a] block">Simulated Opens</span>
                          <span className="font-bold text-[#080808]">{c.simulated_opens}</span>
                        </div>
                        <div>
                          <span className="text-[10px] text-[#5a5a5a] block">Conversions</span>
                          <span className="font-bold text-emerald-700">{c.simulated_conversions}</span>
                        </div>
                        <div>
                          <span className="text-[10px] text-[#5a5a5a] block">Simulated Revenue</span>
                          <span className="font-bold text-[#146ef5]">{formatPaise(c.simulated_revenue_paise)}</span>
                        </div>
                      </div>
                    )}

                    {c.status === 'PENDING_APPROVAL' && (
                      <div className="flex justify-end pt-1">
                        <button
                          onClick={() => handleDispatch(c.id)}
                          className="px-3 py-1.5 text-xs font-semibold bg-[#146ef5] text-white rounded-[4px] hover:bg-[#1366e2]"
                        >
                          Simulate Dispatch to Opted-in Contacts
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Customer Contacts & Consent Table */}
          <div className="studio-card p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-[#080808]">Customer Contacts & Consent Registry</h3>
                <p className="text-xs text-[#5a5a5a]">
                  Only contacts with verified opt-in are eligible for campaigns. Unsubscribing (STOP) removes contact permanently.
                </p>
              </div>
            </div>

            <div className="overflow-x-auto border border-[#d8d8d8] rounded-[4px]">
              <table className="w-full text-xs text-left">
                <thead className="bg-[#f0f0f0] text-[#080808] font-semibold border-b border-[#d8d8d8]">
                  <tr>
                    <th className="py-2 px-3">Name</th>
                    <th className="py-2 px-3">Phone</th>
                    <th className="py-2 px-3">Orders</th>
                    <th className="py-2 px-3">Lifetime Spend</th>
                    <th className="py-2 px-3">Consent Status</th>
                    <th className="py-2 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#d8d8d8]">
                  {contacts.map((c) => (
                    <tr key={c.id} className="hover:bg-[#f0f0f0]">
                      <td className="py-2.5 px-3 font-semibold text-[#080808]">{c.name}</td>
                      <td className="py-2.5 px-3 font-mono text-[#5a5a5a]">{c.phone}</td>
                      <td className="py-2.5 px-3">{c.total_orders_count}</td>
                      <td className="py-2.5 px-3 font-medium text-[#080808]">{formatPaise(c.total_spend_paise)}</td>
                      <td className="py-2.5 px-3">
                        {c.is_opted_in ? (
                          <span className="px-2 py-0.5 rounded-[4px] text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                            OPTED-IN
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-[4px] text-[10px] font-semibold bg-rose-50 text-rose-800 border border-rose-200">
                            STOPPED / UNSUBSCRIBED
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        {c.is_opted_in ? (
                          <button
                            onClick={() => handleOptOut(c.phone)}
                            className="px-2 py-1 text-[11px] text-rose-700 hover:underline"
                          >
                            Simulate STOP
                          </button>
                        ) : (
                          <span className="text-[11px] text-[#5a5a5a]">Excluded</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        /* Community Group Deals View */
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Create Deal Form (Col 5) */}
            <div className="lg:col-span-5 studio-card p-6 space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-[#080808]">Create Community Group Deal</h3>
                <p className="text-xs text-[#5a5a5a]">
                  Unlock volume deals for hostels, offices, or societies while preserving margin floor.
                </p>
              </div>

              <form onSubmit={handleCreateGroupDeal} className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-[#080808] mb-1">
                    Target Community / Group Name
                  </label>
                  <input
                    type="text"
                    value={groupName}
                    onChange={(e) => setGroupName(e.target.value)}
                    className="w-full studio-input px-3 py-1.5 text-xs text-[#080808]"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-[#080808] mb-1">
                    Minimum Activation Threshold (Units)
                  </label>
                  <input
                    type="number"
                    min="5"
                    max="50"
                    value={groupThreshold}
                    onChange={(e) => setGroupThreshold(parseInt(e.target.value))}
                    className="w-full studio-input px-3 py-1.5 text-xs text-[#080808]"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-[#080808] mb-1">
                    Group Price (Paise)
                  </label>
                  <input
                    type="number"
                    value={groupPricePaise}
                    onChange={(e) => setGroupPricePaise(parseInt(e.target.value))}
                    className="w-full studio-input px-3 py-1.5 text-xs text-[#080808]"
                    required
                  />
                  <span className="text-[10px] text-[#5a5a5a] mt-0.5 block">
                    Equivalent to {formatPaise(groupPricePaise)}. Backend will reject if gross margin &lt; 25.0%.
                  </span>
                </div>

                <button
                  type="submit"
                  disabled={creatingGroupDeal}
                  className="w-full btn-primary py-2 text-xs font-semibold"
                >
                  {creatingGroupDeal ? 'Verifying Margin...' : 'Launch Group Deal'}
                </button>
              </form>
            </div>

            {/* Active Group Deals (Col 7) */}
            <div className="lg:col-span-7 studio-card p-6 space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-[#080808]">Active Group Deals</h3>
                <p className="text-xs text-[#5a5a5a]">
                  When threshold is reached, deals unlock at authorized volume prices.
                </p>
              </div>

              <div className="space-y-4">
                {groupDeals.map((d) => {
                  const progressPct = Math.min(100, Math.round((d.current_pledged_units / d.min_threshold_units) * 100));
                  return (
                    <div key={d.id} className="p-4 border border-[#d8d8d8] rounded-[6px] space-y-3 bg-[#ffffff]">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-semibold text-xs text-[#080808]">{d.target_group_name}</div>
                          <div className="font-mono text-[10px] text-[#146ef5]">CODE: {d.deal_code}</div>
                        </div>
                        <span className="px-2 py-0.5 rounded-[4px] text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                          {d.status}
                        </span>
                      </div>

                      {/* Progress Bar */}
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="text-[#5a5a5a]">Pledged Units:</span>
                          <span className="font-bold text-[#080808]">
                            {d.current_pledged_units} / {d.min_threshold_units} ({progressPct}%)
                          </span>
                        </div>
                        <div className="w-full bg-[#f0f0f0] rounded-full h-2 overflow-hidden border border-[#d8d8d8]">
                          <div
                            className="bg-[#146ef5] h-full transition-all duration-300"
                            style={{ width: `${progressPct}%` }}
                          />
                        </div>
                      </div>

                      <div className="flex items-center justify-between pt-2 border-t border-[#d8d8d8] text-xs">
                        <div>
                          <span className="text-[#5a5a5a] text-[11px]">Group Price: </span>
                          <span className="font-bold text-[#080808]">{formatPaise(d.discounted_price_paise)}</span>
                          <span className="text-emerald-700 ml-2 font-semibold">({d.gross_margin_percent}% Margin)</span>
                        </div>

                        <button
                          onClick={() => handlePledge(d.id)}
                          className="px-3 py-1 text-xs font-semibold border border-[#146ef5] text-[#146ef5] rounded-[4px] hover:bg-[#eff6ff]"
                        >
                          + Pledge 1 Unit
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
