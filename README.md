# anki-tools

Small command-line tools for maintaining Anki data.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Remove HTML from note fields

Anki must be open with the AnkiConnect add-on enabled. The default scope is the
`Chinese::1 - Vocabulary` deck and its subdecks, using the `Hanzi` field.

```bash
# Preview without modifying notes
anki-clean-html

# Apply the previewed changes
anki-clean-html --apply

# Select another deck and one or more fields
anki-clean-html --deck "Another Deck" --fields Front Back --apply
```

## Scrape simplified Chinese terms

```bash
anki-scrape-simplified --url "https://example.com/frequency-list"
```

## Tests

```bash
python -m unittest discover -s tests -v
```
