# Rule-Based Interactive Terminal Chatbot

A customer-support chatbot built with **Python 3**, **`re`** (regex) and **`json`** only — no external libraries.

## Features
- Intent recognition with keywords + regular expressions (scored matching)
- **Multi-intent** replies (e.g. "what are your hours and shipping time?" answers both)
- Business-hours answers with a live open / closed status
- FAQ knowledge base loaded from `faq.json` (also accepts a plain `[{"question", "answer"}]` list)
- Conversation state management: greeting -> listening -> resolution -> exit
- Contextual follow-ups ("tell me more")
- Graceful fallbacks with a help menu after repeated misses
- Clean exit with `bye`, `exit` or `quit`

## Run
```bash
python chatbot.py                  # uses faq.json
python chatbot.py sample_faq.json  # use the internship sample dataset
```

## Dataset format (`faq.json`)
```json
{"intents": [{
  "intent": "returns",
  "keywords": ["return", "refund"],
  "patterns": ["\\bsend (it )?back\\b"],
  "response": "You can return items within 30 days.",
  "followup": "Go to My Orders to print a return label."
}]}
```

## Example
```
You : what are your hours and shipping time?
Nova: Our business hours: ... Standard shipping takes 3-5 business days ...
You : bye
Nova: Thanks for chatting with TechNest. Goodbye!
```
