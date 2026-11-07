'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare,
  ShieldAlert,
  Send,
  RefreshCw,
  CheckCircle2,
  Clock,
  Smartphone,
  Server,
  Key,
  Globe,
  Sparkles,
  ArrowRight,
  ChevronRight,
  Info,
  Copy,
  Check
} from 'lucide-react';
import { api } from '@/lib/api';

interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: string;
  intent?: string;
  wamid?: string;
  isPolicyAlert?: boolean;
}

export default function WhatsAppAgentPage() {
  const [diagnostics, setDiagnostics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [senderPhone, setSenderPhone] = useState('+919113960498');
  const [inputText, setInputText] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Chat message history
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init_1',
      sender: 'agent',
      text: '👋 ನಮಸ್ಕಾರ! Welcome to Vyapar Mitra — Vastram AI Business Assistant.\n\nYou can manage retail products, verify profit margins, check stock alerts, or create clearance offers in Kannada, English, or Hindi.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const fetchDiagnostics = async () => {
    try {
      const data = await api.getWhatsAppDiagnostics();
      setDiagnostics(data);
      if (data?.configuration?.target_merchant_phone) {
        setSenderPhone(data.configuration.target_merchant_phone);
      }
    } catch (err) {
      console.error('Failed to fetch WhatsApp diagnostics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDiagnostics();
    const interval = setInterval(fetchDiagnostics, 6000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputText;
    if (!text.trim() || isSending) return;

    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      sender: 'user',
      text: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInputText('');
    setIsSending(true);

    try {
      const response = await api.simulateWhatsApp(senderPhone, text);
      const processed = response?.result?.processed?.[0];
      const reply = processed?.reply || '✅ Message acknowledged by WhatsApp Cloud API.';
      const intent = processed?.intent;
      const isPolicyAlert = reply.includes('Policy Alert') || reply.includes('ನೀತಿ ಎಚ್ಚರಿಕೆ');

      const agentMsg: ChatMessage = {
        id: `agent_${Date.now()}`,
        sender: 'agent',
        text: reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        intent: intent,
        wamid: processed?.wamid,
        isPolicyAlert: isPolicyAlert
      };

      setMessages((prev) => [...prev, agentMsg]);
      await fetchDiagnostics();
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          sender: 'agent',
          text: `❌ Error dispatching message: ${err.message || 'API connection failed'}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const copyToClipboard = (text: string, keyName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(keyName);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Quick Action Demo Pills
  const DEMO_ACTIONS = [
    {
      label: 'Ee black bag price 1800 inda 1600 maadu',
      lang: 'Kannada Price Cut',
      desc: 'Triggers Deterministic Policy Margin Guardrail',
      color: 'border-purple-200 bg-purple-50 text-purple-700 hover:bg-purple-100'
    },
    {
      label: 'YES',
      lang: 'Confirm Action',
      desc: 'Authorizes Compliant Safe Price Floor',
      color: 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
    },
    {
      label: 'Change backpack price to 2500',
      lang: 'English Price Update',
      desc: 'Valid Margin (28% >= 25%)',
      color: 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100'
    },
    {
      label: 'Black bag ka price 1600 kar do',
      lang: 'Hindi Price Cut',
      desc: 'Multilingual NLU Extraction',
      color: 'border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100'
    },
    {
      label: 'Add 25 stock to backpack',
      lang: 'Inventory Restock',
      desc: 'Adds 25 Units with Confirmation',
      color: 'border-teal-200 bg-teal-50 text-teal-700 hover:bg-teal-100'
    },
    {
      label: 'Stock eshtu ide nodu',
      lang: 'Kannada Inventory Query',
      desc: 'Real-Time Catalog Stock Report',
      color: 'border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
    },
    {
      label: 'CANCEL',
      lang: 'Abort Pending Action',
      desc: 'Single-Use Token Revocation',
      color: 'border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100'
    }
  ];

  return (
    <div className="w-full px-2 sm:px-4 md:px-6 py-4 space-y-6 pb-12">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 bg-emerald-500 text-white rounded-lg shadow-sm">
              <MessageSquare className="w-5 h-5" />
            </span>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
              WhatsApp Business Live Agent
            </h1>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Live Webhook Active
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Meta Cloud API integration with multilingual natural language reasoning, deterministic margin guardrails, and single-use confirmations.
          </p>
        </div>

        <button
          onClick={fetchDiagnostics}
          className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm transition-colors self-start md:self-auto"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Telemetry
        </button>
      </div>

      {/* Operational Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center gap-2 text-slate-500 text-xs font-medium uppercase tracking-wider mb-1">
            <Server className="w-3.5 h-3.5 text-blue-500" />
            Delivery Engine
          </div>
          <div className="text-base font-bold text-slate-800">
            {diagnostics?.delivery_mode === 'META_CLOUD_API' ? (
              <span className="text-emerald-600 flex items-center gap-1">
                Meta Cloud API <span className="text-xs px-1.5 py-0.5 bg-emerald-100 rounded">Live</span>
              </span>
            ) : (
              <span className="text-amber-600 flex items-center gap-1">
                Mock Fallback <span className="text-xs px-1.5 py-0.5 bg-amber-100 rounded">Interactive</span>
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-1">Outbound dispatch mode</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center gap-2 text-slate-500 text-xs font-medium uppercase tracking-wider mb-1">
            <Smartphone className="w-3.5 h-3.5 text-emerald-500" />
            Merchant Phone
          </div>
          <div className="text-base font-bold font-mono text-slate-800">
            {diagnostics?.configuration?.target_merchant_phone || '+919113960498'}
          </div>
          <p className="text-xs text-slate-400 mt-1">Authorized test operator</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center gap-2 text-slate-500 text-xs font-medium uppercase tracking-wider mb-1">
            <Clock className="w-3.5 h-3.5 text-purple-500" />
            Pending Confirmations
          </div>
          <div className="text-xl font-bold text-purple-700">
            {diagnostics?.metrics?.active_pending_confirmations ?? 0}
          </div>
          <p className="text-xs text-slate-400 mt-1">15-min TTL authorization tokens</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
          <div className="flex items-center gap-2 text-slate-500 text-xs font-medium uppercase tracking-wider mb-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-teal-500" />
            Webhooks Processed
          </div>
          <div className="text-xl font-bold text-teal-700">
            {diagnostics?.metrics?.total_inbound_webhooks ?? 0}
          </div>
          <p className="text-xs text-slate-400 mt-1">WAMID deduplicated ledger</p>
        </div>
      </div>

      {/* Main Grid: Live Terminal (Left) and Diagnostics Inspector (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: WhatsApp Interactive Terminal */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden flex flex-col h-[640px]">
            {/* Terminal Header */}
            <div className="bg-emerald-600 px-4 py-3 text-white flex items-center justify-between shadow-xs">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center font-bold text-sm">
                  WA
                </div>
                <div>
                  <h3 className="font-semibold text-sm leading-tight">Atlas Travel Agent (Official WhatsApp)</h3>
                  <div className="flex items-center gap-1.5 text-xs text-emerald-100">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-ping" />
                    Online • Multilingual AI Ready
                  </div>
                </div>
              </div>

              <div className="text-xs bg-emerald-700/60 px-2.5 py-1 rounded-md font-mono">
                {senderPhone}
              </div>
            </div>

            {/* Chat Message Scrollable Container */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-[#efeae2]/40">
              {messages.map((msg) => {
                const isUser = msg.sender === 'user';
                return (
                  <div
                    key={msg.id}
                    className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-2.5 shadow-xs text-sm ${
                        isUser
                          ? 'bg-emerald-600 text-white rounded-tr-xs'
                          : msg.isPolicyAlert
                          ? 'bg-amber-50 text-slate-800 border border-amber-300 rounded-tl-xs'
                          : 'bg-white text-slate-800 border border-slate-200 rounded-tl-xs'
                      }`}
                    >
                      {/* Message Content */}
                      <div className="whitespace-pre-line leading-relaxed">
                        {msg.text}
                      </div>

                      {/* Meta Footer */}
                      <div
                        className={`flex items-center justify-between gap-3 text-[10px] mt-1.5 pt-1 border-t ${
                          isUser
                            ? 'border-emerald-500/50 text-emerald-100'
                            : 'border-slate-100 text-slate-400'
                        }`}
                      >
                        <span>
                          {msg.intent && (
                            <span className="font-semibold tracking-wider mr-1">
                              [{msg.intent}]
                            </span>
                          )}
                          {msg.timestamp}
                        </span>
                        {isUser && <span>✓✓</span>}
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>

            {/* Quick Prompt Pill Strip */}
            <div className="bg-slate-50 border-t border-slate-200 px-3 py-2 overflow-x-auto flex gap-2 no-scrollbar">
              {DEMO_ACTIONS.map((action, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(action.label)}
                  disabled={isSending}
                  className={`text-xs px-2.5 py-1 rounded-full border whitespace-nowrap transition-colors flex items-center gap-1.5 font-medium ${action.color}`}
                  title={action.desc}
                >
                  <span>{action.label}</span>
                  <span className="text-[10px] opacity-75">({action.lang})</span>
                </button>
              ))}
            </div>

            {/* Input Form Bar */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="p-3 bg-white border-t border-slate-200 flex items-center gap-2"
            >
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Type command in English, Kannada, or Hindi (e.g. 'Backpack price 2500 maadu')..."
                className="flex-1 px-3.5 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all text-slate-800 placeholder-slate-400"
                disabled={isSending}
              />
              <button
                type="submit"
                disabled={isSending || !inputText.trim()}
                className="p-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-xl shadow-xs transition-colors"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Telemetry & Webhook Inspection */}
        <div className="lg:col-span-5 space-y-4">
          {/* Active Expiring Confirmations Card */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-purple-600" />
                <h3 className="font-semibold text-xs text-slate-900 uppercase tracking-wider">
                  Active Pending Tokens (15-Min TTL)
                </h3>
              </div>
              <span className="text-xs bg-purple-100 text-purple-700 font-semibold px-2 py-0.5 rounded-full">
                {diagnostics?.active_confirmations?.length ?? 0} Active
              </span>
            </div>

            <div className="p-4 divide-y divide-slate-100">
              {diagnostics?.active_confirmations?.length > 0 ? (
                diagnostics.active_confirmations.map((conf: any) => (
                  <div key={conf.id} className="py-2.5 first:pt-0 last:pb-0 space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-mono font-bold bg-purple-50 text-purple-700 px-2 py-0.5 rounded border border-purple-200">
                        CONFIRM {conf.code}
                      </span>
                      <span className="text-[11px] text-slate-400">
                        Expires: {new Date(conf.expires_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="text-xs text-slate-800 font-medium">
                      {conf.product_name || conf.operation_type}
                    </div>
                    <div className="text-xs text-slate-500 font-mono">
                      Proposed: {JSON.stringify(conf.proposed_values)}
                    </div>
                  </div>
                ))
              ) : (
                <div className="py-6 text-center text-xs text-slate-400">
                  No pending authorizations active. High-risk price modifications require short code confirmation before applying.
                </div>
              )}
            </div>
          </div>

          {/* Webhook Endpoints & Verification Settings */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-900 uppercase tracking-wider">
              <Key className="w-4 h-4 text-blue-600" />
              Meta Cloud API Configuration
            </div>

            <div className="space-y-2 text-xs">
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 space-y-1">
                <span className="text-slate-500 font-medium block">Webhook Callback URL (for Meta Dashboard)</span>
                <div className="flex items-center justify-between font-mono text-[11px] text-slate-800 bg-white p-1.5 rounded border border-slate-200">
                  <span className="truncate">https://your-domain.ngrok-free.app/webhook/whatsapp</span>
                  <button
                    onClick={() => copyToClipboard('https://your-domain.ngrok-free.app/webhook/whatsapp', 'webhook')}
                    className="text-slate-400 hover:text-slate-700 ml-2"
                  >
                    {copiedKey === 'webhook' ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>

              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 space-y-1">
                <span className="text-slate-500 font-medium block">Verify Token (hub.verify_token)</span>
                <div className="flex items-center justify-between font-mono text-[11px] text-slate-800 bg-white p-1.5 rounded border border-slate-200">
                  <span>{diagnostics?.configuration?.verify_token_configured ? 'vastram_growth_agent_verify_2026' : 'Not set'}</span>
                  <button
                    onClick={() => copyToClipboard('vastram_growth_agent_verify_2026', 'verify')}
                    className="text-slate-400 hover:text-slate-700 ml-2"
                  >
                    {copiedKey === 'verify' ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Recent Inbound Audit Ledger */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Globe className="w-4 h-4 text-emerald-600" />
                <h3 className="font-semibold text-xs text-slate-900 uppercase tracking-wider">
                  Recent Inbound Webhook Ledger
                </h3>
              </div>
            </div>

            <div className="p-3 divide-y divide-slate-100 max-h-56 overflow-y-auto">
              {diagnostics?.recent_inbound?.length > 0 ? (
                diagnostics.recent_inbound.map((item: any) => (
                  <div key={item.id} className="py-2 text-xs space-y-0.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[11px] text-slate-500 truncate max-w-[180px]">
                        {item.message_id}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700">
                        {item.status}
                      </span>
                    </div>
                    <div className="text-slate-800 font-medium line-clamp-1">
                      {item.text || 'Status Update / Interactive'}
                    </div>
                  </div>
                ))
              ) : (
                <div className="py-4 text-center text-xs text-slate-400">
                  No inbound webhooks recorded yet.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
