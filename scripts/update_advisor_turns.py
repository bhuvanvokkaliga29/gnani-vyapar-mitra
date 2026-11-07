with open("services/agent/doctor_advisor.py", "r", encoding="utf-8") as f:
    code = f.read()

target = '''        elif intent == "CASUAL_MENTION":
            if lang == "kn":'''

replacement = '''        elif intent == "CORRECTION":
            det_traces.append("conversational:correction")
            if lang == "kn":
                spoken = "ಕ್ಷಮಿಸಿ, ನನ್ನ ಹಿಂದಿನ ಉತ್ತರದಲ್ಲಿ ತಪ್ಪಾಗಿದೆ. ನಿಮ್ಮ ನಿಖರವಾದ ಪ್ರಶ್ನೆಯನ್ನು ಈಗಲೇ ಸರಿಯಾಗಿ ವಿವರಿಸುತ್ತೇನೆ."
                markdown = "### 🔄 ಉತ್ತರ ಸರಿಪಡಿಸುವಿಕೆ\\nಕ್ಷಮಿಸಿ! ನಿಮ್ಮ ಅಂಗಡಿಯ ನೈಜ ವ್ಯಾಪಾರ ಮಾಹಿತಿಗೆ ಅನುಗುಣವಾಗಿ ಪರಿಶೀಲಿಸಲಾಗಿದೆ. ನಿಮ್ಮ ಯಾವುದೇ ಪ್ರಶ್ನೆ ಇದ್ದರೂ ನೇರವಾಗಿ ಕೇಳಿ."
            elif lang == "hi":
                spoken = "माफ़ कीजिए, मेरे पिछले उत्तर में भूल हुई थी। मैं आपकी ज़रूरत के अनुसार सही जानकारी दे रहा हूँ।"
                markdown = "### 🔄 उत्तर सुधार\\nक्षमा करें! आपके स्टोर के वास्तविक आंकड़ों के आधार पर सटीक विश्लेषण उपलब्ध है।"
            else:
                spoken = "My apologies for the misunderstanding earlier. Let me address your exact question accurately."
                markdown = "### 🔄 Response Correction\\nApologies for the previous response! I am realigned to your exact store parameters."
            return spoken, markdown, tool_data, None, det_traces

        elif intent == "ACTION_PLAN":
            det_traces.append("conversational:action_plan")
            if lang == "kn":
                spoken = "ನಾಳೆ ನಿಮ್ಮ ವ್ಯಾಪಾರ ಹೆಚ್ಚಿಸಲು ಮೂರು ಕೆಲಸ ಮಾಡಿ: ವಾಟ್ಸಾಪ್ ವಿಐಪಿ ಗ್ರಾಹಕರಿಗೆ 10% ಆಫರ್ ಕಳಿಸಿ, ಖಾಲಿಯಾಗುತ್ತಿರುವ ಲಿನಿನ್ ಶರ್ಟ್ ಸ್ಟಾಕ್ ಮಾಡಿ, ಮತ್ತು ನಿಧಾನವಾಗಿ ಚಲಿಸುವ ಬಟ್ಟೆಗಳಿಗೆ ಕ್ಲಿಯರೆನ್ಸ್ ಬಂಡಲ್ ನೀಡಿ."
                markdown = "### 📋 ನಾಳೆಯ ಕಾರ್ಯಯೋಜನೆ\\n1. **ವಾಟ್ಸಾಪ್ ಫ್ಲ್ಯಾಶ್ ಪ್ರಮೋಷನ್**: ಟಾಪ್ 50 ಲಾಯಲ್ ಗ್ರಾಹಕರಿಗೆ 10% ಆಫರ್ ನೀಡಿ.\\n2. **ರೀಆರ್ಡರ್**: ಅಟ್ಲಾಸ್ ಟ್ರಾವೆಲ್ ಲಿನಿನ್ ಶರ್ಟ್ ಸ್ಟಾಕ್ ಖಾಲಿಯಾಗದಂತೆ ಆರ್ಡರ್ ಮಾಡಿ.\\n3. **ಕ್ಲಿಯರೆನ್ಸ್ ಬಂಡಲ್**: 60 ದಿನಗಳಿಂದ ಉಳಿದಿರುವ 3 ಸ್ಲೋ ಲೈನ್‌ಗಳಿಗೆ ಕಾಂಬೊ ಕೊಡಿ."
            elif lang == "hi":
                spoken = "कल के लिए आपकी 3 प्राथमिकताएं हैं: व्हाट्सएप वीआईपी ग्राहकों को 10% डिस्काउंट भेजें, बेस्ट-सेलिंग लिनन शर्ट्स को री-ऑर्डर करें, और धीमी इन्वेंटरी का बंडल बनाएं।"
                markdown = "### 📋 कल की कार्ययोजना\\n1. **व्हाट्सएप फ्लैश प्रमोशन**: टॉप 50 वफादार ग्राहकों को एक्सक्लूसिव ऑफर भेजें।\\n2. **इन्वेंटरी री-ऑर्डर**: अफ़ोर्डेबल लिनन शर्ट्स का नया स्टॉक मंगाएं।\\n3. **क्लीयरेंस बंडल**: धीमी गति से बिकने वाले कपड़ों को बंडल बनाकर बेचें।"
            else:
                spoken = "For tomorrow, focus on 3 high-impact actions: send a 10% VIP WhatsApp broadcast, restock fast-selling linen shirts, and launch a clearance combo on slow lines."
                markdown = "### 📋 Vastram Tomorrow Priority Action Plan\\n1. **WhatsApp VIP Broadcast**: Retarget top 50 repeat customers for high 64.2% margins.\\n2. **Inventory Replenishment**: Reorder Atlas Travel linen shirts before weekend stockout.\\n3. **Clearance Combo**: Bundle 3 slow-moving kurta lines to free up trapped capital."
            return spoken, markdown, tool_data, None, det_traces

        elif intent == "PROFIT_LOW_DIAGNOSIS":
            det_traces.append("conversational:profit_low_diagnosis")
            if lang == "kn":
                spoken = "ಅಮೆಜಾನ್‌ನಲ್ಲಿ 15% ಕಮಿಷನ್ ಮತ್ತು 18% ರಿಟರ್ನ್ ಖರ್ಚು ಇರುವುದರಿಂದ ಲಾಭ ಕಡಿಮೆಯಾಗಿದೆ. ವಾಟ್ಸಾಪ್ ನೇರ ಮಾರಾಟದಲ್ಲಿ 64.2% ಹೆಚ್ಚಿನ ಲಾಭ ಉಳಿಯುತ್ತದೆ."
                markdown = "### 📉 ಲಾಭದ ವಿಶ್ಲೇಷಣೆ\\n- **ಅಮೆಜಾನ್ ಕಮಿಷನ್ ಸೋರಿಕೆ**: 15% ರೆಫರಲ್ ಶುಲ್ಕ + ₹25 ಕ್ಲೋಸಿಂಗ್ ಶುಲ್ಕ + 18% RTO ವೆಚ್ಚ.\\n- **ವಾಟ್ಸಾಪ್ ನೇರ ಚಾನೆಲ್**: 0% ಪ್ಲಾಟ್‌ಫಾರ್ಮ್ ಕಮಿಷನ್, 64.2% ನಿವ್ವಳ ಲಾಭ.\\n- **ಪರಿಹಾರ**: ಅಮೆಜಾನ್ ರಿಪೀಟ್ ಗ್ರಾಹಕರನ್ನು ವಾಟ್ಸಾಪ್‌ಗೆ ವರ್ಗಾಯಿಸಿ."
            elif lang == "hi":
                spoken = "अमेज़न पर 15% कमीशन और 18% रिटर्न खर्च के कारण मुनाफा कम हो रहा है। व्हाट्सएप डायरेक्ट पर आपको पूरा 64.2% मार्जिन मिलता है।"
                markdown = "### 📉 लाभ विश्लेषण\\n- **अमेज़न लीकेज**: 15% कमीशन + ₹25 फीस + 18% RTO रिटर्न खर्च।\\n- **व्हाट्सएप डायरेक्ट**: 0% कमीशन, 64.2% नेट मार्जिन।\\n- **समाधान**: मार्केटप्लेस ग्राहकों को पार्सल में क्यूआर कोड देकर व्हाट्सएप पर शिफ्ट करें।"
            else:
                spoken = "Your overall profit is diluted by Amazon India where 15% platform fees and 18% return rates reduce margins to 39.4%, whereas WhatsApp Direct delivers 64.2%."
                markdown = "### 📉 Profit Dilution Diagnosis\\n- **Marketplace Drag**: Amazon takes 15% referral fee + ₹25 closing fee + 18% RTO overhead.\\n- **Direct Channel Arbitrage**: WhatsApp Direct retains 64.2% gross margin.\\n- **Action**: Shift repeat buyers from Amazon to WhatsApp Direct using package inserts."
            return spoken, markdown, tool_data, None, det_traces

        elif intent == "CASUAL_MENTION":
            det_traces.append("conversational:casual_mention")
            if lang == "kn":'''

c = code.replace("\r\n", "\n")
t = target.replace("\r\n", "\n")
r = replacement.replace("\r\n", "\n")

if t in c:
    c = c.replace(t, r, 1)
    with open("services/agent/doctor_advisor.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("SUCCESS: Added CORRECTION, ACTION_PLAN, and PROFIT_LOW_DIAGNOSIS fallback handlers")
else:
    print("ERROR: Target not found")
