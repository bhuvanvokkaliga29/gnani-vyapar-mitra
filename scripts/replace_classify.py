with open("services/agent/doctor_advisor.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if "def _classify_intent(" in line:
        start_idx = i
    if start_idx != -1 and "def _detect_language(" in line:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    new_method = """    def _classify_intent(self, text: str) -> str:
        \"\"\"Classify merchant query into structured business intents.\"\"\"
        t = text.lower()
        # 1. Humor & Jokes
        if any(k in t for k in ["joke", "ಜೋಕ್", "ಚುಟ್ಕುಲ", "चुटकुला", "chutkula", "funny"]):
            return "JOKE"

        # 2. Greetings, Identity & Social Chit-Chat
        if any(k in t for k in [
            "namaskara", "namaste", "ನಮಸ್ಕಾರ", "नमस्ते", "प्रणाम", "hello", "hi vyapar", "kaise ho",
            "ಹೇಗಿದ್ದೀರಿ", "ಹೇಗಿದೀರಾ", "ನೀವು ಯಾರು", "ನಿನ್ನ ಹೆಸರೇನು", "ನಿಮ್ಮ ಹೆಸರೇನು", "who are you",
            "what is your name", "kya haal", "good morning", "shubhodaya", "how are you", "how are u",
            "how r u", "how do you do", "aap kaise hain", "kaisa hai", "kaisa chal raha hai",
            "tumhara naam kya hai", "aapka naam kya hai", "आपका नाम क्या है", "तुम्हारा नाम क्या है"
        ]):
            return "GREETING"

        # 3. Merchant Corrections & Misunderstandings
        if any(k in t for k in [
            "correct the previous", "correct previous", "that is wrong", "that's not what i asked",
            "ಸರಿಪಡಿಸು", "ಹಿಂದಿನ ಉತ್ತರ ಸರಿಪಡಿಸು", "ತಪ್ಪಾಗಿದೆ", "ನಾನು ಕೇಳಿದ್ದು ಇದಲ್ಲ", "ಹಿಂದಿನ ಉತ್ತರ",
            "पिछला उत्तर सही करो", "सही करो", "गलत है", "मैंने यह नहीं पूछा", "पिछला उत्तर"
        ]):
            return "CORRECTION"

        # 4. Tomorrow's Action Plan
        if any(k in t for k in [
            "what should i do tomorrow", "what to do tomorrow", "tomorrow plan", "tomorrow",
            "ನಾಳೆ ನಾನು ಏನು ಮಾಡಬೇಕು", "ನಾಳೆ ಏನು ಮಾಡಬೇಕು", "ನಾಳೆ ಏನು", "ಮುಂದಿನ ಹೆಜ್ಜೆ",
            "कल क्या करना चाहिए", "कल मुझे क्या करना चाहिए", "कल क्या करूँ", "कल क्या करें"
        ]):
            return "ACTION_PLAN"

        # 5. Why is profit low diagnosis
        if any(k in t for k in [
            "why is profit low", "profit is low", "why profit low", "low profit",
            "ಲಾಭ ಏಕೆ ಕಡಿಮೆಯಾಗಿದೆ", "ಲಾಭ ಏಕೆ ಕಡಿಮೆ", "ಲಾಭ ಕಡಿಮೆ", "ಪ್ರಾಫಿಟ್ ಕಡಿಮೆ",
            "मुनाफा कम क्यों है", "मुनाफा कम क्यों", "मुनाफा कम", "प्रॉफिट कम क्यों"
        ]):
            return "PROFIT_LOW_DIAGNOSIS"

        # 6. Explicit Marketing & Promotional Content Creation
        if any(k in t for k in [
            "create a whatsapp promotion", "create whatsapp promotion", "promotion message", "whatsapp promotion",
            "ಪ್ರಮೋಷನ್ ಮೆಸೇಜ್", "ಪ್ರಮೋಷನ್ ರೆಡಿ", "ಪ್ರಮೋಷನ್ ಮಾಡು", "ಮೆಸೇಜ್ ರೆಡಿ ಮಾಡು",
            "प्रमोशन मैसेज बनाओ", "प्रमोशन बनाओ", "प्रमोशन तैयार करो"
        ]):
            return "MARKETING_CREATION"

        # 7. Casual Conversation / Platform Explanations / Statements mentioning WhatsApp
        if any(k in t for k in [
            "what is whatsapp", "whatsapp kya hai", "ವಾಟ್ಸಾಪ್ ಅಂದರೆ ಏನು", "whatsapp ಏನು",
            "sent a whatsapp", "sent whatsapp", "whatsapp message yesterday", "whatsapp msg", "whatsapp message",
            "ಕಳಿಸಿದ್ದೆ", "ಮೆಸೇಜ್ ಕಳಿಸಿದ್ದೆ", "ವಾಟ್ಸಾಪ್ ಕಳಿಸಿದ್ದೆ", "ವಾಟ್ಸಾಪ್ ಮೆಸೇಜ್", "ವಾಟ್ಸಾಪ್ ಮೆಸೇಜ್ ಕಳಿಸಿದ್ದೆ",
            "मैसेज भेजा था", "व्हाट्सएप भेजा था", "व्हाट्सएप मैसेज भेजा", "व्हाट्सएप मैसेज"
        ]):
            return "CASUAL_MENTION"

        # 8. Strategic Advice & General Growth
        if any(k in t for k in [
            "improve ಮಾಡೋಕೆ", "improve ಮಾಡುವುದು ಹೇಗೆ", "ಹೆಚ್ಚಿಸುವುದು ಹೇಗೆ", "growth ಸಲಹೆ",
            "how to improve", "how can i improve", "growth tips", "सुधार कैसे करें"
        ]):
            return "STRATEGIC_ADVICE"

        # 9. Follow-up intent checks:
        if any(k in t for k in [
            "its stock", "it's stock", "ಆ product stock", "product stock", "stock estide", "stock eshtu", "stock estu",
            "ಸ್ಟಾಕ್ ಎಷ್ಟಿದೆ", "ಸ್ಟಾಕ್ ಎಷ್ಟು", "ಇವರ ಸ್ಟಾಕ್", "ಇವರ ಸ್ಟಾಕ್ ಎಷ್ಟಿದೆ",
            "ಆ ಪ್ರಾಡಕ್ಟ್ ಸ್ಟಾಕ್", "ಪ್ರಾಡಕ್ಟ್ ಸ್ಟಾಕ್", "स्टॉक कितना", "कितना स्टॉक", "इसका स्टॉक"
        ]):
            return "FOLLOWUP_STOCK"

        if any(k in t for k in ["its profit", "it's profit", "ಎಷ್ಟು ಲಾಭ", "ಇದು ಎಷ್ಟು ಲಾಭ", "कितना मुनाफा", "इससे कितना मुनाफा", "profit does it generate"]):
            return "FOLLOWUP_PROFIT"

        if any(k in t for k in ["sells the most", "top selling", "ಹೆಚ್ಚು ಮಾರಾಟ", "highest selling", "ಯಾವ ಪ್ರಾಡಕ್ಟ್", "ಯಾವ ಪ್ರಾಡಕ್ಟ್ ಹೆಚ್ಚು", "सबसे ज्यादा बिकने वाला"]):
            return "TOP_SELLING"

        if any(k in t for k in ["reorder", "ರೀಆರ್ಡರ್", "ಖಾಲಿಯಾಗುತ್ತಿದೆ", "stockout", "shortage", "ಖಾಲಿ"]):
            return "REORDER_ALERT"

        if any(k in t for k in ["ಸ್ಲೋ", "dead stock", "slow", "moving slowly", "ಕಡಿಮೆ ಸೇಲ್ಸ್", "trapped"]):
            return "DEAD_STOCK"

        if any(k in t for k in [
            "channel performance", "channel margin", "channel economics", "which channel", "amazon vs whatsapp",
            "whatsapp vs amazon", "ಚಾನೆಲ್", "ಚಾನೆಲ್ ಮಾರ್ಜಿನ್", "चैनल परफॉर्मेंस", "चैनल मार्जिन"
        ]):
            return "CHANNEL_PERFORMANCE"

        if any(k in t for k in ["ಲಾಭ", "profit", "margin", "highest profit", "ಹೆಚ್ಚು ಲಾಭ"]):
            return "PROFIT_SUMMARY"

        if any(k in t for k in [
            "how is my business doing", "business doing", "ವ್ಯಾಪಾರ ಹೇಗೆ", "ಮಾರಾಟ", "ವ್ಯಾಪಾರ", "व्यापार कैसा",
            "ಸೇಲ್ಸ್", "sales", "revenue", "order", "today", "ivattu", "बिक्री", "आज की बिक्री"
        ]):
            return "DAILY_SALES"

        if any(k in t for k in ["stock", "ದಾಸ್ತಾನು", "inventory"]):
            return "INVENTORY_HEALTH"

        return "GENERAL_GROWTH"

"""
    lines[start_idx:end_idx] = [new_method]
    with open("services/agent/doctor_advisor.py", "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("SUCCESS: Fully replaced _classify_intent")
else:
    print(f"ERROR: indices not found ({start_idx}, {end_idx})")

