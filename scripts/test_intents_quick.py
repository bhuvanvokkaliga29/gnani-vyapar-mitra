import sys, os
sys.path.insert(0, os.path.abspath("."))
from services.agent.doctor_advisor import DoctorAdvisorAgent

agent = DoctorAdvisorAgent()
queries = [
    "मुनाफा कम क्यों है?",
    "कल मुझे क्या करना चाहिए?",
    "पिछला उत्तर सही करो।",
    "ನಾಳೆ ನಾನು ಏನು ಮಾಡಬೇಕು?",
    "ಲಾಭ ಏಕೆ ಕಡಿಮೆಯಾಗಿದೆ?",
    "ಹಿಂದಿನ ಉತ್ತರ ಸರಿಪಡಿಸು"
]
for q in queries:
    print(f'"{q}" -> {agent._classify_intent(q)}')

