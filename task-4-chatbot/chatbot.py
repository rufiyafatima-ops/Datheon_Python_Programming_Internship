#!/usr/bin/env python3
"""
Rule-Based Interactive Terminal Assistant / Chatbot
---------------------------------------------------
A customer-support chatbot that:
  * loads its knowledge base (intents / FAQs) from a JSON dataset
  * normalizes user input (lowercase, strip whitespace, remove punctuation)
  * recognises intents using keywords + regular expressions (multi-intent)
  * answers business-hours questions with a live "open / closed" status
  * manages conversation state: greeting -> listening -> resolution -> exit
  * handles low-confidence queries with graceful fallbacks
  * exits cleanly on 'bye', 'exit' or 'quit'

Usage:
    python chatbot.py                 # uses faq.json next to this file
    python chatbot.py path/to/faq.json
"""

import json
import random
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # very old Python
    ZoneInfo = None

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
BOT_NAME = "Nova"
COMPANY = "TechNest"
DEFAULT_FAQ_FILE = Path(__file__).with_name("faq.json")

# Business hours as (open_hour, close_hour) in 24h time; None = closed.
# Monday = 0 ... Sunday = 6. Used for the live "open / closed" status.
TIMEZONE = "Asia/Kolkata"   # falls back to the computer's local time if unavailable
BUSINESS_HOURS = {
    0: (9, 18),
    1: (9, 18),
    2: (9, 18),
    3: (9, 18),
    4: (9, 18),
    5: None,
    6: None,
}
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]

MAX_INTENTS_PER_REPLY = 3      # answer up to 3 intents in a single message
MIN_CONFIDENCE = 1.0           # below this score -> fallback
FALLBACK_LIMIT = 2             # after this many fallbacks in a row, show help menu

EXIT_PATTERN = re.compile(r"\b(bye|goodbye|exit|quit)\b")
YES_PATTERN = re.compile(r"\b(yes|yeah|yep|yup|sure|ok|okay|please)\b")
NO_PATTERN = re.compile(
    r"\b(no|nope|nah|nothing|that is all|thats all|that s all|im good|i am good)\b"
)
MORE_PATTERN = re.compile(
    r"\b(more|details|detail|explain|elaborate|tell me more|go on)\b"
)

STOPWORDS = {
    "a", "an", "the", "is", "are", "do", "does", "i", "you", "your", "my",
    "me", "to", "of", "for", "and", "or", "in", "on", "at", "what", "how",
    "can", "it", "this", "that", "with", "about", "be", "if", "there",
    "when", "will", "would", "should", "could", "we", "our", "us", "have",
    "has", "get", "receive", "which", "who", "where", "why", "so", "any",
    "operation", "much", "many",
}

# Conversation states
GREETING, LISTENING, RESOLVED, EXIT = "greeting", "listening", "resolved", "exit"


# --------------------------------------------------------------------------- #
# Built-in fallback dataset (used only if the JSON file cannot be loaded)
# --------------------------------------------------------------------------- #
DEFAULT_INTENTS = [
    {
        "intent": "greeting",
        "keywords": ["hi", "hello", "hey", "good morning", "good evening"],
        "patterns": [r"\bgood (morning|afternoon|evening)\b"],
        "response": [f"Hello! I'm {BOT_NAME}, the {COMPANY} assistant. How can I help?"],
    },
    {
        "intent": "hours",
        "keywords": ["hours", "open", "close", "closing", "timing", "timings"],
        "patterns": [r"\bwhat time\b.*\b(open|close)\b", r"\bbusiness hours\b"],
        "response": ["We are open Mon-Fri 9am-6pm, Sat 10am-4pm, closed Sunday."],
    },
]


# --------------------------------------------------------------------------- #
# Intent model
# --------------------------------------------------------------------------- #
class Intent:
    """One recognisable topic: keywords, regex patterns and response(s)."""

    def __init__(self, name, keywords, patterns, responses, followup=None, label=None):
        self.name = name
        self.label = label or name.replace("_", " ")
        self.keywords = [k.lower() for k in keywords]
        self.patterns = []
        for p in patterns:
            try:
                self.patterns.append(re.compile(p, re.IGNORECASE))
            except re.error:
                print(f"[warning] Invalid regex ignored in intent '{name}': {p}")
        self.responses = responses
        self.followup = followup

    def score(self, text):
        """Confidence score: regex hit = 2 points, keyword hit = 1 point."""
        total = 0.0
        for pattern in self.patterns:
            if pattern.search(text):
                total += 2
        for keyword in self.keywords:
            if re.search(rf"\b{re.escape(keyword)}(s|es)?\b", text):
                total += 1
        return total

    def reply(self):
        if isinstance(self.responses, list):
            return random.choice(self.responses)
        return str(self.responses)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def normalize(text):
    """Lowercase, strip, drop punctuation and collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def keywords_from_question(question):
    """Derive keywords from a plain FAQ question (for simple Q/A datasets)."""
    words = normalize(question).split()
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def load_intents(path):
    """
    Load intents from a JSON file. Supported formats:

    1. {"intents": [ {intent, keywords, patterns, response, followup}, ... ]}
    2. [ {intent, keywords, patterns, response}, ... ]
    3. [ {"question": "...", "answer": "..."}, ... ]   (plain FAQ list)
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        print(f"[warning] '{path}' not found. Using built-in dataset.")
        data = DEFAULT_INTENTS
    except json.JSONDecodeError as err:
        print(f"[warning] '{path}' is not valid JSON ({err}). Using built-in dataset.")
        data = DEFAULT_INTENTS

    intents = []
    if isinstance(data, dict):
        greetings = data.get("greetings") or []
        if greetings:
            intents.append(Intent(
                "greeting", greetings, [],
                ["Hello! How can I help you today?", "Hi there! What can I do for you?"],
            ))
        data = data.get("intents") or data.get("faqs") or data.get("faq") or []

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        name = item.get("intent") or item.get("tag") or item.get("name") or f"faq_{i}"
        response = item.get("response") or item.get("responses") or item.get("answer")
        if not response:
            continue
        keywords = item.get("keywords", [])
        patterns = item.get("patterns", [])
        if not keywords and not patterns and item.get("question"):
            keywords = keywords_from_question(item["question"])
            if re.search(r"\b(hours?|open|opening|timings?)\b", normalize(item["question"])):
                name = "hours"          # enables the live open/closed status
                keywords += ["open", "close", "closing", "timing", "timings"]
        intents.append(Intent(name, keywords, patterns, response,
                              item.get("followup"), item.get("question")))
    return intents


# --------------------------------------------------------------------------- #
# The chatbot
# --------------------------------------------------------------------------- #
class ChatBot:
    def __init__(self, faq_path=DEFAULT_FAQ_FILE):
        self.intents = load_intents(faq_path)
        self.by_name = {intent.name: intent for intent in self.intents}
        self.state = GREETING
        self.last_intent = None
        self.fallback_count = 0

    # ----- business hours (dynamic) ---------------------------------------- #
    @staticmethod
    def now():
        if ZoneInfo:
            try:
                return datetime.now(ZoneInfo(TIMEZONE))
            except Exception:
                pass
        return datetime.now()

    def open_status(self):
        """Tell the user whether the business is open right now."""
        now = self.now()
        today = BUSINESS_HOURS[now.weekday()]
        if today and today[0] <= now.hour < today[1]:
            return f"We're open right now (until {today[1]:02d}:00 today)."
        if today and now.hour < today[0]:
            return f"We're closed right now. We open today at {today[0]:02d}:00."
        for offset in range(1, 8):
            day = (now.weekday() + offset) % 7
            if BUSINESS_HOURS[day]:
                label = "tomorrow" if offset == 1 else DAY_NAMES[day]
                return (f"We're closed right now. We reopen {label} "
                        f"at {BUSINESS_HOURS[day][0]:02d}:00.")
        return "We're closed right now."

    # ----- input classification --------------------------------------------- #
    def is_exit(self, text):
        return bool(EXIT_PATTERN.search(text))

    def match_intents(self, text):
        """Return [(score, intent), ...] sorted best-first, above the threshold."""
        scored = [(intent.score(text), intent) for intent in self.intents]
        scored = [(s, i) for s, i in scored if s >= MIN_CONFIDENCE]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        if not scored:
            return []
        top = scored[0][0]
        # multi-intent: keep intents that score at least half as well as the best
        keep = [(s, i) for s, i in scored if s >= top / 2]
        return keep[:MAX_INTENTS_PER_REPLY]

    # ----- response building ------------------------------------------------ #
    def topics(self):
        labels = [i.label for i in self.intents
                  if i.name not in ("greeting", "thanks", "goodbye")]
        return "; ".join(labels)

    def intent_reply(self, intent):
        if intent.name == "hours":
            return f"{intent.reply()}\n{self.open_status()}"
        return intent.reply()

    def fallback(self):
        self.fallback_count += 1
        if self.fallback_count >= FALLBACK_LIMIT:
            return (
                "I'm still having trouble understanding. I can help with: "
                f"{self.topics()}."
            )
        return random.choice([
            "Sorry, I didn't quite get that. Could you rephrase it?",
            "Hmm, I'm not sure I understand. Try asking about one of my topics, like business hours.",
            "I couldn't find an answer to that. Could you give me a few more details?",
        ])

    def respond(self, raw):
        """Process one user message and return the bot's reply (str)."""
        text = normalize(raw)

        # 1. empty input
        if not text:
            return "Please type something and I'll do my best to help."

        # 2. clean exit commands (always available)
        if self.is_exit(text):
            self.state = EXIT
            return f"Thanks for chatting with {COMPANY}. Goodbye! 👋"

        # 3. state: waiting for "anything else?" answer
        if self.state == RESOLVED:
            if NO_PATTERN.search(text) and not self.match_intents(text):
                self.state = EXIT
                return f"Glad I could help. Thanks for visiting {COMPANY}. Goodbye! 👋"
            if YES_PATTERN.search(text) and not self.match_intents(text):
                self.state = LISTENING
                return "Great, what else would you like to know?"
            self.state = LISTENING  # they asked a new question directly

        # 4. identify intent(s)
        matches = self.match_intents(text)

        # 5. contextual follow-up ("tell me more")
        if not matches and self.last_intent and MORE_PATTERN.search(text):
            intent = self.by_name.get(self.last_intent)
            if intent and intent.followup:
                self.state = RESOLVED
                return f"{intent.followup}\n\nIs there anything else I can help with?"

        # 6. fallback
        if not matches:
            return self.fallback()

        # 7. resolution
        self.fallback_count = 0
        self.last_intent = matches[0][1].name
        replies = [self.intent_reply(intent) for _, intent in matches]
        reply = "\n\n".join(replies)

        only_social = all(i.name in ("greeting", "thanks") for _, i in matches)
        if self.state == GREETING or only_social:
            self.state = LISTENING
            return reply
        self.state = RESOLVED
        return f"{reply}\n\nIs there anything else I can help with?"

    # ----- main loop --------------------------------------------------------- #
    def run(self):
        print("=" * 60)
        print(f"  {COMPANY} Support Assistant  |  type 'bye', 'exit' or 'quit' to leave")
        print("=" * 60)
        print(f"{BOT_NAME}: Hi there! I'm {BOT_NAME}. Ask me about our business hours, "
              "products, shipping, returns and more.")
        self.state = LISTENING

        while self.state != EXIT:
            try:
                user_input = input("You : ")
            except (EOFError, KeyboardInterrupt):
                print(f"\n{BOT_NAME}: Session ended. Goodbye! 👋")
                break
            print(f"{BOT_NAME}: {self.respond(user_input)}\n")


def main():
    faq_file = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FAQ_FILE
    ChatBot(faq_file).run()


if __name__ == "__main__":
    main()
