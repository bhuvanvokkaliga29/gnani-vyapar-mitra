'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Volume2,
  RefreshCw,
  Sparkles,
  Send,
  RotateCcw,
  Square,
  Globe,
  Radio,
  CheckCircle2,
  AlertCircle,
  Clock,
  Layers,
  ChevronRight,
  TrendingUp,
  Package,
  Activity,
  Play,
  Pause,
  Bot,
  Phone,
  Copy,
  Check,
  ExternalLink,
  X,
  Database,
  Key,
  HelpCircle,
  PhoneCall
} from 'lucide-react';
import { api, API_BASE } from '@/lib/api';
import { useMerchant } from '@/lib/MerchantContext';

// Clean monochrome quick prompts
const QUICK_PROMPTS = [
  { label: "Today's sales?", query: 'How much revenue did my shop generate today?', lang: 'en' },
  { label: 'Top product?', query: 'Which product contributed the most to today\'s sales?', lang: 'en' },
  { label: 'Remaining stock?', query: 'How much stock is remaining in that product?', lang: 'en' },
  { label: 'Should I reorder?', query: 'Should I reorder it right now?', lang: 'en' },
  { label: 'Profit margin?', query: 'What about its profit margin?', lang: 'en' },
  { label: 'ಇವತ್ತಿನ ಮಾರಾಟ ಎಷ್ಟು?', query: 'ಇವತ್ತಿನ ಸೇಲ್ಸ್ ಎಷ್ಟಾಗಿದೆ?', lang: 'kn' },
  { label: 'ಆ ಪ್ರಾಡಕ್ಟ್ ಸ್ಟಾಕ್ ಎಷ್ಟಿದೆ?', query: 'ಆ ಪ್ರಾಡಕ್ಟ್ ಸ್ಟಾಕ್ ಎಷ್ಟಿದೆ?', lang: 'kn' },
  { label: 'दुकान की बिक्री कैसी है?', query: 'आज की दुकान की बिक्री कैसी है?', lang: 'hi' }
];

type VoiceState = 'READY' | 'LISTENING' | 'PROCESSING' | 'THINKING' | 'SPEAKING' | 'INTERRUPTED' | 'ERROR';

interface MessageTurn {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  spoken_content?: string;
  timestamp: string;
  audio_base64?: string;
  tools_used?: string[];
  focused_entity?: any;
  latency_metrics?: {
    reasoning_seconds?: number;
    tts_ttfb_seconds?: number;
    tts_total_seconds?: number;
    total_latency_seconds?: number;
  };
}

// Clean formatted message renderer for transcripts (No raw markdown syntax)
function FormattedTranscriptContent({ content, isUser = false }: { content: string; isUser?: boolean }) {
  if (!content) return null;

  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let tableRows: string[][] = [];
  let inTable = false;

  const flushTable = (keyPrefix: string) => {
    if (tableRows.length === 0) return;
    const headerRow = tableRows[0];
    const dataRows = tableRows.slice(1);

    elements.push(
      <div key={`table-${keyPrefix}`} className={`my-2.5 overflow-x-auto rounded-lg border ${isUser ? 'border-neutral-300 bg-neutral-100' : 'border-neutral-800 bg-neutral-950/80'}`}>
        <table className="w-full text-left text-[11px] font-mono border-collapse">
          <thead>
            <tr className={`${isUser ? 'bg-neutral-200 border-b border-neutral-300 text-neutral-900' : 'bg-neutral-900 border-b border-neutral-800 text-neutral-300'}`}>
              {headerRow.map((cell, cIdx) => (
                <th key={cIdx} className={`py-2 px-3 font-semibold ${isUser ? 'text-black' : 'text-neutral-200'}`}>
                  {cell.trim()}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {dataRows.map((row, rIdx) => (
              <tr key={rIdx} className={`border-b ${isUser ? 'border-neutral-200 hover:bg-neutral-200/50' : 'border-neutral-900/70 hover:bg-neutral-900/50'}`}>
                {row.map((cell, cIdx) => {
                  const val = cell.trim();
                  const isNum = /^₹?[0-9,]+(?:\.[0-9]+)?%?$/.test(val);
                  return (
                    <td key={cIdx} className={`py-2 px-3 ${isUser ? (isNum ? 'text-right font-semibold text-black' : 'text-neutral-900') : (isNum ? 'text-right font-medium text-white' : 'text-neutral-300')}`}>
                      {val}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    tableRows = [];
    inTable = false;
  };

  const renderInline = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, pIdx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={pIdx} className={`font-semibold ${isUser ? 'text-black' : 'text-white'}`}>{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      if (/^\|(?:\s*[:-]+[-| :]*)\|$/.test(trimmed)) {
        continue;
      }
      const cells = trimmed.slice(1, -1).split('|').map((c) => c.trim());
      tableRows.push(cells);
      inTable = true;
      continue;
    } else if (inTable) {
      flushTable(`row-${i}`);
    }

    if (!trimmed) {
      continue;
    }

    if (trimmed.startsWith('#')) {
      const headingText = trimmed.replace(/^#+\s*/, '');
      elements.push(
        <h4 key={`h-${i}`} className={`text-xs font-bold uppercase tracking-wider mt-3 mb-1.5 flex items-center gap-1.5 ${isUser ? 'text-black' : 'text-white'}`}>
          <span className={`w-1.5 h-3 rounded-full inline-block ${isUser ? 'bg-black' : 'bg-white'}`} />
          {renderInline(headingText)}
        </h4>
      );
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const bulletText = trimmed.replace(/^[-*]\s+/, '');
      elements.push(
        <div key={`bullet-${i}`} className={`flex items-start gap-2 my-1 pl-1 text-[11px] leading-relaxed ${isUser ? 'text-neutral-900' : 'text-neutral-300'}`}>
          <span className={`mt-1 text-[8px] ${isUser ? 'text-neutral-600' : 'text-neutral-500'}`}>•</span>
          <span>{renderInline(bulletText)}</span>
        </div>
      );
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const numMatch = trimmed.match(/^(\d+)\.\s+(.*)$/);
      if (numMatch) {
        elements.push(
          <div key={`num-${i}`} className={`flex items-start gap-2 my-1 pl-1 text-[11px] leading-relaxed ${isUser ? 'text-neutral-900' : 'text-neutral-300'}`}>
            <span className={`font-mono text-[10px] w-4 shrink-0 ${isUser ? 'text-neutral-700' : 'text-neutral-400'}`}>{numMatch[1]}.</span>
            <span>{renderInline(numMatch[2])}</span>
          </div>
        );
        continue;
      }
    }

    elements.push(
      <p key={`p-${i}`} className={`text-[11px] leading-relaxed my-1 ${isUser ? 'text-neutral-950 font-medium' : 'text-neutral-300'}`}>
        {renderInline(trimmed)}
      </p>
    );
  }

  if (inTable) {
    flushTable('end');
  }

  return <div className="space-y-0.5">{elements}</div>;
}

export default function VoiceAgentPage() {
  const { currentMerchant } = useMerchant();

  // Voice Interaction States
  const [voiceState, setVoiceState] = useState<VoiceState>('READY');
  const [isContinuous, setIsContinuous] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState<'kn' | 'hi' | 'en' | 'ta' | 'ml' | 'te'>('kn');
  const [audioLevel, setAudioLevel] = useState(0);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageTurn[]>([]);
  const [inputText, setTextInput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [focusedProduct, setFocusedProduct] = useState<{ name: string; sku: string } | null>(null);
  const [pendingAutoplayAudio, setPendingAutoplayAudio] = useState<string | null>(null);

  // Gnani Agent Builder Modal & Actions State
  const [isAgentModalOpen, setIsAgentModalOpen] = useState(false);
  const [agentStatusData, setAgentStatusData] = useState<any>(null);
  const [isLoadingAgentStatus, setIsLoadingAgentStatus] = useState(false);
  const [syncStatus, setSyncStatus] = useState<{ loading: boolean; result?: any; error?: string } | null>(null);
  const [callPhone, setCallPhone] = useState('+91');
  const [callStatus, setCallStatus] = useState<{ loading: boolean; result?: any; error?: string } | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Audio Playback
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const currentAudioSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const outputGainNodeRef = useRef<GainNode | null>(null);
  const speakingStartTimeRef = useRef<number | null>(null);

  // Hardware Audio & VAD Refs
  const isContinuousRef = useRef(false);
  const voiceStateRef = useRef<VoiceState>('READY');
  const activeRequestIdRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentSessionIdRef = useRef<string | null>(null);

  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const pcmWorkerNodeRef = useRef<ScriptProcessorNode | null>(null);
  const pcmSampleChunksRef = useRef<Float32Array[]>([]);
  const speechStartRef = useRef<number | null>(null);
  const silenceStartRef = useRef<number | null>(null);
  const bargeInStartRef = useRef<number | null>(null);
  const vadAnimationRef = useRef<number | null>(null);

  // Independent Contained Transcript Scroll Ref (NO window scrolling!)
  const transcriptContainerRef = useRef<HTMLDivElement | null>(null);
  const isUserScrolledUpRef = useRef(false);

  const SPEECH_THRESHOLD = 0.030;
  const MIN_UTTERANCE_MS = 350;
  const BARGE_IN_THRESHOLD = 0.055;

  // Adaptive Silence Endpointing based on utterance duration:
  // - Short speech (< 1.5s): user is forming thought; allow 1,350ms pause before cut-off
  // - Medium speech (1.5s - 3.5s): mid-sentence pause; allow 1,200ms pause
  // - Long speech (> 3.5s): full sentence completed; 950ms pause for responsive finalization
  const getAdaptiveSilenceThreshold = (speechDurationMs: number): number => {
    if (speechDurationMs < 1500) {
      return 1350; // 1.35 seconds for thinking pause (e.g. "Today my sales were... [pause] ...actually...")
    } else if (speechDurationMs < 3500) {
      return 1200; // 1.2 seconds for mid-sentence conversational pause
    } else {
      return 950;  // 0.95 seconds after complete sentence
    }
  };

  useEffect(() => {
    isContinuousRef.current = isContinuous;
  }, [isContinuous]);

  useEffect(() => {
    voiceStateRef.current = voiceState;
  }, [voiceState]);

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  // Contained Auto-Scroll ONLY when message count changes AND user has not scrolled up
  const handleTranscriptScroll = () => {
    if (!transcriptContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = transcriptContainerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    isUserScrolledUpRef.current = distanceFromBottom > 80;
  };

  useEffect(() => {
    if (transcriptContainerRef.current && !isUserScrolledUpRef.current) {
      transcriptContainerRef.current.scrollTo({
        top: transcriptContainerRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [messages.length]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopVoice();
      stopActiveAudioPlayback();
    };
  }, []);

  // Fetch Gnani Agent Status
  const fetchAgentStatus = async () => {
    setIsLoadingAgentStatus(true);
    try {
      const data = await api.getGnaniAgentStatus(currentMerchant.id);
      setAgentStatusData(data);
    } catch (err: any) {
      setAgentStatusData({ error: err.message || 'Failed to load Agent Builder status' });
    } finally {
      setIsLoadingAgentStatus(false);
    }
  };

  const handleSyncKnowledge = async () => {
    setSyncStatus({ loading: true });
    try {
      const res = await api.syncGnaniKnowledge(currentMerchant.id);
      setSyncStatus({ loading: false, result: res });
    } catch (err: any) {
      setSyncStatus({ loading: false, error: err.message || 'Failed to sync knowledge base' });
    }
  };

  const handleTriggerCall = async () => {
    if (!callPhone.trim() || callPhone.trim().length < 8) {
      setCallStatus({ loading: false, error: 'Please enter a valid phone number with country code' });
      return;
    }
    setCallStatus({ loading: true });
    try {
      const res = await api.triggerGnaniTestCall(currentMerchant.id, callPhone.trim());
      setCallStatus({ loading: false, result: res });
    } catch (err: any) {
      setCallStatus({ loading: false, error: err.message || 'Failed to trigger outbound call' });
    }
  };

  const copyToClipboard = (text: string, key: string) => {
    try {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2500);
    } catch (e) {}
  };

  // Unlock AudioContext and HTML5 Audio privileges during user gesture
  const unlockAudioContext = async () => {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
        audioContextRef.current = new AudioCtx();
      }
      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume();
      }

      // Pre-warm HTML5 Audio with 1-sample silent WAV
      if (!audioPlayerRef.current) {
        audioPlayerRef.current = new Audio();
      }
      audioPlayerRef.current.src = 'data:audio/wav;base64,UklGRigAAABXQVZFRm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA';
      audioPlayerRef.current.volume = 0.01;
      await audioPlayerRef.current.play().then(() => {
        audioPlayerRef.current?.pause();
      }).catch(() => {});
    } catch (e) {
      console.warn('AudioContext pre-warm note:', e);
    }
  };

  // Stop any active playing audio source immediately with 0ms mute
  const stopActiveAudioPlayback = (wasInterrupted: boolean = false) => {
    activeRequestIdRef.current++;
    if (outputGainNodeRef.current && audioContextRef.current) {
      try {
        outputGainNodeRef.current.gain.setValueAtTime(0, audioContextRef.current.currentTime);
      } catch (e) {}
    }
    if (currentAudioSourceRef.current) {
      try {
        currentAudioSourceRef.current.stop(0);
        currentAudioSourceRef.current.disconnect();
      } catch (e) {}
      currentAudioSourceRef.current = null;
    }
    if (audioPlayerRef.current) {
      try {
        audioPlayerRef.current.pause();
        audioPlayerRef.current.currentTime = 0;
      } catch (e) {}
    }
    setIsPlayingAudio(false);

    if (wasInterrupted) {
      const sessId = currentSessionIdRef.current || currentSessionId;
      if (sessId) {
        api.interruptDoctorSession(currentMerchant.id, sessId).catch(() => {});
      }
    }
  };

  // Ultra-reliable Web Audio API + HTML5 Audio Vocalization
  const playAudioBase64 = async (base64Audio: string) => {
    if (!base64Audio) return;
    setPendingAutoplayAudio(null);
    stopActiveAudioPlayback();

    // 1. Sanitize base64 string: strip any data URL prefix and whitespace!
    const rawB64 = base64Audio.includes(',') ? base64Audio.split(',')[1] : base64Audio;
    const cleanB64 = rawB64.replace(/[^A-Za-z0-9+/=]/g, '');

    try {
      const binary = atob(cleanB64);
      const len = binary.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binary.charCodeAt(i);
      }

      // Primary Engine: Web Audio API (Immune to HTMLMediaElement autoplay policy once unlocked)
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      if (!audioContextRef.current || audioContextRef.current.state === 'closed') {
        audioContextRef.current = new AudioCtx();
      }
      if (audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume();
      }

      const audioCtx = audioContextRef.current;
      const bufferCopy = bytes.buffer.slice(0);
      const decodedBuffer = await audioCtx.decodeAudioData(bufferCopy);

      const source = audioCtx.createBufferSource();
      source.buffer = decodedBuffer;

      const gainNode = audioCtx.createGain();
      gainNode.gain.setValueAtTime(1.0, audioCtx.currentTime);
      source.connect(gainNode);
      gainNode.connect(audioCtx.destination);
      outputGainNodeRef.current = gainNode;
      currentAudioSourceRef.current = source;

      speakingStartTimeRef.current = Date.now();
      setIsPlayingAudio(true);
      setVoiceState('SPEAKING');

      source.onended = () => {
        if (currentAudioSourceRef.current === source) {
          currentAudioSourceRef.current = null;
        }
        setIsPlayingAudio(false);
        // Automatic return to listening for hands-free continuous dialogue
        if (isContinuousRef.current) {
          speechStartRef.current = null;
          silenceStartRef.current = null;
          pcmSampleChunksRef.current = [];
          setTimeout(() => {
            if (isContinuousRef.current && voiceStateRef.current !== 'PROCESSING' && voiceStateRef.current !== 'THINKING') {
              setVoiceState('LISTENING');
            }
          }, 350);
        } else {
          setVoiceState('READY');
        }
      };

      source.start(0);
      return;
    } catch (webAudioErr) {
      console.warn('WebAudio playback fallback to HTML5 Audio:', webAudioErr);
    }

    // Secondary Engine: HTML5 Audio Fallback
    try {
      const player = audioPlayerRef.current || new Audio();
      audioPlayerRef.current = player;
      player.src = base64Audio.startsWith('data:') ? base64Audio : `data:audio/wav;base64,${cleanB64}`;
      player.volume = 1.0;

      speakingStartTimeRef.current = Date.now();
      setIsPlayingAudio(true);
      setVoiceState('SPEAKING');

      player.onended = () => {
        setIsPlayingAudio(false);
        if (isContinuousRef.current) {
          speechStartRef.current = null;
          silenceStartRef.current = null;
          pcmSampleChunksRef.current = [];
          setTimeout(() => {
            if (isContinuousRef.current && voiceStateRef.current !== 'PROCESSING' && voiceStateRef.current !== 'THINKING') {
              setVoiceState('LISTENING');
            }
          }, 350);
        } else {
          setVoiceState('READY');
        }
      };

      await player.play();
    } catch (err: any) {
      console.warn('Autoplay deferred by browser policy:', err);
      setPendingAutoplayAudio(base64Audio);
      setIsPlayingAudio(false);
      setVoiceState(isContinuousRef.current ? 'LISTENING' : 'READY');
    }
  };

  const startVoice = async (continuous: boolean = false) => {
    await unlockAudioContext();
    setError(null);
    setIsContinuous(continuous);
    isContinuousRef.current = continuous;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      streamRef.current = stream;

      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      const audioCtx = audioContextRef.current || new AudioCtx();
      audioContextRef.current = audioCtx;
      if (audioCtx.state === 'suspended') {
        await audioCtx.resume();
      }

      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.3;
      analyserRef.current = analyser;
      source.connect(analyser);

      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        if (speechStartRef.current !== null) {
          pcmSampleChunksRef.current.push(new Float32Array(inputData));
        }
      };

      source.connect(processor);

      // Connect through a silent GainNode to prevent mic loopback into speakers!
      const muteGain = audioCtx.createGain();
      muteGain.gain.value = 0;
      processor.connect(muteGain);
      muteGain.connect(audioCtx.destination);
      pcmWorkerNodeRef.current = processor;

      setVoiceState('LISTENING');
      speechStartRef.current = null;
      silenceStartRef.current = null;
      bargeInStartRef.current = null;

      runVADLoop();
    } catch (err: any) {
      setError(`Microphone access required: ${err.message || 'Permission denied'}`);
      setVoiceState('READY');
      setIsContinuous(false);
    }
  };

  const stopVoice = () => {
    setIsContinuous(false);
    isContinuousRef.current = false;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    if (vadAnimationRef.current) {
      cancelAnimationFrame(vadAnimationRef.current);
      vadAnimationRef.current = null;
    }

    stopActiveAudioPlayback();

    if (pcmWorkerNodeRef.current) {
      try {
        pcmWorkerNodeRef.current.disconnect();
      } catch (e) {}
      pcmWorkerNodeRef.current = null;
    }
    pcmSampleChunksRef.current = [];

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }

    setVoiceState('READY');
    setAudioLevel(0);
  };

  const runVADLoop = () => {
    if (!analyserRef.current || !streamRef.current) return;

    const dataArray = new Uint8Array(analyserRef.current.fftSize);
    analyserRef.current.getByteTimeDomainData(dataArray);

    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      const v = (dataArray[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / dataArray.length);
    setAudioLevel(rms);

    const now = Date.now();
    const currentState = voiceStateRef.current;

    // Barge-in interruption during SPEAKING
    if (currentState === 'SPEAKING') {
      const speechElapsed = now - (speakingStartTimeRef.current || 0);
      // Natural conversational threshold: 300ms speech clearance + 0.055 RMS
      if (speechElapsed > 300 && rms >= BARGE_IN_THRESHOLD) {
        if (bargeInStartRef.current === null) {
          bargeInStartRef.current = now;
        } else if (now - bargeInStartRef.current >= 120) {
          bargeInStartRef.current = null;
          stopActiveAudioPlayback(true);
          setVoiceState('LISTENING');
          voiceStateRef.current = 'LISTENING';
          speechStartRef.current = now;
          silenceStartRef.current = null;
          pcmSampleChunksRef.current = [];
        }
      } else {
        bargeInStartRef.current = null;
      }
    }

    // Speech start and pause detection in LISTENING state
    if (currentState === 'LISTENING') {
      if (rms >= SPEECH_THRESHOLD) {
        if (speechStartRef.current === null) {
          speechStartRef.current = now;
          pcmSampleChunksRef.current = [];
        }
        silenceStartRef.current = null;
      } else if (speechStartRef.current !== null) {
        if (silenceStartRef.current === null) {
          silenceStartRef.current = now;
        } else {
          const duration = silenceStartRef.current - speechStartRef.current;
          const adaptiveSilenceLimit = getAdaptiveSilenceThreshold(duration);
          if (now - silenceStartRef.current >= adaptiveSilenceLimit) {
            speechStartRef.current = null;
            silenceStartRef.current = null;

            if (duration >= MIN_UTTERANCE_MS && pcmSampleChunksRef.current.length > 0) {
              const sampleRate = audioContextRef.current?.sampleRate || 44100;
              const wavBlob = encodePcmToWav([...pcmSampleChunksRef.current], sampleRate);
              pcmSampleChunksRef.current = [];
              handleProcessAudio(wavBlob);
            } else {
              pcmSampleChunksRef.current = [];
            }
          }
        }
      }
    }

    vadAnimationRef.current = requestAnimationFrame(runVADLoop);
  };

  const encodePcmToWav = (chunks: Float32Array[], inputSampleRate: number): Blob => {
    let totalLen = 0;
    for (const chunk of chunks) totalLen += chunk.length;
    const flat = new Float32Array(totalLen);
    let offset = 0;
    for (const chunk of chunks) {
      flat.set(chunk, offset);
      offset += chunk.length;
    }

    const targetRate = 16000;
    const ratio = inputSampleRate / targetRate;
    const newLen = Math.round(flat.length / ratio);
    const downsampled = new Float32Array(newLen);
    for (let i = 0; i < newLen; i++) {
      downsampled[i] = flat[Math.min(Math.round(i * ratio), flat.length - 1)];
    }

    const numSamples = downsampled.length;
    const buffer = new ArrayBuffer(44 + numSamples * 2);
    const view = new DataView(buffer);

    const writeStr = (off: number, s: string) => {
      for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
    };

    writeStr(0, 'RIFF');
    view.setUint32(4, 36 + numSamples * 2, true);
    writeStr(8, 'WAVE');
    writeStr(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, targetRate, true);
    view.setUint32(28, targetRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeStr(36, 'data');
    view.setUint32(40, numSamples * 2, true);

    let bOff = 44;
    for (let i = 0; i < numSamples; i++) {
      const s = Math.max(-1, Math.min(1, downsampled[i]));
      view.setInt16(bOff, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      bOff += 2;
    }

    return new Blob([buffer], { type: 'audio/wav' });
  };

  const handleProcessAudio = async (audioBlob: Blob) => {
    const reqId = ++activeRequestIdRef.current;
    setVoiceState('PROCESSING');

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      // 1. Transcribe via Gnani Prisma v3.0
      const sttRes = await api.transcribeVoice(audioBlob, 'indic-auto', 'codemix');
      if (reqId !== activeRequestIdRef.current || abortController.signal.aborted) return;

      const userText = (sttRes.transcript || '').trim();
      if (!userText) {
        setVoiceState(isContinuousRef.current ? 'LISTENING' : 'READY');
        return;
      }

      // Dynamic Turn-by-Turn Multilingual Mirroring:
      // Extract the language detected by Gnani Prisma STT (e.g. 'kn', 'ta', 'ml', 'te', 'hi', 'en')
      const detectedLang = sttRes.detected_language_code?.split('-')[0] || selectedLanguage;
      if (['kn', 'hi', 'en', 'ta', 'ml', 'te', 'mr', 'gu', 'bn', 'ur'].includes(detectedLang)) {
        setSelectedLanguage(detectedLang as any);
      }

      // Execute assistant turn in the exact language the user is speaking!
      await executeAssistantTurn(userText, detectedLang, reqId);
    } catch (err: any) {
      if (reqId === activeRequestIdRef.current) {
        setError(`Transcription error: ${err.message || err}`);
        setVoiceState(isContinuousRef.current ? 'LISTENING' : 'READY');
      }
    }
  };

  const handleSendText = async () => {
    const q = inputText.trim();
    if (!q) return;
    await unlockAudioContext();
    setTextInput('');
    const reqId = ++activeRequestIdRef.current;
    await executeAssistantTurn(q, selectedLanguage, reqId);
  };

  const handleQuickPrompt = async (queryText: string, lang: string) => {
    await unlockAudioContext();
    const reqId = ++activeRequestIdRef.current;
    setSelectedLanguage(lang as any);
    await executeAssistantTurn(queryText, lang, reqId);
  };

  const executeAssistantTurn = async (queryText: string, lang: string, reqId: number) => {
    setVoiceState('THINKING');
    setError(null);

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userTurn: MessageTurn = {
      id: `usr_${Date.now()}`,
      role: 'user',
      content: queryText,
      timestamp: timeStr
    };
    setMessages((prev) => [...prev, userTurn]);

    try {
      // Build conversation history payload preserving full dialogue context
      const historyPayload = [...messages, userTurn].map((m) => ({
        role: m.role,
        content: m.spoken_content || m.content
      }));

      // Direct call to Doctor/Voice reasoning engine with full Timbre synthesis
      const response = await api.queryVoiceAgent({
        merchant_id: currentMerchant.id,
        query: queryText,
        session_id: currentSessionIdRef.current || currentSessionId || undefined,
        conversation_history: historyPayload,
        preferred_language: lang,
        synthesize_audio: true
      });

      if (reqId !== activeRequestIdRef.current) return;

      if (response.session_id) {
        setCurrentSessionId(response.session_id);
        currentSessionIdRef.current = response.session_id;
      }

      if (response.focused_entity && response.focused_entity.sku) {
        setFocusedProduct({
          name: response.focused_entity.name || 'Focused Product',
          sku: response.focused_entity.sku
        });
      } else if (!response.focused_entity) {
        setFocusedProduct(null);
      }

      // Sanitize any internal model naming or system metadata headers from visible transcript
      let cleanDetailed = (response.detailed_advice || response.spoken_text || '')
        .replace(/^(?:[*_#]*\s*(?:DETAILED[_\s]*(?:BOX|ADVICE|REPORT)|SPOKEN[_\s]*REPLY|LANGUAGE\s*PREFERENCE(?:\s*UPDATE)?)\s*[:*_-]*\s*)+/gim, '')
        .replace(/Gemini\s*(Flash|Reasoning|2\.5|3\.1|3\.5)?/gi, 'AI Business Advisor')
        .replace(/OpenRouter/gi, 'AI Engine');

      const assistantTurn: MessageTurn = {
        id: `ast_${Date.now()}`,
        role: 'assistant',
        content: cleanDetailed,
        spoken_content: response.spoken_text,
        timestamp: timeStr,
        audio_base64: response.audio?.audio_base64,
        tools_used: response.trace
          ? response.trace.filter((s: string) => s.startsWith('tool_executed:')).map((s: string) => s.replace('tool_executed:', ''))
          : [],
        focused_entity: response.focused_entity,
        latency_metrics: response.latency_metrics
      };

      if (response.intent === 'NEW_SESSION') {
        setMessages([userTurn, assistantTurn]);
      } else {
        setMessages((prev) => [...prev, assistantTurn]);
      }

      // Automatic audio vocalization via Gnani Timbre
      if (response.audio && response.audio.audio_base64) {
        await playAudioBase64(response.audio.audio_base64);
      } else {
        setVoiceState(isContinuousRef.current ? 'LISTENING' : 'READY');
      }
    } catch (err: any) {
      if (reqId === activeRequestIdRef.current) {
        setError(`Assistant error: ${err.message || err}`);
        setVoiceState(isContinuousRef.current ? 'LISTENING' : 'READY');
      }
    }
  };

  const handleNewSession = () => {
    stopVoice();
    setCurrentSessionId(null);
    setMessages([]);
    setFocusedProduct(null);
    setError(null);
    setPendingAutoplayAudio(null);
  };

  // Status Orb Visual Styles (Strict Black & White Minimalist)
  const getOrbVisuals = () => {
    switch (voiceState) {
      case 'LISTENING':
        return 'bg-white text-black scale-105 shadow-[0_0_40px_rgba(255,255,255,0.4)] animate-pulse';
      case 'PROCESSING':
        return 'bg-neutral-800 text-white animate-spin border-2 border-dashed border-white';
      case 'THINKING':
        return 'bg-neutral-900 text-white border border-neutral-600 animate-pulse';
      case 'SPEAKING':
        return 'bg-white text-black scale-105 shadow-[0_0_50px_rgba(255,255,255,0.6)]';
      case 'INTERRUPTED':
        return 'bg-neutral-800 text-white border-2 border-white scale-95';
      default:
        return 'bg-black text-white border border-neutral-800 hover:border-neutral-500 hover:scale-102';
    }
  };

  const getStatusText = () => {
    switch (voiceState) {
      case 'LISTENING':
        return isContinuous ? 'Listening continuously • Speak naturally' : 'Listening • Speak your question';
      case 'PROCESSING':
        return 'Transcribing speech via Gnani Prisma v3.0...';
      case 'THINKING':
        return 'Analyzing live Vastram store metrics...';
      case 'SPEAKING':
        return 'Gnani Timbre Speaking • Tap to interrupt';
      case 'INTERRUPTED':
        return 'Playback stopped • Ready for next question';
      case 'ERROR':
        return 'Audio or network issue • Click to retry';
      default:
        return 'Ready • Tap microphone or choose a question below';
    }
  };

  return (
    <div className="w-full h-full max-h-full flex flex-col overflow-hidden bg-black text-white font-sans select-none antialiased">
      {/* =================================================================== */}
      {/* 1. HACKATHON & GNANI AI MONOCHROME IDENTITY BANNER                  */}
      {/* =================================================================== */}
      <header className="w-full border-b border-neutral-800 bg-black/95 backdrop-blur-md px-4 sm:px-6 py-2.5 flex flex-col md:flex-row items-start md:items-center justify-between gap-2 shrink-0 z-20">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-white text-black flex items-center justify-center font-black text-xs tracking-wider">
            GN
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono tracking-widest uppercase bg-neutral-900 text-neutral-300 border border-neutral-700 px-2 py-0.5 rounded">
                Great Indian AI Internship Challenge 2026
              </span>
              <span className="text-[10px] font-mono text-neutral-400">
                Powered by <strong className="text-white">Gnani AI</strong>
              </span>
            </div>
            <h1 className="text-xs sm:text-sm font-bold tracking-tight text-white mt-0.5">
              Vyapar Mitra Voice Agent • Har Dukaan Ka Apna Mitra
            </h1>
          </div>
        </div>

        {/* Integration Status Badges & Language Selector */}
        <div className="flex items-center gap-2 flex-wrap self-end md:self-auto">
          {/* Engine Badges */}
          <div className="hidden lg:flex items-center gap-1.5 text-[10px] font-mono text-neutral-400 border border-neutral-800 rounded-lg px-2.5 py-1 bg-neutral-950">
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
            <span>Prisma STT v3.0</span>
            <span className="text-neutral-700">•</span>
            <span>Timbre TTS v3.0</span>
            <span className="text-neutral-700">•</span>
            <span title="Bot ID: 7bd15e5ff5a7411db02665f468d3353a">Agent Builder</span>
            <span className="text-neutral-700">•</span>
            <span>Vastram BI</span>
          </div>

          {/* Gnani Cloud Agent Modal Trigger */}
          <button
            onClick={() => {
              setIsAgentModalOpen(true);
              fetchAgentStatus();
            }}
            className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono border border-neutral-700 rounded-lg bg-neutral-900 hover:bg-neutral-800 text-neutral-200 transition-colors cursor-pointer"
            title="Gnani Agent Builder Settings, Custom Actions & Outbound Voice"
          >
            <Bot className="w-3.5 h-3.5 text-white" />
            <span className="hidden sm:inline">Gnani Agent</span>
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
          </button>

          {/* Multilingual Selector */}
          <div className="flex items-center bg-neutral-900 border border-neutral-700 rounded-lg p-0.5 text-xs font-semibold overflow-x-auto">
            <button
              onClick={() => setSelectedLanguage('kn')}
              className={`px-2 py-1 rounded transition-colors cursor-pointer ${
                selectedLanguage === 'kn' ? 'bg-white text-black font-bold' : 'text-neutral-400 hover:text-white'
              }`}
            >
              ಕನ್ನಡ
            </button>
            <button
              onClick={() => setSelectedLanguage('en')}
              className={`px-2 py-1 rounded transition-colors cursor-pointer ${
                selectedLanguage === 'en' ? 'bg-white text-black font-bold' : 'text-neutral-400 hover:text-white'
              }`}
            >
              English
            </button>
            <button
              onClick={() => setSelectedLanguage('hi')}
              className={`px-2 py-1 rounded transition-colors cursor-pointer ${
                selectedLanguage === 'hi' ? 'bg-white text-black font-bold' : 'text-neutral-400 hover:text-white'
              }`}
            >
              हिंदी
            </button>
            <button
              onClick={() => setSelectedLanguage('ta')}
              className={`px-2 py-1 rounded transition-colors cursor-pointer ${
                selectedLanguage === 'ta' ? 'bg-white text-black font-bold' : 'text-neutral-400 hover:text-white'
              }`}
            >
              தமிழ்
            </button>
            <button
              onClick={() => setSelectedLanguage('ml')}
              className={`px-2 py-1 rounded transition-colors cursor-pointer ${
                selectedLanguage === 'ml' ? 'bg-white text-black font-bold' : 'text-neutral-400 hover:text-white'
              }`}
            >
              മലയാളം
            </button>
            <button
              onClick={() => setSelectedLanguage('te')}
              className={`px-2 py-1 rounded transition-colors cursor-pointer ${
                selectedLanguage === 'te' ? 'bg-white text-black font-bold' : 'text-neutral-400 hover:text-white'
              }`}
            >
              తెలుగు
            </button>
          </div>

          {/* New Session Button */}
          <button
            onClick={handleNewSession}
            title="Reset Voice Session Memory"
            className="p-1.5 border border-neutral-700 rounded-lg bg-neutral-900 hover:bg-neutral-800 text-neutral-300 hover:text-white transition-colors cursor-pointer"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Autoplay Fallback Banner (if browser blocked initial audio) */}
      {pendingAutoplayAudio && (
        <div className="bg-neutral-900 border-b border-white px-4 py-2 flex items-center justify-between text-xs animate-fade-in shrink-0 z-20">
          <div className="flex items-center gap-2">
            <Volume2 className="w-4 h-4 text-white animate-bounce" />
            <span>Spoken response ready from Gnani Timbre. Click to listen.</span>
          </div>
          <button
            onClick={() => playAudioBase64(pendingAutoplayAudio)}
            className="px-3 py-1 bg-white text-black font-bold rounded text-xs hover:bg-neutral-200 cursor-pointer"
          >
            ▶ Play Spoken Response
          </button>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="bg-neutral-950 border-b border-neutral-700 px-4 py-2 flex items-center justify-between text-xs text-neutral-300 shrink-0 z-20">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-white" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-white font-bold ml-2 cursor-pointer">✕</button>
        </div>
      )}

      {/* =================================================================== */}
      {/* 2. FULL-SCREEN TWO-COLUMN COMMAND CENTER                            */}
      {/* Left: Interactive Voice Stage | Right: Contained Living Transcript   */}
      {/* =================================================================== */}
      <div className="flex-1 w-full grid grid-cols-1 lg:grid-cols-12 min-h-0 overflow-hidden">
        
        {/* LEFT PANEL: Voice Focal Stage (5 columns, contained height) */}
        <div className="lg:col-span-5 border-b lg:border-b-0 lg:border-r border-neutral-800 p-4 sm:p-6 flex flex-col items-center justify-between space-y-4 bg-black relative overflow-y-auto">
          
          {/* Focused Commercial Product Context */}
          <div className="w-full flex justify-center">
            {focusedProduct ? (
              <div className="inline-flex items-center gap-2 px-3 py-1 bg-neutral-900 border border-neutral-700 rounded-full text-xs text-neutral-200">
                <Package className="w-3.5 h-3.5 text-white" />
                <span>Active Context: <strong>{focusedProduct.name}</strong> ({focusedProduct.sku})</span>
              </div>
            ) : (
              <div className="inline-flex items-center gap-2 px-3 py-1 bg-neutral-950 border border-neutral-800 rounded-full text-[11px] text-neutral-400">
                <Activity className="w-3 h-3 text-neutral-400" />
                <span>Connected to Vastram Retail Database (Bangalore)</span>
              </div>
            )}
          </div>

          {/* MAIN MONOCHROME VOICE ORB (Visual Focal Point) */}
          <div className="relative flex items-center justify-center my-auto py-4">
            
            {/* Acoustic ripple waves when capturing audio */}
            {voiceState === 'LISTENING' && (
              <div
                className="absolute rounded-full border border-white/20 animate-ping pointer-events-none"
                style={{
                  width: `${150 + Math.min(audioLevel * 400, 100)}px`,
                  height: `${150 + Math.min(audioLevel * 400, 100)}px`
                }}
              />
            )}
            {voiceState === 'SPEAKING' && (
              <div className="absolute w-40 h-40 rounded-full border border-white/30 animate-pulse pointer-events-none" />
            )}

            {/* Core Action Button */}
            <button
              onClick={() => {
                if (voiceState === 'READY' || voiceState === 'ERROR') {
                  startVoice(true);
                } else if (voiceState === 'SPEAKING') {
                  stopActiveAudioPlayback(true);
                  setVoiceState('INTERRUPTED');
                  setTimeout(() => {
                    if (isContinuousRef.current) setVoiceState('LISTENING');
                    else setVoiceState('READY');
                  }, 200);
                } else {
                  stopVoice();
                }
              }}
              title={
                voiceState === 'READY'
                  ? 'Start Voice Conversation'
                  : voiceState === 'SPEAKING'
                  ? 'Tap to Interrupt Assistant'
                  : 'Stop Microphone'
              }
              className={`w-28 h-28 sm:w-32 sm:h-32 rounded-full flex flex-col items-center justify-center transition-all duration-300 cursor-pointer shadow-2xl relative z-10 ${getOrbVisuals()}`}
            >
              {voiceState === 'READY' ? (
                <>
                  <Mic className="w-10 h-10 sm:w-12 sm:h-12 stroke-[1.5]" />
                  <span className="text-[10px] font-mono tracking-widest uppercase mt-1">Tap Mic</span>
                </>
              ) : voiceState === 'LISTENING' ? (
                <>
                  <Radio className="w-10 h-10 sm:w-12 sm:h-12 animate-pulse" />
                  <span className="text-[10px] font-mono tracking-widest uppercase mt-1">Listening</span>
                </>
              ) : voiceState === 'PROCESSING' ? (
                <>
                  <RefreshCw className="w-10 h-10 sm:w-12 sm:h-12 animate-spin" />
                  <span className="text-[10px] font-mono tracking-widest uppercase mt-1">Prisma</span>
                </>
              ) : voiceState === 'THINKING' ? (
                <>
                  <Sparkles className="w-10 h-10 sm:w-12 sm:h-12 animate-pulse" />
                  <span className="text-[10px] font-mono tracking-widest uppercase mt-1">Thinking</span>
                </>
              ) : voiceState === 'SPEAKING' ? (
                <>
                  <Volume2 className="w-10 h-10 sm:w-12 sm:h-12 animate-bounce" />
                  <span className="text-[10px] font-mono tracking-widest uppercase mt-1">Interrupt</span>
                </>
              ) : (
                <>
                  <Square className="w-9 h-9 sm:w-10 sm:h-10" />
                  <span className="text-[10px] font-mono tracking-widest uppercase mt-1">Stop</span>
                </>
              )}
            </button>
          </div>

          {/* Current Status Label */}
          <div className="text-center space-y-1">
            <p className="text-xs sm:text-sm font-semibold tracking-wide text-white">
              {getStatusText()}
            </p>
            <p className="text-[11px] text-neutral-400 font-mono">
              Auto speech synthesis via Gnani Timbre • Native 48 kHz
            </p>
          </div>

          {/* Mode Controls: Push-to-Talk vs Continuous Hands-Free */}
          <div className="w-full flex items-center justify-center gap-2.5 pt-1">
            <button
              onClick={() => {
                if (voiceState === 'READY') startVoice(false);
                else stopVoice();
              }}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
                voiceState !== 'READY' && !isContinuous
                  ? 'bg-white text-black border-white'
                  : 'bg-neutral-900 text-neutral-300 border-neutral-700 hover:border-white hover:text-white'
              }`}
            >
              {voiceState !== 'READY' && !isContinuous ? '■ Stop Mic' : '● Push-to-Talk'}
            </button>

            <button
              onClick={() => {
                if (isContinuous) stopVoice();
                else startVoice(true);
              }}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
                isContinuous
                  ? 'bg-white text-black border-white shadow-lg'
                  : 'bg-neutral-900 text-neutral-300 border-neutral-700 hover:border-white hover:text-white'
              }`}
            >
              {isContinuous ? '■ Stop Continuous' : '⚡ Hands-Free Loop'}
            </button>
          </div>

          {/* Suggested Quick Prompt Chips */}
          <div className="w-full pt-3 border-t border-neutral-800 flex flex-wrap items-center justify-center gap-1.5">
            <span className="text-[10px] font-mono text-neutral-400 mr-1 uppercase">
              Quick Inquiries:
            </span>
            {QUICK_PROMPTS.map((qp, idx) => (
              <button
                key={idx}
                onClick={() => handleQuickPrompt(qp.query, qp.lang)}
                disabled={voiceState === 'THINKING' || voiceState === 'PROCESSING'}
                className="px-2.5 py-1 text-[11px] bg-neutral-900 hover:bg-neutral-800 text-neutral-300 hover:text-white rounded border border-neutral-700 transition-colors disabled:opacity-40 cursor-pointer"
              >
                {qp.label}
              </button>
            ))}
          </div>
        </div>

        {/* RIGHT PANEL: Live Dialogue Transcript (7 columns, Strictly Contained Scroll) */}
        <div className="lg:col-span-7 flex flex-col h-full bg-[#0A0A0A] min-h-0 overflow-hidden">
          
          {/* Transcript Sub-header */}
          <div className="border-b border-neutral-800 px-4 sm:px-5 py-2.5 flex items-center justify-between shrink-0 bg-neutral-950">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-white" />
              <h2 className="text-xs font-mono uppercase tracking-wider text-neutral-200">
                Audited Conversation Transcript
              </h2>
            </div>
            <span className="text-[11px] font-mono text-neutral-400">
              {messages.length} {messages.length === 1 ? 'turn' : 'turns'} recorded
            </span>
          </div>

          {/* Living Scrollable Message Area (ONLY this element scrolls; zero window jump!) */}
          <div
            ref={transcriptContainerRef}
            onScroll={handleTranscriptScroll}
            className="flex-1 p-4 sm:p-5 overflow-y-auto space-y-4 min-h-0"
          >
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center text-neutral-400 space-y-3 py-16">
                <div className="w-12 h-12 rounded-full border border-neutral-700 flex items-center justify-center">
                  <Mic className="w-6 h-6 stroke-1 text-neutral-400" />
                </div>
                <div className="space-y-1 max-w-sm">
                  <p className="text-xs font-semibold text-neutral-300">No dialogue recorded in this session yet.</p>
                  <p className="text-[11px] text-neutral-400 leading-relaxed">
                    Click the microphone orb or select a prompt to begin. Vyapar Mitra will automatically speak each answer aloud via Gnani Timbre.
                  </p>
                </div>
              </div>
            ) : (
              messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'} space-y-1.5`}
                >
                  <div className="flex items-center gap-2 text-[10px] font-mono text-neutral-400 px-1">
                    <span className="font-semibold text-neutral-300">{m.role === 'user' ? 'MERCHANT' : 'VYAPAR MITRA'}</span>
                    <span>•</span>
                    <span>{m.timestamp}</span>
                  </div>

                  <div
                    className={`p-3.5 sm:p-4 rounded-xl max-w-xl text-xs leading-relaxed space-y-2.5 ${
                      m.role === 'user'
                        ? 'bg-white text-black font-medium shadow-sm'
                        : 'bg-neutral-900 border border-neutral-700 text-neutral-100'
                    }`}
                  >
                    {/* Natural Spoken Vocalization Block with instant replay */}
                    {m.role === 'assistant' && m.spoken_content && (
                      <div className="p-3 bg-black border border-neutral-700 rounded-lg flex items-start justify-between gap-3">
                        <div className="space-y-0.5">
                          <span className="text-[9px] font-mono uppercase tracking-wider text-neutral-400 block">
                            Gnani Timbre Audio (Spoken Response)
                          </span>
                          <p className="text-xs text-white font-semibold leading-snug">
                            "{m.spoken_content}"
                          </p>
                        </div>
                        {m.audio_base64 && (
                          <button
                            onClick={() => playAudioBase64(m.audio_base64!)}
                            title="Replay Spoken Audio"
                            className="p-1.5 bg-neutral-800 hover:bg-white hover:text-black text-white rounded transition-colors shrink-0 cursor-pointer"
                          >
                            <Volume2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    )}

                    {/* Rich Detailed Advice Content for Assistant, High-Contrast Text for Merchant */}
                    {m.role === 'user' ? (
                      <p className="text-xs sm:text-sm text-neutral-950 font-semibold leading-relaxed whitespace-pre-wrap">
                        {m.content}
                      </p>
                    ) : (
                      <FormattedTranscriptContent content={m.content} isUser={false} />
                    )}

                    {/* Verified Ground Truth Tools Badge */}
                    {m.tools_used && m.tools_used.length > 0 && (
                      <div className="pt-2 border-t border-neutral-800 flex flex-wrap gap-1.5 items-center">
                        <span className="text-[10px] font-mono text-neutral-400">Verified Ground Truth:</span>
                        {m.tools_used.map((t, tIdx) => (
                          <span
                            key={tIdx}
                            className="px-2 py-0.5 rounded bg-neutral-950 border border-neutral-700 text-neutral-300 text-[10px] font-mono"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Monotonic Real-Time Latency Telemetry */}
                    {m.latency_metrics && typeof m.latency_metrics.total_latency_seconds === 'number' && (
                      <div className="pt-1.5 flex flex-wrap gap-2 items-center text-[10px] font-mono text-neutral-400">
                        <span className="px-1.5 py-0.5 rounded bg-neutral-950 border border-neutral-800 text-white font-medium">
                          ⚡ {m.latency_metrics.total_latency_seconds.toFixed(2)}s total
                        </span>
                        {typeof m.latency_metrics.reasoning_seconds === 'number' && m.latency_metrics.reasoning_seconds > 0 && (
                          <span>AI: {m.latency_metrics.reasoning_seconds.toFixed(2)}s</span>
                        )}
                        {typeof m.latency_metrics.tts_ttfb_seconds === 'number' && (
                          <span>Voice TTFB: {m.latency_metrics.tts_ttfb_seconds.toFixed(2)}s</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Quick Chat Input Box (Fallback for noisy environments) */}
          <div className="border-t border-neutral-800 p-3 bg-neutral-950 shrink-0">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendText();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={inputText}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder="Type question or ask in Kannada / Hindi / English..."
                disabled={voiceState === 'THINKING' || voiceState === 'PROCESSING'}
                className="flex-1 bg-neutral-900 border border-neutral-700 rounded-lg px-3.5 py-2 text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-white transition-colors"
              />
              <button
                type="submit"
                disabled={!inputText.trim() || voiceState === 'THINKING' || voiceState === 'PROCESSING'}
                className="px-3.5 py-2 bg-white text-black font-semibold rounded-lg text-xs hover:bg-neutral-200 transition-colors disabled:opacity-40 flex items-center gap-1.5 cursor-pointer"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Send</span>
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* =================================================================== */}
      {/* 3. GNANI AGENT BUILDER CONSOLE & INTEGRATION MODAL                 */}
      {/* =================================================================== */}
      {isAgentModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-3 sm:p-6 overflow-y-auto animate-fade-in">
          <div className="bg-neutral-950 border border-neutral-800 text-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-800 bg-black">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-white text-black flex items-center justify-center">
                  <Bot className="w-4 h-4" />
                </div>
                <div>
                  <h2 className="text-sm font-bold tracking-tight text-white flex items-center gap-2">
                    <span>Gnani AI Agent Builder Console</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-neutral-900 border border-neutral-700 text-neutral-300">
                      Vyapar Mitra Companion
                    </span>
                  </h2>
                  <p className="text-[11px] text-neutral-400 font-mono">
                    Bot ID: 7bd15e5ff5a7411db02665f468d3353a
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsAgentModalOpen(false)}
                className="p-1 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-900 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-5 text-xs">
              
              {/* SECTION A: Status & Connection Diagnostics */}
              <div className="bg-neutral-900/60 border border-neutral-800 rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-neutral-300" />
                    <span className="font-semibold text-white">Platform Health Probe</span>
                  </div>
                  <button
                    onClick={fetchAgentStatus}
                    disabled={isLoadingAgentStatus}
                    className="flex items-center gap-1 px-2.5 py-1 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 rounded text-[11px] font-mono cursor-pointer disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3 h-3 ${isLoadingAgentStatus ? 'animate-spin' : ''}`} />
                    <span>Refresh</span>
                  </button>
                </div>

                {agentStatusData ? (
                  <div className="space-y-2">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-mono">
                      <div className="bg-neutral-950 p-2.5 rounded border border-neutral-800/80">
                        <span className="text-neutral-500 block text-[10px]">AGENT BUILDER STATUS</span>
                        <span className="font-semibold text-white">
                          {agentStatusData.configured ? 'Configured & Active' : 'Not Configured'}
                        </span>
                      </div>
                      <div className="bg-neutral-950 p-2.5 rounded border border-neutral-800/80">
                        <span className="text-neutral-500 block text-[10px]">PLATFORM API KEY SCOPE</span>
                        <span className={agentStatusData.platform_key_valid ? 'text-emerald-400 font-semibold' : 'text-neutral-400'}>
                          {agentStatusData.platform_key_valid ? 'Verified (api.inya.ai)' : 'Speech Key Active / Needs Platform Key'}
                        </span>
                      </div>
                    </div>
                    {agentStatusData.platform_response && (
                      <div className="bg-neutral-950 p-2 rounded border border-neutral-800 text-[10px] font-mono text-neutral-400 overflow-x-auto">
                        Response: {JSON.stringify(agentStatusData.platform_response)}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-neutral-500 font-mono text-[11px]">
                    Click Refresh to test live connection to https://api.inya.ai/platform
                  </div>
                )}
              </div>

              {/* SECTION B: Custom Action Webhook (Vastram Live Store Intelligence) */}
              <div className="bg-neutral-900/60 border border-neutral-800 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-neutral-300" />
                  <span className="font-semibold text-white">Custom Action Webhook (Live Store Intelligence)</span>
                </div>
                <p className="text-neutral-400 text-[11px] leading-relaxed">
                  Configure this webhook URL inside your <strong>Gnani Agent Builder &gt; Custom Actions</strong> dashboard so your hosted agent can execute live database queries for sales, stock, and margins.
                </p>

                <div className="space-y-2">
                  <div>
                    <label className="text-[10px] font-mono text-neutral-500 uppercase block mb-1">Webhook Endpoint URL</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        readOnly
                        value={`${API_BASE}/api/v1/gnani-agent/action`}
                        className="flex-1 bg-neutral-950 border border-neutral-800 rounded px-2.5 py-1.5 font-mono text-[11px] text-neutral-200 select-all"
                      />
                      <button
                        onClick={() => copyToClipboard(`${API_BASE}/api/v1/gnani-agent/action`, 'action_url')}
                        className="px-2.5 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 rounded text-[11px] font-mono flex items-center gap-1 cursor-pointer"
                      >
                        {copiedKey === 'action_url' ? <Check className="w-3.5 h-3.5 text-white" /> : <Copy className="w-3.5 h-3.5" />}
                        <span>{copiedKey === 'action_url' ? 'Copied' : 'Copy'}</span>
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="text-[10px] font-mono text-neutral-500 uppercase block mb-1">Authentication Secret Header</label>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        readOnly
                        value="Header: X-Gnani-Secret (Configured in backend GNANI_WEBHOOK_SECRET)"
                        className="flex-1 bg-neutral-950 border border-neutral-800 rounded px-2.5 py-1.5 font-mono text-[11px] text-neutral-400 select-all"
                      />
                      <button
                        onClick={() => copyToClipboard('X-Gnani-Secret', 'secret')}
                        className="px-2.5 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 rounded text-[11px] font-mono flex items-center gap-1 cursor-pointer"
                        title="Copy Header Name"
                      >
                        {copiedKey === 'secret' ? <Check className="w-3.5 h-3.5 text-white" /> : <Copy className="w-3.5 h-3.5" />}
                        <span>{copiedKey === 'secret' ? 'Copied' : 'Copy Header'}</span>
                      </button>
                    </div>
                  </div>
                </div>

                <div className="pt-2">
                  <span className="text-[10px] font-mono text-neutral-500 block mb-1">SUPPORTED ACTION NAMES:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {['get_daily_sales', 'get_top_products', 'get_product_stock', 'get_profit_summary'].map((act) => (
                      <span key={act} className="px-2 py-0.5 rounded bg-neutral-950 border border-neutral-800 font-mono text-[10px] text-neutral-300">
                        {act}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* SECTION C: Knowledge Base Sync */}
              <div className="bg-neutral-900/60 border border-neutral-800 rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-neutral-300" />
                    <span className="font-semibold text-white">Store Knowledge Sync</span>
                  </div>
                  <button
                    onClick={handleSyncKnowledge}
                    disabled={syncStatus?.loading}
                    className="px-3 py-1 bg-white text-black font-semibold rounded text-xs hover:bg-neutral-200 transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${syncStatus?.loading ? 'animate-spin' : ''}`} />
                    <span>Sync Store FAQs</span>
                  </button>
                </div>
                <p className="text-neutral-400 text-[11px]">
                  Extracts live Vastram store catalog, today&apos;s sales totals, and top-selling SKUs, then syncs them into your Gnani Agent Builder FAQ knowledge base.
                </p>
                {syncStatus && (
                  <div className="bg-neutral-950 p-2.5 rounded border border-neutral-800 font-mono text-[11px]">
                    {syncStatus.loading && <span className="text-neutral-400">Syncing live catalog to Gnani Agent Builder...</span>}
                    {syncStatus.result && (
                      <div className="text-emerald-400">
                        Sync Completed! {syncStatus.result.faq_count || 0} FAQs uploaded to bot 7bd15e5ff5a7411db02665f468d3353a.
                      </div>
                    )}
                    {syncStatus.error && (
                      <div className="text-neutral-300">
                        Note: {syncStatus.error} (Requires GNANI_PLATFORM_API_KEY with agent edit permissions)
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* SECTION D: Outbound Telephony Trigger */}
              <div className="bg-neutral-900/60 border border-neutral-800 rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <PhoneCall className="w-4 h-4 text-neutral-300" />
                  <span className="font-semibold text-white">Trigger Outbound Telephony Voice Call</span>
                </div>
                <p className="text-neutral-400 text-[11px]">
                  Uses Gnani Telephony to trigger an outbound conversational voice call from your agent (botId: 7bd15e5ff5a7411db02665f468d3353a) to any merchant or customer phone number.
                </p>
                <div className="flex items-center gap-2">
                  <input
                    type="tel"
                    value={callPhone}
                    onChange={(e) => setCallPhone(e.target.value)}
                    placeholder="+91 98765 43210"
                    className="flex-1 bg-neutral-950 border border-neutral-800 rounded px-3 py-1.5 font-mono text-xs text-white placeholder-neutral-600 focus:outline-none focus:border-white"
                  />
                  <button
                    onClick={handleTriggerCall}
                    disabled={callStatus?.loading}
                    className="px-3.5 py-1.5 bg-white text-black font-semibold rounded text-xs hover:bg-neutral-200 transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
                  >
                    <Phone className="w-3.5 h-3.5" />
                    <span>{callStatus?.loading ? 'Triggering...' : 'Place Call'}</span>
                  </button>
                </div>
                {callStatus && (
                  <div className="bg-neutral-950 p-2.5 rounded border border-neutral-800 font-mono text-[11px]">
                    {callStatus.loading && <span className="text-neutral-400">Contacting Gnani Telephony API...</span>}
                    {callStatus.result && (
                      <div className="text-emerald-400">
                        Call Triggered Successfully! Call ID: {callStatus.result.call_id || JSON.stringify(callStatus.result)}
                      </div>
                    )}
                    {callStatus.error && (
                      <div className="text-neutral-300">
                        Diagnostic: {callStatus.error}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* SECTION E: Post-Call Webhook & Session Continuity */}
              <div className="bg-neutral-900/60 border border-neutral-800 rounded-lg p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <RotateCcw className="w-4 h-4 text-neutral-300" />
                  <span className="font-semibold text-white">Post-Call Webhook &amp; SQLite Session Continuity</span>
                </div>
                <p className="text-neutral-400 text-[11px] leading-relaxed">
                  Post-call conversation transcripts and duration logs from Gnani are delivered to:
                </p>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    readOnly
                    value={`${API_BASE}/api/v1/gnani-agent/webhook`}
                    className="flex-1 bg-neutral-950 border border-neutral-800 rounded px-2.5 py-1.5 font-mono text-[11px] text-neutral-200 select-all"
                  />
                  <button
                    onClick={() => copyToClipboard(`${API_BASE}/api/v1/gnani-agent/webhook`, 'webhook_url')}
                    className="px-2.5 py-1.5 bg-neutral-800 hover:bg-neutral-700 text-neutral-200 rounded text-[11px] font-mono flex items-center gap-1 cursor-pointer"
                  >
                    {copiedKey === 'webhook_url' ? <Check className="w-3.5 h-3.5 text-white" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedKey === 'webhook_url' ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
                <div className="text-[10px] text-neutral-500 font-mono pt-1">
                  Transcripts are automatically parsed and saved to SQLite voice sessions with idempotency deduplication.
                </div>
              </div>

            </div>

            {/* Modal Footer */}
            <div className="px-5 py-3 border-t border-neutral-800 bg-black flex items-center justify-between">
              <span className="text-[10px] font-mono text-neutral-500">
                Agent ID: 7bd15e5ff5a7411db02665f468d3353a
              </span>
              <button
                onClick={() => setIsAgentModalOpen(false)}
                className="px-4 py-1.5 bg-neutral-900 hover:bg-neutral-800 border border-neutral-700 rounded text-xs text-neutral-200 cursor-pointer"
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
