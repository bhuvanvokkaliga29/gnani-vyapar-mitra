with open('services/agent/doctor_advisor.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# In _deterministic_synthesizer (after line 550)
for idx in range(550, len(lines)):
    if 'def _classify_intent' in lines[idx]:
        break
    if 'return spoken, markdown, tool_data, None, det_traces' in lines[idx]:
        lines[idx] = lines[idx].replace('return spoken, markdown, tool_data, None, det_traces', 'return spoken, markdown, None')
        print(f"Fixed line {idx+1}")
    if 'det_traces.append("conversational:marketing_creation")' in lines[idx]:
        lines[idx] = ""
        print(f"Removed det_traces in line {idx+1}")

with open('services/agent/doctor_advisor.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Finished cleaning _deterministic_synthesizer")

