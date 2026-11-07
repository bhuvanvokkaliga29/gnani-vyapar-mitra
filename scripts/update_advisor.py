with open('services/agent/doctor_advisor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

target_start = -1
for i, l in enumerate(lines):
    if '            "namaskara", "namaste", "ನಮಸ್ಕಾರ"' in l:
        target_start = i - 1 # '        if any(k in t for k in ['
        break

if target_start != -1:
    new_code = '''        # 2. Greetings, Identity & Social Chit-Chat
        if any(k in t for k in [
            "namaskara", "namaste", "ನಮಸ್ಕಾರ", "नमस्ते", "प्रणाम", "hello", "hi vyapar", "kaise ho",
            "ಹೇಗಿದ್ದೀರಿ", "ಹೇಗಿದೀರಾ", "ನೀವು ಯಾರು", "ನಿನ್ನ ಹೆಸರೇನು", "ನಿಮ್ಮ ಹೆಸರೇನು", "who are you",
            "what is your name", "kya haal", "good morning", "shubhodaya", "how are you", "how are u",
            "how r u", "how do you do", "aap kaise hain", "kaisa hai", "kaisa chal raha hai",
            "tumhara naam kya hai", "aapka naam kya hai", "आपका नाम क्या है", "तुम्हारा नाम क्या है"
        ]):
            return "GREETING"

        # 3. Explicit Marketing & Promotional Content Creation
        if any(k in t for k in [
            "create a whatsapp promotion", "create whatsapp promotion", "promotion message", "whatsapp promotion",
            "ಪ್ರಮೋಷನ್ ಮೆಸೇಜ್", "ಪ್ರಮೋಷನ್ ರೆಡಿ", "ಪ್ರಮೋಷನ್ ಮಾಡು", "ಮೆಸೇಜ್ ರೆಡಿ ಮಾಡು",
            "प्रमोशन मैसेज बनाओ", "प्रमोशन बनाओ", "प्रमोशन तैयार करो"
        ]):
            return "MARKETING_CREATION"

        # 4. Casual Conversation / Statements mentioning WhatsApp or messaging
        if any(k in t for k in [
            "sent a whatsapp", "sent whatsapp", "whatsapp message yesterday", "whatsapp msg",
            "ಕಳಿಸಿದ್ದೆ", "ಮೆಸೇಜ್ ಕಳಿಸಿದ್ದೆ", "ವಾಟ್ಸಾಪ್ ಕಳಿಸಿದ್ದೆ", "ವಾಟ್ಸಾಪ್ ಮೆಸೇಜ್ ಕಳಿಸಿದ್ದೆ",
            "मैसेज भेजा था", "व्हाट्सएप भेजा था", "व्हाट्सएप मैसेज भेजा"
        ]):
            return "CASUAL_MENTION"
'''
    # The old block is 5 lines: lines[target_start : target_start+5]
    lines[target_start : target_start + 5] = [new_code]
    with open('services/agent/doctor_advisor.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("SUCCESS: Replaced greeting and added marketing/casual mention intents")
else:
    print("ERROR: Could not find target_start")
