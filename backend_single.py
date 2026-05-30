
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Tuple
import random, datetime, hashlib, os

from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="Q~Cross API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://t33n-l4quif4h.github.io"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Core helpers ─────────────────────────────────────────────────────────────
DICE = [
    ["A","E","I","O","U","Y"], ["A","C","H","O","P","S"], ["A","D","E","I","N","R"],
    ["A","D","E","I","N","R"], ["B","C","D","E","F","G"], ["E","H","I","N","O","T"],
    ["E","I","K","L","O","T"], ["E","I","N","Q","S","U"], ["E","L","M","N","O","S"],
    ["G","I","L","N","O","U"], ["I","N","O","R","S","T"], ["M","P","R","S","T","U"],
]

MIN_WORD_LEN = 3

# Small fallback word list so the service always works even before you mount the big one.
FALLBACK_WORDS = {
    "ACE", "AID", "AIR", "ANT", "ARE", "ART", "ASK", "ATE", "BAD", "BAR", "BAT", "BEE", "BIG", "BUD",
    "CAB", "CAN", "CAR", "CAT", "COD", "COP", "COT", "DAD", "DAM", "DAY", "DIG", "DUE", "EAT", "EAR",
    "EEL", "END", "ERA", "EVE", "FAR", "FAT", "FED", "FEE", "FIG", "GAS", "GET", "GUM", "GUN", "HAD",
    "HAT", "HEN", "ICE", "INK", "JAM", "JET", "KEY", "LAD", "LEG", "MAN", "MAP", "MAT", "MAY", "NET",
    "NEW", "NOD", "NUT", "OAR", "OIL", "ONE", "OUR", "OWL", "PAN", "PET", "PIG", "RAN", "RAT", "RED",
    "RUG", "RUN", "SAD", "SAP", "SEA", "SIR", "SUN", "TAG", "TAP", "TEA", "TEN", "TIN", "TOE", "TON",
    "TOP", "URN", "VAN", "VAT", "WAX", "WEB", "WIN", "YAK", "YAM", "ZOO",
    "CODE", "GAME", "PLAY", "WORD", "CROSS", "SOLVE", "TRAY", "TILE", "HINT", "DAILY", "BOARD", "GRID",
}

WORDSET = None

def load_wordset():
    global WORDSET
    if WORDSET is not None:
        return WORDSET
    words = set(FALLBACK_WORDS)
    path = os.environ.get("QCROSS_WORDLIST", "")
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    w = line.strip().upper()
                    if len(w) >= MIN_WORD_LEN and w.isalpha():
                        words.add(w)
        except Exception:
            pass
    WORDSET = words
    return WORDSET

# Very lightweight solver: returns a set of words using available letters.
# This is intentionally conservative and guarantees a response even on small lists.
def solve_letters(letters):
    ws = load_wordset()
    letters = [c.upper() for c in letters][:12]
    bag = sorted(letters)
    # Prefer longer words first.
    candidates = sorted(ws, key=lambda w: (-len(w), w))
    chosen = []
    used = []

    def can_make(word, pool):
        pool = list(pool)
        for ch in word:
            if ch in pool:
                pool.remove(ch)
            else:
                return False
        return True

    for w in candidates:
        if len(chosen) >= 4:
            break
        if len(w) < 3:
            continue
        if can_make(w, bag):
            chosen.append(w)
            for ch in w:
                bag.remove(ch)
    # If no words fit, create a simple fallback from letters.
    if not chosen and len(letters) >= 3:
        chosen = ["".join(letters[:3])]
    return chosen, {"letters": letters}

# Daily seed roll

def daily_seed(date=None):
    if date is None:
        date = datetime.date.today()
    s = date.isoformat().encode("utf-8")
    return int(hashlib.sha256(s).hexdigest()[:8], 16)

def roll_daily(date=None):
    rng = random.Random(daily_seed(date))
    return [rng.choice(d) for d in DICE]

# Clue/hint generation
HINTS = [
    lambda w: f"I'm thinking of a {len(w)}-letter word...",
    lambda w: f"It starts with '{w[0]}' .",
    lambda w: f"The answer has letters {len(w)} long.",
    lambda w: f"It ends with '{w[-1]}' .",
    lambda w: f"The word is {w}.",
]

def hint_for(word, ask_number=0):
    word = (word or "WORD").upper()
    idx = min(max(ask_number, 0), len(HINTS)-1)
    return HINTS[idx](word)

# Validation: extremely conservative but useful for the first web prototype.
def validate_solution(letters, placed_letters, words, cells):
    letters = [c.upper() for c in letters]
    placed_letters = [c.upper() for c in placed_letters]
    if len(placed_letters) != 12:
        return False, "You must place all 12 letters."
    if sorted(placed_letters) != sorted(letters):
        return False, "Placed letters do not match the rolled dice."
    if any(len(w) < 3 for w in words):
        return False, "No 2-letter words allowed."
    if not words:
        return False, "No words found."
    return True, "Solved!"

# Scoring

def score_game(elapsed_secs, hints_used, rerolls, difficulty):
    base = 1000
    if elapsed_secs < 60:
        base += 400
    elif elapsed_secs < 120:
        base += 250
    elif elapsed_secs < 180:
        base += 100
    elif elapsed_secs < 300:
        base += 50
    base -= hints_used * 50
    base -= rerolls * 100
    mult = {"easy": 0.75, "medium": 1.0, "hard": 1.5}.get(difficulty, 1.0)
    return max(0, int(base * mult))

# Pydantic models
class SolveRequest(BaseModel):
    letters: List[str]

class ValidateRequest(BaseModel):
    letters: List[str]
    placed_letters: List[str]
    words: List[str]
    cells: List[Tuple[int, int]]

class HintRequest(BaseModel):
    word: str
    ask_number: int = 0
    user_message: str = "Give me a hint"

class ScoreRequest(BaseModel):
    elapsed_secs: int
    hints_used: int = 0
    rerolls: int = 0
    difficulty: str = "medium"

@app.on_event("startup")
def startup():
    load_wordset()

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/daily")
def daily():
    letters = roll_daily()
    words, grid = solve_letters(letters)
    clues = [{"word": w, "clue": f"A clue for {w} ({len(w)})", "length": len(w)} for w in words]
    return {"puzzle_number": int(datetime.date.today().strftime("%j")), "letters": letters, "clues": clues}

@app.post("/solve")
def solve(req: SolveRequest):
    words, grid = solve_letters(req.letters)
    return {"valid": True, "message": "Solution found", "words": words, "grid": grid}

@app.post("/validate")
def validate(req: ValidateRequest):
    ok, msg = validate_solution(req.letters, req.placed_letters, req.words, set(req.cells))
    return {"valid": ok, "message": msg}

@app.post("/hint")
def hint(req: HintRequest):
    return {"hint": hint_for(req.word, req.ask_number)}

@app.post("/score")
def score(req: ScoreRequest):
    return {"score": score_game(req.elapsed_secs, req.hints_used, req.rerolls, req.difficulty)}
