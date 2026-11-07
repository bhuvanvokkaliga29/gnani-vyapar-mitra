from services.agent.doctor_advisor import DoctorAdvisorAgent

agent = DoctorAdvisorAgent()
queries = [
    "ಆ product stock ಎಷ್ಟಿದೆ?",
    "product stock estide",
    "its stock",
    "ಆ ಪ್ರಾಡಕ್ಟ್ ಸ್ಟಾಕ್ ಎಷ್ಟು?",
    "इसका स्टॉक कितना है?",
    "What is its stock?",
    "stock estu"
]
for q in queries:
    print(f'"{q}" -> {agent._classify_intent(q)}')

