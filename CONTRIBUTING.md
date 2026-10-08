# Contributing to ReliefRank

Thank you for helping. The most useful contribution is a **language pack**, which lets ReliefRank read rescue messages in another language without changing any core code.

## Add a language pack

1. Copy `packs/en/` to `packs/<code>/`, using the ISO 639-1 code (for example `ml` for Malayalam or `ta` for Tamil).
2. Edit the files in your new folder:

| File | What to put in it |
| --- | --- |
| `pack.json` | Language name, code, version and your name as maintainer |
| `examples.json` | About 6 example messages in your language, each with the correct extracted fields. These are the few-shot examples Gemma sees. |
| `areas.json` | Place names for your region, with spelling variants in `aliases` and approximate `lat`/`lon` |
| `call_script.txt` | The phone-call script, translated. Keep the `[section]` names unchanged; `{about}` must stay in `[opening]`. |
| `tests.json` | At least 20 messages with expected fields, used by `eval/evaluate.py` |

3. Use the exact field names from `reliefrank/models.py`: `people_count`, `vulnerable`, `trapped`, `water_level`, `location_text`, `phone`.
4. Set `PACK = "<code>"` at the top of `eval/evaluate.py` and run it. Include the numbers from `eval/results.md` in your pull request.
5. Open a pull request titled `Add <language> language pack`.

## Rules for test data

- Write synthetic messages. Never use real people's names, phone numbers or messages from a real disaster.
- Use placeholder phone numbers and mark the file as synthetic in its `note` field.

## Other contributions

- Bug fixes and tests are welcome. Run the tests in `tests/` before opening a pull request.
- Keep the design rule: the model only **reads** messages; ranking stays in transparent code in `reliefrank/score.py`.
- Never commit secrets. Put API keys in `.env`, which is not tracked; see `.env.example`.

By contributing, you agree that your contribution is licensed under the Apache License 2.0.
