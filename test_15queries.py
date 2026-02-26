"""Quick test: simulate a 15-question call to verify long-call support."""

import knowledge_base as kb
import llm

kb.init_kb()

questions = [
    "What programs does IST offer",
    "What is the fee for aerospace engineering",
    "How is merit calculated",
    "Does IST accept A-level students",
    "Is there a hostel for girls",
    "What is the last date to apply",
    "Does IST offer BS AI",
    "What is the fee for computer science",
    "Is there transport facility",
    "Can I pay fee in installments",
    "What is the eligibility for electrical engineering",
    "Does IST have a cafeteria",
    "What about scholarships",
    "When is the challan deadline",
    "What entry test is needed",
]

history = []
ok_count = 0
esc_count = 0

for i, q in enumerate(questions):
    ctx = kb.search(q)
    ans = llm.generate_answer(q, ctx, history)
    history.append({"user": q, "assistant": ans})
    is_esc = "forward your query" in ans.lower()
    if is_esc:
        esc_count += 1
    else:
        ok_count += 1
    tag = "ESCALATED" if is_esc else "OK"
    print("Q{}: {} [{}]".format(i + 1, q, tag))
    print("A{}: {}".format(i + 1, ans[:150]))
    print()

print("=" * 50)
print("DONE: {}/{} answered from KB, {} escalated".format(ok_count, len(questions), esc_count))
