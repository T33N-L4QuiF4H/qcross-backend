# Q~Cross Claude Handoff

## Project overview
Q~Cross is a GitHub Pages web game based on Q-Less-style crossword puzzle rules.
The live site is hosted from the `docs/` folder in this repo.
The main app file is `docs/index.html` and it contains the full single-file frontend.

## Repository
- GitHub repo: `https://github.com/T33N-L4QuiF4H/qcross-backend`
- Live site: `https://t33n-l4quif4h.github.io/qcross-backend/`
- Main file: `docs/index.html`

## What to preserve
Do not break or remove any of these existing behaviors unless explicitly requested:
- layout and styles
- audio
- NES/SNES theme toggles
- daily puzzle loading
- hints
- validation logic
- tray selection and board placement
- tap behavior
- drag behavior
- double-tap return-to-tray behavior
- Clear Board

## Current gameplay rules
- Tap a tray die to select it, then tap a board cell to place it.
- Tap a filled cell to select it, then tap another cell to move or swap.
- Double-tap a filled cell to return its tile to the tray.
- Drag tray to board to place a tile.
- Drag board cell to board cell to move or swap.
- Drag board cell to tray to return the tile to the tray.

## Current development priorities
1. Keep the single-file frontend working cleanly on GitHub Pages.
2. Preserve all existing gameplay behaviors.
3. Improve tray-return discoverability and mobile dragging if needed.
4. Keep validation consistent with Q-Less-style rules.

## Q-Less-style constraints
When discussing or implementing validation, keep these rules in mind:
- use all 12 letters
- words must be at least 3 letters long
- no proper nouns or names
- no abbreviations unless explicitly allowed by the puzzle logic

## Working instructions
- Inspect the repo before changing code.
- Prefer the smallest safe change.
- Do not rewrite unrelated sections.
- If a request is ambiguous, ask one focused clarifying question.
- When making edits, explain what behavior changes and what should be tested.

## Important file locations
- `docs/index.html` — main app
- `README.md` — add one if needed for future onboarding

## Suggested first action
Open `docs/index.html`, inspect the current drag/tap logic, and summarize any issues before editing.

## Notes
This project is meant to continue in Claude Code from this handoff without needing repeated setup.
