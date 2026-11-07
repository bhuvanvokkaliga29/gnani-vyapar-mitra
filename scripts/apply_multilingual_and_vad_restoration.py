import re

# =============================================================================
# 1. Update services/agent/doctor_advisor.py
# =============================================================================

advisor_path = r"services/agent/doctor_advisor.py"
with open(advisor_path, "r", encoding="utf-8") as f:
    advisor_content = f.read()

# Normalize line endings
advisor_content = advisor_content.replace("\r\n", "\n")

# A. Update _detect_language
new_detect_language = '''    def _detect_language(self, text: str) -> str:
        """Detect language script or Romanized Indic code-mixed phrasing dynamically."""
        if not text:
            return "en"

        # 1. Unicode Script Range Detection (100% authoritative for native scripts)
        if any("\\u0c80" <= c <= "\\u0cff" for c in text):
            return "kn"  # Kannada
        if any("\\u0b80" <= c <= "\\u0bff" for c in text):
            return "ta"  # Tamil
        if any("\\u0d00" <= c <= "\\u0d7f" for c in text):
            return "ml"  # Malayalam
        if any("\\u0c00" <= c <= "\\u0c7f" for c in text):
            return "te"  # Telugu
        if any("\\u0a80" <= c <= "\\u0aff" for c in text):
            return "gu"  # Gujarati
        if any("\\u0980" <= c <= "\\u09ff" for c in text):
            return "bn"  # Bengali
        if any("\\u0600" <= c <= "\\u06ff" for c in text):
            return "ur"  # Urdu
        if any("\\u0a00" <= c <= "\\u0a7f" for c in text):
            return "pa"  # Punjabi

        t_low = text.lower()

        # Devanagari script (\\u0900 - \\u097f) - distinguishes Marathi vs Hindi
        if any("\\u0900" <= c <= "\\u097f" for c in text):
            if any(w in t_low for w in ["आहे", "झाली", "झाला", "विक्री", "सांगा", "काय", "नुकसान", "फायदा", "दुकान"]):
                return "mr"  # Marathi
            return "hi"  # Hindi

        # 2. Romanized Code-Mixed Phrasing (Kanglish, Hinglish, Tanglish, Manglish, etc.)
        # Kannada / Kanglish markers:
        if any(w in t_low for w in [
            "hegiddiya", "hegiddira", "chennagidini", "ivattu", "eshtu", "estu", "yaava", "yava",
            "maadu", "beku", "namaskara", "labha", "nanna", "nimma", "kottu", "hogu", "bari",
            "dukaan", "angadi", "bikkri", "marata", "maratavagide", "haagiddare"
        ]):
            return "kn"

        # Hindi / Hinglish markers:
        if any(w in t_low for w in [
            "kaise", "kya", "batao", "bhai", "aaj", "kitna", "munafa", "bikri", "accha", "theek",
            "bolo", "mera", "meri", "humara", "karna", "chahiye", "dhandha"
        ]):
            return "hi"

        # Tamil / Tanglish markers:
        if any(w in t_low for w in [
            "vanakkam", "eppadi", "irukinga", "irukku", "inru", "vilpanai", "solla", "nalla",
            "enakku", "unga", "kadavul", "evvalavu"
        ]):
            return "ta"

        # Malayalam / Manglish markers:
        if any(w in t_low for w in [
            "namaskaram", "engane", "undu", "innu", "vilppana", "labham", "parayu", "njan", "nalla",
            "ethra", "undayo"
        ]):
            return "ml"

        # Telugu markers:
        if any(w in t_low for w in [
            "namaskaram", "ela", "unnaru", "iroju", "ammukalu", "entha", "cheppandi", "naaku", "bavunnara"
        ]):
            return "te"

        return "en"'''

old_detect_pattern = r'    def _detect_language\(self, text: str\) -> str:.*?(?=\n\n|\Z)'
advisor_content = re.sub(old_detect_pattern, lambda m: new_detect_language, advisor_content, flags=re.DOTALL)
print("Updated _detect_language")

# B. Update prepare_spoken_response currency words for all Indic languages
new_currency_block = '''    # Convert currency symbols to natural spoken words depending on language
    lang = (language or "en").lower()
    if lang.startswith("kn"):
        clean = re.sub(r'₹\\s*([0-9,]+(?:\\.[0-9]+)?)', r'\\1 ರೂಪಾಯಿಗಳು', clean)
        clean = re.sub(r'₹', 'ರೂಪಾಯಿ ', clean)
    elif lang.startswith("ta"):
        clean = re.sub(r'₹\\s*([0-9,]+(?:\\.[0-9]+)?)', r'\\1 ரூபாய்', clean)
        clean = re.sub(r'₹', 'ரூபாய் ', clean)
    elif lang.startswith("ml"):
        clean = re.sub(r'₹\\s*([0-9,]+(?:\\.[0-9]+)?)', r'\\1 രൂപ', clean)
        clean = re.sub(r'₹', 'രൂപ ', clean)
    elif lang.startswith("te"):
        clean = re.sub(r'₹\\s*([0-9,]+(?:\\.[0-9]+)?)', r'\\1 రూపాయలు', clean)
        clean = re.sub(r'₹', 'రూపాయలు ', clean)
    elif lang.startswith("hi") or lang.startswith("mr"):
        clean = re.sub(r'₹\\s*([0-9,]+(?:\\.[0-9]+)?)', r'\\1 रुपये', clean)
        clean = re.sub(r'₹', 'रुपये ', clean)
    elif lang.startswith("gu"):
        clean = re.sub(r'₹\\s*([0-9,]+(?:\\.[0-9]+)?)', r'\\1 રૂપિયા', clean)
        clean = re.sub(r'₹', 'રૂપિયા ', clean)
    elif lang.startswith("bn"):
        clean = re.sub(r'₹\\s*([0-9,]+(?:\\.[0-9]+)?)', r'\\1 টাকা', clean)
        clean = re.sub(r'₹', 'টাকা ', clean)
    elif lang.startswith("ur"):
        clean = re.sub(r'₹\\s*([0-9,]+(?:\\.[0-9]+)?)', r'\\1 روپے', clean)
        clean = re.sub(r'₹', 'روپے ', clean)
    else:
        clean = re.sub(r'₹\\s*([0-9,]+(?:\\.[0-9]+)?)', r'\\1 rupees', clean)
        clean = re.sub(r'₹', 'rupees ', clean)'''

currency_old_pattern = r'    # Convert currency symbols to natural spoken words depending on language.*?clean = re\.sub\(r\'₹\', \'rupees \', clean\)'
advisor_content = re.sub(currency_old_pattern, lambda m: new_currency_block, advisor_content, flags=re.DOTALL)
print("Updated currency handling in prepare_spoken_response")

# C. Update DOCTOR_SYSTEM_PROMPT Rule 0A
prompt_old_rule = '''0A. LANGUAGE OF RESPONSE & MULTILINGUAL SUPPORT:
   - When Target Language is 'en' (the default): Even if the merchant speaks in Kannada (e.g., "ಇವತ್ತು ನನ್ನ ಸೇಲ್ಸ್ ಎಷ್ಟು ಆಗಿದೆ?", "ಸ್ಟಾಕ್ ಎಷ್ಟಿದೆ?") or Hindi, understand their Kannada/Hindi intent completely, retrieve store facts from SQLite, and produce both SPOKEN_REPLY and DETAILED_ADVICE in fluent, natural English!
   - When Target Language is 'kn' (or if the merchant explicitly commands you to speak in Kannada, e.g. "Speak in Kannada" or "ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡು"): Formulate both SPOKEN_REPLY and DETAILED_ADVICE in authentic, natural Kannada (ಕನ್ನಡ/Kanglish).
   - When Target Language is 'hi' (or if the merchant explicitly commands you to speak in Hindi): Formulate your response in natural Hindi (हिंदी/Hinglish).'''

prompt_new_rule = '''0A. DYNAMIC MULTILINGUAL CONVERSATION & NATURAL LANGUAGE MIRRORING (HIGHEST PRIORITY):
   - You MUST respond in the EXACT SAME LANGUAGE the merchant is speaking in the current turn!
   - English must NEVER be the forced default!
   - Dynamic Turn-by-Turn Language Contract:
     * Merchant speaks Kannada (ಕನ್ನಡ/Kanglish) -> You MUST respond in fluent, authentic, warm Kannada (ಕನ್ನಡ).
     * Merchant speaks English -> You MUST respond in natural, professional Indian English.
     * Merchant speaks Tamil (தமிழ்) -> You MUST respond in natural, polite Tamil (தமிழ்).
     * Merchant speaks Malayalam (മലയാളം) -> You MUST respond in natural, polite Malayalam (മലയാളം).
     * Merchant speaks Hindi (हिंदी/Hinglish) -> You MUST respond in natural, respectful Hindi (हिंदी).
     * Merchant speaks Telugu (తెలుగు) -> You MUST respond in natural, polite Telugu (తెలుగు).
     * Merchant speaks Gujarati (ગુજરાતી) -> You MUST respond in natural Gujarati (ગુજરાતી).
     * Merchant speaks Marathi (मराठी) -> You MUST respond in natural Marathi (मराठी).
     * Merchant speaks Bengali (বাংলা) -> You MUST respond in natural Bengali (বাংলা).
     * Merchant speaks Urdu (اردو) -> You MUST respond in natural Urdu (اردو).
   - DYNAMIC TURN-BY-TURN SWITCHING:
     * If the merchant switches languages across turns (e.g., Turn 1 in Kannada, Turn 2 in English, Turn 3 in Tamil or back to Kannada), you MUST dynamically switch your response language to match EACH respective turn!
     * Never remain stuck in a previous turn's language.
   - EXPLICIT COMMANDS:
     * If the merchant commands "Speak in English", "ಕನ್ನಡದಲ್ಲಿ ಮಾತಾಡು", "हिंदी में बोलो", "தமிழில் பேசு", "മലയാളത്തിൽ പറയೂ", etc., immediately obey and respond in that requested language.'''

if prompt_old_rule in advisor_content:
    advisor_content = advisor_content.replace(prompt_old_rule, prompt_new_rule, 1)
    print("Updated DOCTOR_SYSTEM_PROMPT Rule 0A")
else:
    print("Could not find prompt_old_rule")

# D. Update answer_merchant_query language selection logic
lang_detect_old = '''        # 1. Detect target language & explicit user language commands
        q_lower_text = q_clean.lower()
        is_explicit_kannada = any(p in q_lower_text for p in [
            "speak in kannada", "talk in kannada", "reply in kannada", "answer in kannada",
            "ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡು", "ಕನ್ನಡದಲ್ಲಿ ಹೇಳು", "ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರ ಕೊಡು", "ಕನ್ನಡದಲ್ಲಿ ಮಾತಾಡು"
        ])
        is_explicit_hindi = any(p in q_lower_text for p in [
            "speak in hindi", "talk in hindi", "reply in hindi", "answer in hindi",
            "हिंदी में बोलो", "हिंदी में बात करो", "हिंदी में बताओ"
        ])
        is_explicit_english = any(p in q_lower_text for p in [
            "speak in english", "talk in english", "reply in english", "answer in english",
            "ಇಂಗ್ಲಿಷ್ನಲ್ಲಿ ಮಾತನಾಡು", "ಇಂಗ್ಲಿಷ್ ನಲ್ಲಿ", "इंग्लिश में बोलो"
        ])

        if is_explicit_kannada:
            lang = "kn"
        elif is_explicit_hindi:
            lang = "hi"
        elif is_explicit_english:
            lang = "en"
        elif preferred_language in ("kn", "hi", "en"):
            lang = preferred_language
        else:
            # Default response language is English even when input is Kannada
            lang = "en"
        trace_events.append(f"language_detected:{lang}")'''

lang_detect_new = '''        # 1. Detect target language dynamically from turn query & explicit commands
        detected_turn_lang = self._detect_language(q_clean)

        q_lower_text = q_clean.lower()
        is_explicit_kannada = any(p in q_lower_text for p in [
            "speak in kannada", "talk in kannada", "reply in kannada", "answer in kannada",
            "ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡು", "ಕನ್ನಡದಲ್ಲಿ ಹೇಳು", "ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರ ಕೊಡು", "ಕನ್ನಡದಲ್ಲಿ ಮಾತಾಡು", "ಕನ್ನಡದಲ್ಲಿ"
        ])
        is_explicit_hindi = any(p in q_lower_text for p in [
            "speak in hindi", "talk in hindi", "reply in hindi", "answer in hindi",
            "हिंदी में बोलो", "हिंदी में बात करो", "हिंदी में बताओ", "हिंदी में"
        ])
        is_explicit_english = any(p in q_lower_text for p in [
            "speak in english", "talk in english", "reply in english", "answer in english",
            "ಇಂಗ್ಲಿಷ್ನಲ್ಲಿ ಮಾತನಾಡು", "ಇಂಗ್ಲಿಷ್ ನಲ್ಲಿ", "इंग्लिश में बोलो", "in english"
        ])
        is_explicit_tamil = any(p in q_lower_text for p in [
            "speak in tamil", "talk in tamil", "reply in tamil", "answer in tamil",
            "தமிழில் பேசு", "தமிழில் பதில் சொல்", "தமிழில்"
        ])
        is_explicit_malayalam = any(p in q_lower_text for p in [
            "speak in malayalam", "talk in malayalam", "മലയാളത്തിൽ സംസാരിക്കൂ", "മലയാളത്തിൽ പറയൂ", "മലയാളത്തിൽ"
        ])
        is_explicit_telugu = any(p in q_lower_text for p in [
            "speak in telugu", "talk in telugu", "తెలుగులో మాట్లాడు", "తెలుగులో"
        ])

        if is_explicit_kannada:
            lang = "kn"
        elif is_explicit_hindi:
            lang = "hi"
        elif is_explicit_english:
            lang = "en"
        elif is_explicit_tamil:
            lang = "ta"
        elif is_explicit_malayalam:
            lang = "ml"
        elif is_explicit_telugu:
            lang = "te"
        elif preferred_language and preferred_language not in ("indic-auto", "auto", "default", None):
            # STT detected language or explicit user selection for this turn
            lang = preferred_language
        else:
            # Dynamically mirror the language the user is speaking in this turn
            lang = detected_turn_lang

        trace_events.append(f"language_detected:{lang}")'''

if lang_detect_old in advisor_content:
    advisor_content = advisor_content.replace(lang_detect_old, lang_detect_new, 1)
    print("Updated answer_merchant_query language detection logic")
else:
    print("Could not find lang_detect_old")

# E. Update fast-path casual banter instruction to be culturally authentic across all languages
fast_path_old = '''            elif lang.startswith("kn"):
                inst = "ವ್ಯಾಪಾರಿಯೊಂದಿಗೆ ಆತ್ಮೀಯವಾಗಿ, ಸಂಕ್ಷಿಪ್ತವಾಗಿ ವ್ಯಾಪಾರ ಮಿತ್ರನಾಗಿ ಉತ್ತರಿಸಿ (ಉದಾ: 'ನಮಸ್ಕಾರ! ನಿಮ್ಮ ವ್ಯಾಪಾರ ಮಿತ್ರ. ಇಂದು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?'). ಯಾವುದೇ ಪ್ರಾಡಕ್ಟ್, ಸ್ಟಾಕ್, ಅಥವಾ ಮಾರಾಟದ ಅಂಕಿಅಂಶಗಳನ್ನು ಪ್ರಸ್ತಾಪಿಸಬೇಡಿ."
            elif lang.startswith("hi"):
                inst = "व्यापार मित्र के रूप में आत्मीयता और संक्षिप्तता से उत्तर दें (जैसे: 'नमस्ते! मैं आज आपकी क्या सहायता कर सकता हूँ?'). बिना पूछे किसी प्रोडक्ट या स्टॉक का विवरण न दें।"
            else:
                inst = "Respond warmly and naturally as Vyapar Mitra (e.g. 'Hey! Good to hear from you. How can I help you today?'). DO NOT give any product, stock, or financial report."'''

fast_path_new = '''            else:
                inst = (
                    f"Respond warmly, casually, and authentically in the merchant's exact language ('{lang}'). "
                    "If the merchant asks 'ಏನ್ ಬ್ರೋ, ಹೇಗಿದ್ದೀಯಾ?' or greets casually in Kannada, reply like a trusted close friend: 'ನಾನು ಚೆನ್ನಾಗಿದ್ದೀನಿ ಬ್ರೋ! ನೀನು ಹೇಗಿದ್ದೀಯಾ?'. "
                    "If they greet in English ('Hey bro, how are you?'), reply: 'I\\'m doing great, bro! How are you doing today?'. "
                    "If Tamil ('வணக்கம்! நான் நலமாக இருக்கிறேன். நீங்கள் எப்படி இருக்கிறீர்கள்?'), Malayalam ('നമസ്കാരം! സുഖമാണ്.'), Hindi ('मैं बहुत बढ़िया हूँ भाई! आप कैसे हैं?'), Telugu ('నేను బాగున్నాను! మీరు ఎలా ఉన్నారు?'). "
                    "Match their conversational tone naturally. DO NOT produce unprompted business or inventory numbers."
                )'''

if fast_path_old in advisor_content:
    advisor_content = advisor_content.replace(fast_path_old, fast_path_new, 1)
    print("Updated fast-path casual greeting instruction")
else:
    print("Could not find fast_path_old")

with open(advisor_path, "w", encoding="utf-8") as f:
    f.write(advisor_content.replace("\n", "\r\n"))
print("Saved services/agent/doctor_advisor.py")


# =============================================================================
# 2. Update apps/web/src/app/voice-agent/page.tsx (VAD Adaptive Endpointing & Turn Language)
# =============================================================================

page_path = r"apps/web/src/app/voice-agent/page.tsx"
with open(page_path, "r", encoding="utf-8") as f:
    page_content = f.read()

# Normalize line endings
page_content = page_content.replace("\r\n", "\n")

# A. Replace VAD constants with Adaptive Endpointing
vad_const_old = '''  const SPEECH_THRESHOLD = 0.035;
  const SILENCE_DURATION_MS = 420;
  const MIN_UTTERANCE_MS = 220;
  const BARGE_IN_THRESHOLD = 0.055;'''

vad_const_new = '''  const SPEECH_THRESHOLD = 0.030;
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
  };'''

if vad_const_old in page_content:
    page_content = page_content.replace(vad_const_old, vad_const_new, 1)
    print("Updated VAD constants to Adaptive Endpointing")
else:
    print("Could not find vad_const_old")

# B. Update runVADLoop silence detection
vad_loop_old = '''      } else if (speechStartRef.current !== null) {
        if (silenceStartRef.current === null) {
          silenceStartRef.current = now;
        } else if (now - silenceStartRef.current >= SILENCE_DURATION_MS) {
          const duration = silenceStartRef.current - speechStartRef.current;
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
      }'''

vad_loop_new = '''      } else if (speechStartRef.current !== null) {
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
      }'''

if vad_loop_old in page_content:
    page_content = page_content.replace(vad_loop_old, vad_loop_new, 1)
    print("Updated runVADLoop with Adaptive Silence Threshold")
else:
    print("Could not find vad_loop_old")

# C. Update handleProcessAudio to dynamically set language to detected speech
stt_lang_old = '''      // Respect user's selectedLanguage preference (defaults to English spoken output even when input is Kannada)
      await executeAssistantTurn(userText, selectedLanguage, reqId);'''

stt_lang_new = '''      // Dynamic Turn-by-Turn Multilingual Mirroring:
      // Extract the language detected by Gnani Prisma STT (e.g. 'kn', 'ta', 'ml', 'te', 'hi', 'en')
      const detectedLang = sttRes.detected_language_code?.split('-')[0] || selectedLanguage;
      if (['kn', 'hi', 'en', 'ta', 'ml', 'te', 'mr', 'gu', 'bn', 'ur'].includes(detectedLang)) {
        setSelectedLanguage(detectedLang as any);
      }

      // Execute assistant turn in the exact language the user is speaking!
      await executeAssistantTurn(userText, detectedLang, reqId);'''

if stt_lang_old in page_content:
    page_content = page_content.replace(stt_lang_old, stt_lang_new, 1)
    print("Updated handleProcessAudio with turn-by-turn multilingual mirroring")
else:
    print("Could not find stt_lang_old")

# D. Expand selectedLanguage type and UI selector buttons to include Tamil, Malayalam, Telugu
selected_lang_type_old = "const [selectedLanguage, setSelectedLanguage] = useState<'kn' | 'hi' | 'en'>('en');"
selected_lang_type_new = "const [selectedLanguage, setSelectedLanguage] = useState<'kn' | 'hi' | 'en' | 'ta' | 'ml' | 'te'>('kn');"

if selected_lang_type_old in page_content:
    page_content = page_content.replace(selected_lang_type_old, selected_lang_type_new, 1)
    print("Expanded selectedLanguage state type")

selector_old = '''          {/* Language Selector */}
          <div className="flex items-center bg-neutral-900 border border-neutral-700 rounded-lg p-0.5 text-xs font-semibold">
            <button
              onClick={() => setSelectedLanguage('kn')}
              className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
                selectedLanguage === 'kn' ? 'bg-white text-black font-bold' : 'text-neutral-400 hover:text-white'
              }`}
            >
              ಕನ್ನಡ
            </button>
            <button
              onClick={() => setSelectedLanguage('hi')}
              className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
                selectedLanguage === 'hi' ? 'bg-white text-black font-bold' : 'text-neutral-400 hover:text-white'
              }`}
            >
              हिंदी
            </button>
            <button
              onClick={() => setSelectedLanguage('en')}
              className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
                selectedLanguage === 'en' ? 'bg-white text-black font-bold' : 'text-neutral-400 hover:text-white'
              }`}
            >
              English
            </button>
          </div>'''

selector_new = '''          {/* Multilingual Selector */}
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
          </div>'''

if selector_old in page_content:
    page_content = page_content.replace(selector_old, selector_new, 1)
    print("Updated Multilingual Selector in UI")
else:
    print("Could not find selector_old")

with open(page_path, "w", encoding="utf-8") as f:
    f.write(page_content)
print("Saved apps/web/src/app/voice-agent/page.tsx")
