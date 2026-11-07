import re

file_path = r"services/agent/doctor_advisor.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update prepare_spoken_response
new_prepare_spoken = '''def prepare_spoken_response(text: Optional[str], language: Optional[str] = "en", intent: Optional[str] = None) -> str:
    """Sanitize and format text specifically for natural voice speech output (Gnani Timbre TTS).
    
    Guarantees:
    - Strictly 0 internal system labels (DETAILED_BOX, LANGUAGE PREFERENCE, SPOKEN_REPLY, etc.)
    - Strictly 0 table pipes (|), markdown headers, bullet marks, or brackets
    - Consistent, steady, calm speaking volume and pitch across all questions
    - 0 emotion/XML tags (<excited>, <sigh>, etc.) to prevent shouting or pitch distortion
    - Native currency pronunciation across Kannada, Hindi, and English
    - 0 hashtags (# or #tag) so TTS never reads 'hashtag' aloud
    - 0 markdown syntax (*, _, ~, `, headers, bullets)
    - 0 URLs or brackets
    - Rich, natural conversational cadence (2-4 natural sentences, up to 75-80 words)
    """
    if not text:
        return ""
    
    clean = text

    # If the text accidentally contains both SPOKEN_REPLY and DETAILED sections, take ONLY the SPOKEN portion!
    m_spk = re.search(r'[*_#]*\\s*(?:SPOKEN[_\s]*REPLY|SPOKEN[_\s]*TEXT|SPOKEN)\\s*[:*_-]*\\s*', clean, flags=re.IGNORECASE)
    m_det = re.search(r'[*_#]*\\s*(?:DETAILED[_\s]*ADVICE|DETAILED[_\s]*BOX|DETAILED[_\s]*REPORT|DETAILED)\\s*[:*_-]*\\s*', clean, flags=re.IGNORECASE)
    if m_spk and m_det:
        if m_spk.start() < m_det.start():
            clean = clean[m_spk.end():m_det.start()]
        else:
            clean = clean[m_spk.end():]
    elif m_spk:
        clean = clean[m_spk.end():]
    elif m_det:
        before_det = clean[:m_det.start()].strip()
        if before_det:
            clean = before_det

    # Strip any internal system directives or language preference updates completely
    clean = re.sub(r'(?i)LANGUAGE\\s*PREFERENCE(?:\\s*UPDATE)?\\s*[:*_-]*\\s*[^\\n]*', '', clean)
    clean = re.sub(r'(?i)DETAILED[_\\s]*(?:BOX|ADVICE|REPORT)\\s*[:*_-]*', '', clean)
    clean = re.sub(r'(?i)SPOKEN[_\\s]*(?:REPLY|TEXT)\\s*[:*_-]*', '', clean)
    clean = re.sub(r'^\\s*SPOKENRE\\w*\\s*', '', clean, flags=re.IGNORECASE)
    
    # Strip markdown table rows completely (any line with pipes | or divider dashes)
    lines = clean.splitlines()
    non_table_lines = [
        l for l in lines 
        if not ('|' in l and l.strip().startswith('|')) 
        and not re.match(r'^\\s*\\|?[-:| ]+\\|?\\s*$', l)
    ]
    clean = "\\n".join(non_table_lines)

    # Strip URLs
    clean = re.sub(r'https?://\\S+', '', clean)
    # Strip hashtags completely (e.g. #sale, #vastram)
    clean = re.sub(r'#\\w+', '', clean)
    clean = re.sub(r'#', '', clean)
    # Strip markdown symbols & blockquote markers
    clean = re.sub(r'[*_~`|>]', '', clean)
    # Strip markdown bullet dashes, list markers, and headers
    clean = re.sub(r'^\\s*[-*+]\\s+', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'^\\s*\\d+\\.\\s+', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'^\\s*#+\\s+', '', clean, flags=re.MULTILINE)
    
    # Convert currency symbols to natural spoken words depending on language
    lang = (language or "en").lower()
    if lang.startswith("kn"):
        clean = re.sub(r'₹\\s*([0-9,]+(?:\\.[0-9]+)?)', r'\\1 ರೂಪಾಯಿಗಳು', clean)
        clean = re.sub(r'₹', 'ರೂಪಾಯಿ ', clean)
    elif lang.startswith("hi"):
        clean = re.sub(r'₹\\s*([0-9,]+(?:\\.[0-9]+)?)', r'\\1 रुपये', clean)
        clean = re.sub(r'₹', 'रुपये ', clean)
    else:
        clean = re.sub(r'₹\\s*([0-9,]+(?:\\.[0-9]+)?)', r'\\1 rupees', clean)
        clean = re.sub(r'₹', 'rupees ', clean)
        
    # Strip bracketed metadata like [Executed Tools...] or {sku: ...}
    clean = re.sub(r'\\{[^{}]*\\}', '', clean)
    clean = re.sub(r'\\[[^\\[\\]]*\\]', '', clean)
    
    # Strip all emotion or XML/SSML tags completely to ensure consistent, calm, natural voice volume
    clean = re.sub(r'<[^>]+>', '', clean)

    # For natural conversational delivery, clamp spoken text cleanly at sentence boundaries (up to 80 words)
    words = clean.split()
    if len(words) > 80:
        sub = " ".join(words[:80])
        m = re.search(r'^(.*[.!?।])', sub)
        if m and len(m.group(1).split()) >= 15:
            clean = m.group(1)
        else:
            clean = sub

    # Normalize whitespace
    clean = re.sub(r'\\s+', ' ', clean).strip()
    return clean'''

start_idx = content.find("def prepare_spoken_response(text: Optional[str]")
end_idx = content.find("DOCTOR_SYSTEM_PROMPT = \"\"\"")
if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_prepare_spoken + "\n\n\n" + content[end_idx:]
    print("Found and replaced prepare_spoken_response")
else:
    print("Could not find prepare_spoken_response slice", start_idx, end_idx)

# 2. Update DOCTOR_SYSTEM_PROMPT with explicit language, zero greeting repetition, and clean spoken rules
prompt_old_prefix = 'CRITICAL CONVERSATIONAL INTELLIGENCE, DOMAIN & MULTI-TURN MEMORY RULES:'
prompt_new_prefix = '''CRITICAL CONVERSATIONAL INTELLIGENCE, DOMAIN & MULTI-TURN MEMORY RULES:

0A. DEFAULT SPOKEN LANGUAGE (KANNADA INPUT -> ENGLISH RESPONSE):
   - Vastram's merchant frequently speaks in Kannada (ಕನ್ನಡ) or Hindi (हिंदी).
   - BY DEFAULT, YOU MUST RESPOND IN FLUENT, POLITE, CONVERSATIONAL ENGLISH.
   - When the merchant speaks in Kannada (e.g., "ಇವತ್ತು ನನ್ನ ಸೇಲ್ಸ್ ಎಷ್ಟು ಆಗಿದೆ?", "ಸ್ಟಾಕ್ ಎಷ್ಟಿದೆ?"):
     * Fully comprehend their Kannada intent.
     * Use the verified SQLite store facts to answer.
     * Formulate both SPOKEN_REPLY and DETAILED_ADVICE in natural, fluent English!
   - ONLY switch response language to Kannada or Hindi if the merchant explicitly commands you to (e.g., "Speak in Kannada", "ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡು", "हिंदी में बोलो").

0B. ZERO GREETING REPETITION & MULTI-QUESTION HANDLING:
   - Greet the merchant ("Hello!", "Namaskara!") ONLY ONCE at the start of a new session.
   - In ANY subsequent turn (turns > 0), NEVER repeat opening greetings. Answer the business question immediately and directly!
   - If the merchant combines a greeting and a business question (e.g., "Hello, how are you? Tell me today's sales"), provide a very brief 3-word polite acknowledgement ("Doing well!") and immediately provide the exact sales figures!
   - NEVER output internal instructions, debug tags, table pipes, or metadata labels like DETAILED_BOX or LANGUAGE PREFERENCE UPDATE in SPOKEN_REPLY!'''

if prompt_old_prefix in content:
    content = content.replace(prompt_old_prefix, prompt_new_prefix, 1)
    print("Replaced prompt prefix")
else:
    print("Prompt prefix not found")

# 3. Update answer_merchant_query language selection
old_lang_detect = '''        # 1. Detect target language
        lang = preferred_language or self._detect_language(q_clean)
        trace_events.append(f"language_detected:{lang}")'''

new_lang_detect = '''        # 1. Detect target language & explicit user language commands
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

# Normalize newlines for search
content_norm = content.replace("\r\n", "\n")
old_lang_norm = old_lang_detect.replace("\r\n", "\n")
if old_lang_norm in content_norm:
    content_norm = content_norm.replace(old_lang_norm, new_lang_detect.replace("\r\n", "\n"), 1)
    print("Replaced language detect")
else:
    print("Language detect not found")

# 4. Update anchor injection in _run_dynamic_tool_loop (only if recall query)
old_anchor = '''        if opening_anchors and len(conversation_history) > 10:
            anchor_summary = (
                f"[CONVERSATION OPENING (HOW THIS SESSION BEGAN)]\\n"
                f"- First Merchant Query: {opening_anchors[0].get('content')}\\n"
                f"- First Vyapar Mitra Reply: {opening_anchors[1].get('spoken_content') or opening_anchors[1].get('content')}"
            )
            messages.append(LLMMessage(role=LLMRole.SYSTEM, content=anchor_summary))'''

new_anchor = '''        is_recall_query = any(w in query_lower for w in [
            "start", "first", "beginning", "earlier", "remember", "recall",
            "ಮೊದಲು", "ಪ್ರಾರಂಭ", "ಶುರು", "पहले", "शुरुआत"
        ])
        if opening_anchors and is_recall_query and len(conversation_history) > 6:
            anchor_summary = (
                f"[CONVERSATION OPENING (HOW THIS SESSION BEGAN)]\\n"
                f"- First Merchant Query: {opening_anchors[0].get('content')}\\n"
                f"- First Vyapar Mitra Reply: {opening_anchors[1].get('spoken_content') or opening_anchors[1].get('content')}"
            )
            messages.append(LLMMessage(role=LLMRole.SYSTEM, content=anchor_summary))'''

old_anchor_norm = old_anchor.replace("\r\n", "\n")
if old_anchor_norm in content_norm:
    content_norm = content_norm.replace(old_anchor_norm, new_anchor.replace("\r\n", "\n"), 1)
    print("Replaced anchor summary")
else:
    print("Anchor summary not found")

# 5. Overhaul _parse_dual_format_response
old_parse_fn = '''    def _parse_dual_format_response(self, text: str, lang: str) -> (str, str):
        """Split LLM response into SPOKEN_REPLY and DETAILED_ADVICE sections."""
        clean_text = text.strip()
        spoken = None
        detailed = None

        m_spk = re.search(r'[*_#]*\\s*SPOKEN[_\s]*REPLY\\s*[:*_-]*\\s*', clean_text, flags=re.IGNORECASE)
        m_det = re.search(r'[*_#]*\\s*DETAILED[_\s]*ADVICE\\s*[:*_-]*\\s*', clean_text, flags=re.IGNORECASE)

        if m_spk and m_det:
            if m_spk.start() < m_det.start():
                spoken = clean_text[m_spk.end():m_det.start()].strip()
                detailed = clean_text[m_det.end():].strip()
            else:
                detailed = clean_text[m_det.end():m_spk.start()].strip()
                spoken = clean_text[m_spk.end():].strip()
        elif m_spk:
            spoken = clean_text[m_spk.end():].strip()
            detailed = clean_text
        elif m_det:
            spoken = clean_text[:m_det.start()].strip()
            detailed = clean_text[m_det.end():].strip()
        else:
            sentences = re.split(r'(?<=[.!?।])\\s+', clean_text)
            spoken = " ".join(sentences[:2]).strip()
            detailed = clean_text

        # Bulletproof sanity check: if spoken is empty, left as a stray token, or cut off (< 15 words)
        words_count = len((spoken or "").strip().split())
        if not spoken or spoken.strip().upper() in ("SPOKEN", "SPOKEN_REPLY", "SPOKENRE", "YOU", "") or words_count < 15:
            clean_detailed_prose = re.sub(r'[#*`_\\[\\]|]', '', detailed or clean_text)
            clean_detailed_prose = re.sub(r'^\\s*[-*+]\\s+', '', clean_detailed_prose, flags=re.MULTILINE)
            sentences = [s.strip() for s in re.split(r'(?<=[.!?।])\\s+', clean_detailed_prose) if len(s.strip().split()) >= 4]
            if sentences:
                candidate = " ".join(sentences[:3]).strip()
                if len(candidate.split()) > words_count:
                    spoken = candidate
            elif not spoken:
                spoken = clean_detailed_prose[:120]

        # Clean spoken text thoroughly of any markdown symbols, hashtags, or formatting
        clean_spoken = prepare_spoken_response(spoken, language=lang)
        return clean_spoken, detailed'''

new_parse_fn = '''    def _parse_dual_format_response(self, text: str, lang: str) -> (str, str):
        """Split LLM response into SPOKEN_REPLY and DETAILED_ADVICE sections cleanly."""
        clean_text = text.strip()
        spoken = None
        detailed = None

        m_spk = re.search(r'[*_#]*\\s*(?:SPOKEN[_\s]*REPLY|SPOKEN[_\s]*TEXT|SPOKEN)\\s*[:*_-]*\\s*', clean_text, flags=re.IGNORECASE)
        m_det = re.search(r'[*_#]*\\s*(?:DETAILED[_\s]*ADVICE|DETAILED[_\s]*BOX|DETAILED[_\s]*REPORT|DETAILED)\\s*[:*_-]*\\s*', clean_text, flags=re.IGNORECASE)

        if m_spk and m_det:
            if m_spk.start() < m_det.start():
                spoken = clean_text[m_spk.end():m_det.start()].strip()
                detailed = clean_text[m_det.end():].strip()
            else:
                detailed = clean_text[m_det.end():m_spk.start()].strip()
                spoken = clean_text[m_spk.end():].strip()
        elif m_spk:
            spoken = clean_text[m_spk.end():].strip()
            detailed = clean_text
        elif m_det:
            spoken = clean_text[:m_det.start()].strip()
            detailed = clean_text[m_det.end():].strip()
        else:
            sentences = re.split(r'(?<=[.!?।])\\s+', clean_text)
            spoken = " ".join(sentences[:2]).strip()
            detailed = clean_text

        # Sanitize detailed view: strip internal system metadata labels
        if detailed:
            detailed = re.sub(r'^(?:[*_#]*\\s*(?:DETAILED[_\s]*(?:BOX|ADVICE|REPORT)|SPOKEN[_\s]*REPLY|LANGUAGE\\s*PREFERENCE(?:\\s*UPDATE)?)\\s*[:*_-]*\\s*)+', '', detailed, flags=re.IGNORECASE).strip()

        # Sanitize spoken view: if completely empty or just the label token, extract first clean prose sentence
        if not spoken or spoken.strip().upper() in ("SPOKEN", "SPOKEN_REPLY", "SPOKENRE", "YOU", "", "None"):
            clean_prose = re.sub(r'\\|.*?\\|', '', detailed or clean_text)
            clean_prose = re.sub(r'[#*`_\\[\\]|]', '', clean_prose)
            clean_prose = re.sub(r'^\\s*[-*+]\\s+', '', clean_prose, flags=re.MULTILINE)
            sentences = [s.strip() for s in re.split(r'(?<=[.!?।])\\s+', clean_prose) if len(s.strip().split()) >= 3]
            spoken = " ".join(sentences[:2]).strip() if sentences else (clean_prose[:120] if clean_prose else "")

        # Clean spoken text thoroughly of any markdown symbols, hashtags, or formatting
        clean_spoken = prepare_spoken_response(spoken, language=lang)
        return clean_spoken, detailed'''

old_parse_norm = old_parse_fn.replace("\r\n", "\n")
if old_parse_norm in content_norm:
    content_norm = content_norm.replace(old_parse_norm, new_parse_fn.replace("\r\n", "\n"), 1)
    print("Replaced parse function")
else:
    print("Parse function not found")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content_norm.replace("\n", "\r\n"))

print("Finished patching services/agent/doctor_advisor.py")
