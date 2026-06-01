
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Tuple, Optional
import random, datetime, hashlib, os
from collections import Counter, defaultdict

try:
    from anthropic import Anthropic as _Anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

app = FastAPI(title="Q~Cross API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Dice ─────────────────────────────────────────────────────────────────────
DICE = [
    ["M","M","L","L","B","Y"],["V","E","G","K","P","P"],["H","H","N","N","R","R"],
    ["D","F","R","L","L","W"],["R","R","D","L","G","G"],["X","K","B","S","Z","N"],
    ["W","H","H","T","T","P"],["C","C","B","T","J","D"],["C","C","M","T","T","S"],
    ["O","I","I","N","N","Y"],["A","E","I","O","U","U"],["A","A","E","E","O","O"],
]

MIN_WORD_LEN = 3

FALLBACK_WORDS = {
    "ACE","AID","AIR","ANT","ARE","ART","ATE","BAR","BAT","BEE","BIG",
    "CAB","CAN","CAR","CAT","DAD","DAY","DIG","EAR","EAT","END","ERA",
    "FAR","FAT","FEE","GAS","HAT","ICE","JAM","KEY","LAD","LEG","MAN",
    "MAP","MAT","NET","NUT","OAR","OIL","PAN","PET","RAN","RAT","RUN",
    "SAD","SEA","SUN","TAP","TEA","TEN","TOP","VAN","WIN",
    "GAME","PLAY","WORD","CROSS","SOLVE","TRAY","TILE","HINT","BOARD","GRID",
    "CODE","SALE","TALE","LAKE","RATE","CARE","DARE","HARE","MARE","RARE",
}

# ── Word list ─────────────────────────────────────────────────────────────────
WORDSET = None
WORD_BY_SORTED = None   # ''.join(sorted(word)) -> [word, ...]

def load_wordset():
    global WORDSET
    if WORDSET is not None:
        return WORDSET
    words = set(FALLBACK_WORDS)
    for path in [os.environ.get("QCROSS_WORDLIST", ""), "docs/enable1.txt", "enable1.txt"]:
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        w = line.strip().upper()
                        if MIN_WORD_LEN <= len(w) <= 12 and w.isalpha():
                            words.add(w)
                break
            except Exception:
                pass
    WORDSET = words
    return WORDSET

def build_lookup():
    global WORD_BY_SORTED
    if WORD_BY_SORTED is not None:
        return WORD_BY_SORTED
    d = defaultdict(list)
    for w in load_wordset():
        d["".join(sorted(w))].append(w)
    WORD_BY_SORTED = dict(d)
    return WORD_BY_SORTED

# ── Challenge word-finding ────────────────────────────────────────────────────

def skey(letters):
    """Canonical sorted-letter key for a collection of letters."""
    return "".join(sorted(c.upper() for c in letters))

def is_good_word(w):
    """Prefer 4-9-letter words for challenge mode (less obscure range)."""
    return 4 <= len(w) <= 9

def fits_in(small: Counter, big: Counter) -> bool:
    """True if small is a sub-multiset of big."""
    return not (small - big)

def find_challenge_words(letters, max_w1: int = 400):
    """
    Find 1-3 words whose tiles cover all 12 exactly, as a valid crossword.

    In a crossword, an intersection tile is shared between two words — it is
    placed once and counted once.  So for two words of lengths L1 and L2
    crossing at N points:  L1 + L2 - N = 12.

    Returns a list of words, or None if no combination is found.
    """
    lookup = build_lookup()
    bag = Counter(c.upper() for c in letters)

    # All good words formable from bag
    candidates = [
        w for wlist in lookup.values() for w in wlist
        if is_good_word(w) and fits_in(Counter(w), bag)
    ]
    random.shuffle(candidates)

    # ── 1 word (all 12 letters) ──────────────────────────────────────────────
    for w in lookup.get(skey(letters), []):
        if is_good_word(w):
            return [w]

    # ── 2 words ──────────────────────────────────────────────────────────────
    # With N crossings: len(W1) + len(W2) - N = 12  (N = 1 or 2)
    for w1 in candidates[:max_w1]:
        rest = bag - Counter(w1)
        chars = list(set(w1))

        # 1 crossing
        for c in chars:
            w2_bag = rest + Counter({c: 1})
            k = "".join(sorted(w2_bag.elements()))
            for w2 in lookup.get(k, []):
                if w2 != w1 and is_good_word(w2) and c in w2:
                    return [w1, w2]

        # 2 crossings (two distinct shared letters)
        for i, c1 in enumerate(chars):
            for c2 in chars[i + 1:]:
                w2_bag = rest + Counter({c1: 1, c2: 1})
                k = "".join(sorted(w2_bag.elements()))
                for w2 in lookup.get(k, []):
                    if w2 != w1 and is_good_word(w2) and c1 in w2 and c2 in w2:
                        return [w1, w2]

    # ── 3 words, 2 crossings ─────────────────────────────────────────────────
    # W1 placed → W2 crosses W1 at c1 → W3 crosses W1 or W2 at c2.
    # Tiles placed: len(W1) + (len(W2)-1) + (len(W3)-1) = 12
    for w1 in candidates[:max_w1 // 2]:
        rest1 = bag - Counter(w1)

        for c1 in set(w1):
            w2_pool = rest1 + Counter({c1: 1})
            w2_cands = [
                w for w in candidates
                if w != w1 and c1 in w and fits_in(Counter(w), w2_pool)
            ][:15]

            for w2 in w2_cands:
                w2_new = Counter(w2) - Counter({c1: 1})
                if not fits_in(w2_new, rest1):
                    continue
                rest2 = rest1 - w2_new

                for c2 in set(w1) | set(w2):
                    if c2 == c1:
                        continue
                    w3_bag = rest2 + Counter({c2: 1})
                    if sum(w3_bag.values()) < MIN_WORD_LEN:
                        continue
                    k3 = "".join(sorted(w3_bag.elements()))
                    for w3 in lookup.get(k3, []):
                        if w3 not in (w1, w2) and is_good_word(w3) and c2 in w3:
                            return [w1, w2, w3]

    return None

# ── Claude clue generation ────────────────────────────────────────────────────

def _anthropic_client():
    if not _HAS_ANTHROPIC:
        return None
    key = os.environ.get("ANTHROPIC_API_KEY")
    return _Anthropic(api_key=key) if key else None

def generate_clue(word: str, word_num: int, total: int) -> str:
    client = _anthropic_client()
    if not client:
        return f"Word {word_num} of {total} ({len(word)} letters)"
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{"role": "user", "content":
                f'Write a single Will Shortz-style NYT crossword clue for the word "{word}". '
                f'Be clever and indirect — no obvious synonyms, use wordplay or misdirection. '
                f'Do NOT mention the word length or spell out the word. Output only the clue.'
            }],
        )
        return r.content[0].text.strip().strip('"')
    except Exception:
        return f"Word {word_num} of {total} ({len(word)} letters)"

def generate_extra_hint(word: str, clue: str, hint_num: int) -> str:
    client = _anthropic_client()
    if not client:
        fallback = [
            f"It starts with '{word[0]}'.",
            f"It has {len(word)} letters.",
            f"It ends with '{word[-1]}'.",
        ]
        return fallback[min(hint_num - 1, len(fallback) - 1)]
    directness = [
        "a gentle nudge that doesn't give much away",
        "moderately helpful — narrows it down significantly",
        "very direct, almost giving the answer away — but stop short of stating it",
    ][min(hint_num - 1, 2)]
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{"role": "user", "content":
                f'The answer to crossword clue "{clue}" is "{word}". '
                f'Write extra hint #{hint_num} that is {directness}. '
                f'Do not state the answer directly. Output only the hint text.'
            }],
        )
        return r.content[0].text.strip()
    except Exception:
        return f"It starts with '{word[0]}'."

# ── Legacy helpers (unchanged) ────────────────────────────────────────────────

def solve_letters(letters):
    ws = load_wordset()
    letters = [c.upper() for c in letters][:12]
    bag = sorted(letters)
    candidates = sorted(ws, key=lambda w: (-len(w), w))
    chosen = []

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
    if not chosen and len(letters) >= 3:
        chosen = ["".join(letters[:3])]
    return chosen, {"letters": letters}

def daily_seed(date=None):
    if date is None:
        date = datetime.date.today()
    s = date.isoformat().encode("utf-8")
    return int(hashlib.sha256(s).hexdigest()[:8], 16)

def roll_daily(date=None):
    rng = random.Random(daily_seed(date))
    return [rng.choice(d) for d in DICE]

def roll_random():
    return [random.choice(d) for d in DICE]

HINTS = [
    lambda w: f"I'm thinking of a {len(w)}-letter word...",
    lambda w: f"It starts with '{w[0]}'.",
    lambda w: f"The answer has {len(w)} letters.",
    lambda w: f"It ends with '{w[-1]}'.",
    lambda w: f"The word is {w}.",
]

def hint_for(word, ask_number=0):
    word = (word or "WORD").upper()
    idx = min(max(ask_number, 0), len(HINTS) - 1)
    return HINTS[idx](word)

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

def score_game(elapsed_secs, hints_used, rerolls, difficulty):
    base = 1000
    if elapsed_secs < 60:   base += 400
    elif elapsed_secs < 120: base += 250
    elif elapsed_secs < 180: base += 100
    elif elapsed_secs < 300: base += 50
    base -= hints_used * 50
    base -= rerolls * 100
    mult = {"easy": 0.75, "medium": 1.0, "hard": 1.5}.get(difficulty, 1.0)
    return max(0, int(base * mult))

# ── Pydantic models ───────────────────────────────────────────────────────────

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

class ChallengeRequest(BaseModel):
    letters: Optional[List[str]] = None

class ChallengeHintRequest(BaseModel):
    word: str
    clue: str
    hint_number: int = 1

# ── Routes ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    build_lookup()

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/daily")
def daily():
    letters = roll_daily()
    words, _ = solve_letters(letters)
    clues = [{"word": w, "clue": f"A clue for {w} ({len(w)})", "length": len(w)} for w in words]
    return {
        "puzzle_number": int(datetime.date.today().strftime("%j")),
        "letters": letters,
        "clues": clues,
    }

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

@app.post("/challenge")
def challenge(req: ChallengeRequest):
    # Use provided letters or roll new ones; retry up to 12 times to find a combo
    letters = [c.upper() for c in req.letters[:12]] if req.letters else None
    words = None
    for _ in range(12):
        l = letters if letters else roll_random()
        words = find_challenge_words(l)
        if words:
            letters = l
            break

    if not words:
        # Absolute fallback: use legacy greedy solver
        if not letters:
            letters = roll_random()
        words, _ = solve_letters(letters)

    clues = [generate_clue(w, i + 1, len(words)) for i, w in enumerate(words)]

    return {
        "letters": letters,
        "word_count": len(words),
        "words": words,
        "clues": clues,
        "word_lengths": [len(w) for w in words],
    }

@app.post("/challenge/hint")
def challenge_hint(req: ChallengeHintRequest):
    return {"hint": generate_extra_hint(req.word, req.clue, req.hint_number)}
