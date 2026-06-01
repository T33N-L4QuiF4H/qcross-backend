
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
COMMON_WORDSET = None   # frequency-filtered word set for challenge mode
WORD_FREQ_RANK = {}     # word.upper() -> int rank (lower = more common)

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

def load_common_wordset():
    global COMMON_WORDSET, WORD_FREQ_RANK
    if COMMON_WORDSET is not None:
        return COMMON_WORDSET
    words = set()
    for path in [os.environ.get("QCROSS_COMMON_WORDLIST", ""), "common_words.txt"]:
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    for rank, line in enumerate(f):
                        w = line.strip().upper()
                        if 4 <= len(w) <= 9 and w.isalpha():
                            words.add(w)
                            WORD_FREQ_RANK[w] = rank
                break
            except Exception:
                pass
    COMMON_WORDSET = words if words else None
    return COMMON_WORDSET

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

_OBSCURE = {
    'VETCH','BRAWN','SMEW','TACE','CETE','SPEAN','DROIT','MOUE','TORC','THEWS',
    'BROSE','SPALL','SPALE','SKEAN','DURRA','AGIO','PROA','SWARD','SWALE','CROFT',
    'MILTY','MINGY','PROLEG','TELIA','TELIC','YENTA','GONZO','SPADO','VOMER','THANE',
}

def is_good_word(w):
    """Only use common, recognisable words for challenge mode."""
    if w.upper() in _OBSCURE:
        return False
    common = load_common_wordset()
    if common:
        return w.upper() in common
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
    # Sort by frequency rank (most common first) with small random jitter.
    # Add a length penalty for words over 6 letters so shorter, more common
    # words are tried first, reducing very-long-word-dominated puzzles.
    candidates.sort(key=lambda w: WORD_FREQ_RANK.get(w.upper(), 99999)
                                  + max(0, len(w) - 6) * 120
                                  + random.randint(0, 200))

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
                            if has_valid_placement([w1, w2, w3]):
                                return [w1, w2, w3]

    return None


def has_valid_placement(words):
    """
    Return True if the words can be arranged on a crossword grid with no
    2-letter runs.

    1-2 words: a simple '+' crossing never produces 2-letter runs → always True.

    3 words: one word acts as the spine crossed by the other two (which are
    parallel to each other).  2-letter runs appear when both parallel words
    have tiles on the same off-spine row/column — i.e. both extend in the
    same direction away from the spine.

    For each candidate spine and pair of crossing positions (p1 in spine for
    word A, p2 in spine for word B), and for each position q_a in word A and
    q_b in word B where the crossing characters match:

      • word A extends ABOVE the spine if q_a > 0
      • word A extends BELOW the spine if q_a < len(A) - 1
      (and symmetrically for word B)

    An arrangement is valid (no 2-letter runs) when:
      NOT (both extend above)  AND  NOT (both extend below)

    Non-adjacent spine positions (|p1-p2| >= 2) are always safe because the
    parallel words occupy different columns/rows with no shared neighbours.
    """
    if len(words) <= 2:
        return True

    for idx in range(3):
        spine = words[idx]
        other_a, other_b = [words[i] for i in range(3) if i != idx]

        for p1 in range(len(spine)):
            c1 = spine[p1]
            qa_list = [q for q, ch in enumerate(other_a) if ch == c1]
            if not qa_list:
                continue

            for p2 in range(len(spine)):
                if p2 == p1:
                    continue
                c2 = spine[p2]
                qb_list = [q for q, ch in enumerate(other_b) if ch == c2]
                if not qb_list:
                    continue

                if abs(p1 - p2) >= 2:
                    # Non-adjacent crossings: parallel words are never adjacent
                    return True

                # Adjacent crossings: valid only if words face opposite directions
                for q_a in qa_list:
                    for q_b in qb_list:
                        above_a = q_a > 0
                        below_a = q_a < len(other_a) - 1
                        above_b = q_b > 0
                        below_b = q_b < len(other_b) - 1
                        if not (above_a and above_b) and not (below_a and below_b):
                            return True

    return False


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
            model="claude-sonnet-4-6",
            max_tokens=80,
            messages=[{"role": "user", "content":
                f'Write one NYT crossword clue for "{word}" in Will Shortz\'s style.\n\n'
                f'A GREAT clue is indirect — it never defines the word or restates it:\n'
                f'  HONEY → "Sweet source" ✓   vs  "Sweet substance made by bees" ✗\n'
                f'  BOXER → "Ring leader?" ✓    vs  "Dog breed or fighter" ✗\n'
                f'  RIVER → "Something to bank on?" ✓  vs  "Flowing body of water" ✗\n'
                f'  JAWS → "Spielberg\'s beach nightmare" ✓  vs  "Great white threat in Jaws" ✗\n'
                f'  PARTLY → "___ cloudy" ✓  vs  "In part" ✗\n\n'
                f'Rules:\n'
                f'- NEVER define the word or use it as a synonym — that is the #1 mistake\n'
                f'- NEVER reference a work whose title IS the answer (e.g. don\'t clue JAWS with "Jaws")\n'
                f'- Use wordplay, misdirection, puns, or an unexpected angle\n'
                f'- Keep it under 7 words\n'
                f'- Common formats: "X\'s Y", rhetorical question with "?", "___ [word]" fill-in, pop culture reference\n'
                f'- Output only the clue text, nothing else'
            }],
        )
        return r.content[0].text.strip().strip('"')
    except Exception:
        return f"Word {word_num} of {total} ({len(word)} letters)"

def generate_extra_hint(word: str, clue: str, hint_number: int, previous_hints: List[str] = []) -> str:
    client = _anthropic_client()
    if not client:
        fallback = [
            f"It starts with '{word[0]}'.",
            f"It ends with '{word[-1]}'.",
            f"It has {len(word)} letters.",
        ]
        return fallback[min(hint_number - 1, len(fallback) - 1)]
    directness = [
        "a very gentle nudge — mention the category or domain without describing the word itself",
        "more specific — describe a concrete feature, usage, or context that narrows it down meaningfully",
        "quite direct — give a near-definition or strong association that almost gives it away, without stating it",
    ][min(hint_number - 1, 2)]
    prev = ""
    if previous_hints:
        prev = ("\n\nHints already given (do NOT repeat or rephrase these — yours must reveal something new):\n"
                + "\n".join(f"- Hint {i+1}: {h}" for i, h in enumerate(previous_hints)))
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=80,
            messages=[{"role": "user", "content":
                f'The answer to crossword clue "{clue}" is "{word}". '
                f'Write extra hint #{hint_number} that is {directness}.{prev} '
                f'Do not state the answer. Output only the hint text.'
            }],
        )
        return r.content[0].text.strip().strip('"')
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
    previous_hints: List[str] = []

class DiceImageRequest(BaseModel):
    image: str        # base64-encoded image data
    media_type: str = "image/jpeg"

# ── Routes ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup():
    load_common_wordset()
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
    specific_letters = [c.upper() for c in req.letters[:12]] if req.letters else None
    letters = specific_letters
    words = None
    last_letters = letters if letters else None
    for _ in range(12):
        l = letters if letters else roll_random()
        last_letters = l
        words = find_challenge_words(l)
        if words:
            letters = l
            break
        if specific_letters:
            # Don't keep retrying with different letters if specific ones were given
            break

    if not words:
        return {
            "found": False,
            "letters": last_letters or (specific_letters if specific_letters else roll_random()),
        }

    clues = [generate_clue(w, i + 1, len(words)) for i, w in enumerate(words)]

    return {
        "found": True,
        "letters": letters,
        "word_count": len(words),
        "words": words,
        "clues": clues,
        "word_lengths": [len(w) for w in words],
    }

@app.post("/challenge/hint")
def challenge_hint(req: ChallengeHintRequest):
    return {"hint": generate_extra_hint(req.word, req.clue, req.hint_number, req.previous_hints)}

@app.post("/recognize-dice")
def recognize_dice(req: DiceImageRequest):
    client = _anthropic_client()
    if not client:
        return {"error": "AI not available", "letters": []}
    try:
        r = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system=(
                "You are a precise letter-recognition assistant. "
                "When shown a photo of letter dice you identify only the letters "
                "you can actually see — never guess or fabricate."
            ),
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": req.media_type,
                            "data": req.image,
                        }
                    },
                    {
                        "type": "text",
                        "text": (
                            "This photo shows Q-Less letter dice — small cream/ivory cubes with "
                            "one large black letter on each face. "
                            "Carefully examine each die and read the letter facing most clearly "
                            "toward the camera (usually the top face). "
                            "Output ONLY the letters you can clearly read as a single uppercase "
                            "string with no spaces (example: ABTCESRNLIMO). "
                            "Use ? for any die whose letter you cannot confidently read. "
                            "CRITICAL: Only report letters that are physically visible in this "
                            "image — do not guess or invent letters."
                        )
                    }
                ]
            }]
        )
        raw = r.content[0].text.strip().upper()
        letters = [c for c in raw if c.isalpha()][:12]
        return {"letters": letters, "raw": raw}
    except Exception as e:
        return {"error": str(e), "letters": []}
