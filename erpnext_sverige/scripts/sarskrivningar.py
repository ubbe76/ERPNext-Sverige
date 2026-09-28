"""Hitta svenska översättningar med särskrivningar eller engelska versaler.

Läser sv.po för frappe och erpnext, lägger på erpnext_sverige/locale/sv.po och listar
poster där fler än första ordet har stor bokstav, t.ex. "Resultat Enhet".

Körs efter uppdatering av frappe/erpnext för att hitta nya strängar att rätta:

    bench --site <site> execute erpnext_sverige.scripts.sarskrivningar.report
    bench --site <site> execute erpnext_sverige.scripts.sarskrivningar.report --kwargs "{'output': '/tmp/sv.json'}"
"""

import json
import re

import frappe
from babel.messages.pofile import read_po

SOURCE_APPS = ("frappe", "erpnext")
TOKEN = re.compile(r"\{[^}]*\}|%\(?\w*\)?[sd]|<[^>]+>|&\w+;")
WORD = re.compile(r"[A-Za-zÅÄÖåäöÉéÜü][\wÅÄÖåäöÉéÜü\-]*")
SENTENCE_START = ".!?:\n(\"'«–-•*"  # noqa: RUF001

# Egennamn och produktnamn som får ha stor bokstav mitt i en mening
PROPER_NOUNS = {
	"ERPNext",
	"Frappe",
	"Google",
	"Microsoft",
	"Stripe",
	"Plaid",
	"Slack",
	"DocType",
	"Sverige",
	"Excel",
	"Markdown",
	"Jinja",
	"Python",
	"JavaScript",
	"Webhook",
	"GitHub",
	"Dropbox",
	"Gmail",
	"Outlook",
	"Kalender",
	"Kontakter",
	"Drive",
	"Sheets",
	"Cloud",
	"Mail",
	"Gallon",
	"Cubic",
	"Liter",
	"Ounce",
	"DocTypes",
}
ACRONYM_COMPOUND = re.compile(r"^[A-ZÅÄÖ0-9]{2,}-|^[A-ZÅÄÖ][a-zåäö]+-[A-Za-zåäö]")


def _load(path):
	with open(path, "rb") as f:
		return {
			(m.context or "", m.id): m.string
			for m in read_po(f)
			if m.id and m.string and isinstance(m.id, str)
		}


def capitalized_words(text: str) -> list[str]:
	text = TOKEN.sub(" ", text)
	words = []
	for m in WORD.finditer(text):
		word = m.group()
		before = text[: m.start()].rstrip()
		if not before or before[-1] in SENTENCE_START:
			continue
		if (
			word[0].isupper()
			and not word.isupper()
			and word not in PROPER_NOUNS
			and not ACRONYM_COMPOUND.match(word)
		):
			words.append(word)
	return words


def is_title_case(text: str) -> bool:
	"""Etikett med Stor Bokstav På Varje Ord, t.ex. "Inaktivera Automatiska Senaste Filter"."""
	words = WORD.findall(TOKEN.sub(" ", text))
	return len(words) >= 2 and all(w[0].isupper() for w in words)


def find_candidates(title_case_only: bool = False) -> list[dict]:
	merged = {}
	for app in SOURCE_APPS:
		merged.update(_load(frappe.get_app_path(app, "locale", "sv.po")))
	merged.update(_load(frappe.get_app_path("erpnext_sverige", "locale", "sv.po")))
	return [
		{"ctx": ctx, "msgid": msgid, "msgstr": msgstr, "words": words}
		for (ctx, msgid), msgstr in sorted(merged.items(), key=lambda kv: kv[0][1].lower())
		if (words := capitalized_words(msgstr)) and (not title_case_only or is_title_case(msgstr))
	]


def report(output: str | None = None, title_case_only: bool = False):
	candidates = find_candidates(title_case_only)
	if output:
		with open(output, "w", encoding="utf-8") as f:
			json.dump(candidates, f, ensure_ascii=False, indent=1)
	for c in candidates[:50]:
		print(f"{c['msgid']!r} -> {c['msgstr']!r}")
	print(f"{len(candidates)} kandidater")
