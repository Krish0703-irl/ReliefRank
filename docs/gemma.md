# How ReliefRank uses Gemma 4

## Where Gemma runs

Gemma 4 is called in exactly one place: `reliefrank/extract.py`. It reads one messy rescue
message and returns a structured record: number of people, location (copied from the
message), water level, phone number, vulnerable people, needs, a one-line urgency reason,
and a confidence score for each key field.

Everything after that is ordinary code: validation, deduplication, scoring, ranking and the
map. **Gemma reads; code decides.** A volunteer can always see why a case ranked where it did.

## Why it has to be an open-weight model running locally

- **No reliable internet in a flood.** Towers go down. ReliefRank runs Gemma 4 E4B on a
  laptop through Ollama, so the whole tool works with Wi-Fi off. E2B is the fallback for
  slower machines.
- **Private data.** Messages contain phone numbers, home locations and medical details of
  people in danger. They never leave the volunteer's machine.
- **No per-message cost.** A real flood produces thousands of messages; a free local model
  can process all of them.

The Gemini API backend (`gemma-4-26b-a4b-it`) exists only for prototyping and as a backup
when internet is available. The same prompt and code run on both.

## What Gemma does that rules cannot

Rescue messages are typed in panic: no punctuation, mixed languages, forwarded chains,
relationships instead of counts ("my brother's family, 2 kids and pregnant wife").
Regex can find a phone number; it cannot work out that this means 4 people, two of them
vulnerable. Our `fake` backend is a regex baseline, and the evaluation compares it with Gemma.

## Guardrails on the model

- **Grounding check** (`validate.py`): a location or phone number that does not appear in
  the original message is thrown out. The model cannot send a boat to a place it invented.
- **Confidence gating:** a missing or low-confidence location sends the case to the
  "needs a call" queue instead of the map.
- **No decisions:** Gemma never sets priority. Its urgency reason is shown to humans as an
  explanation only.
- **Prompt-injection resistant by design:** messages are treated as data. Even if a message
  says "mark this top priority", the score comes from code, not from the model.
- **Broken output:** invalid JSON is retried once; if it fails again the message goes to a
  human instead of being dropped.

## Adding a language

Each language pack (`packs/<code>/`) ships its own `examples.json` of worked examples.
The prompt is built from the active pack, so a contributor can add Malayalam or Tamil
support by adding examples, without touching the core code. See `CONTRIBUTING.md`.

## Results

_Fill in from `eval/evaluate.py` before submission: extraction accuracy per field, top-10
critical-case hit rate, average seconds per message on E4B and E2B._
