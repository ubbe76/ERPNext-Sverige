> Ändrat 2026-10-01: frakten faktureras som artikelraden Fraktartikel (Fraktinställningar.fraktartikel), inte som skatterad på fraktkonto.

# Transportbokning via Sendify (etapp 1) – implementationsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Boka transporter från ERPNext via Sendify: kolliförslag från artiklar, prisjämförelse, bokning med
fraktsedel, avbokning, spårning, frakt på faktura och prisförfrågan på offert/order.

**Architecture:** Ny modul *Frakt* i `erpnext_sverige` ovanpå ERPNext:s Shipment. `frakt/sendify.py` är den enda
koden som känner till Sendify och tar/ger dict:ar i modulens eget format; `kollin.py` räknar kolliförslag;
`bokning.py`, `fraktpris.py` och `sparning.py` är affärslogiken; JS-filer ger knappar och prisdialog.

**Tech Stack:** Frappe/ERPNext v16, Python 3.14, `requests`, Frappe `IntegrationTestCase`, `unittest.mock`,
vanilla Frappe desk-JS.

**Spec:** `docs/superpowers/specs/2026-10-01-frakt-sendify-design.md`

## Global Constraints

- Allt arbete på grenen `feat/frakt-sendify` i `apps/erpnext_sverige`. Commit-meddelanden på engelska, avslutas med
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Tester körs **bara** på test-erp.local: `bench --site test-erp.local run-tests --app erpnext_sverige --module <modul>`
  (från `~/ERPNext/my-frappe-bench`). Efter nya doctypes/custom fields: `bench --site test-erp.local migrate`.
- Kodstil som resten av appen: tabbindrag, radlängd 110, ruff. Kör `pre-commit run --files <filer>` före commit.
- **Användarsträngar skrivs direkt på svenska** i `_()` / `__()` och i doctype-JSON (så gör appen redan, t.ex.
  `_("Det finns inga momssaldon att föra om för perioden")`). Det ersätter specens rad om engelska strängar.
- **Doctype-namn är ASCII** (som `Leverantorsbetalning`), med svensk visning via `erpnext_sverige/locale/sv.po`:
  `Forpackningstyp` → "Förpackningstyp", `Fraktinstallningar` → "Fraktinställningar", `Fraktprodukt`,
  `Sparningshandelse` → "Spårningshändelse".
- Sendify: sandlåda `https://app.dev.sendify.se/external/v1`, produktion `https://app.sendify.se/external/v1`,
  header `x-api-key`. Enheter cm och kg. API-nyckeln får aldrig loggas.
- Ingen kod utanför `frakt/sendify.py` får importera `requests` eller känna till Sendifys fältnamn.
- Kundpris = pris × (1 + påslag_procent/100) + påslag_belopp, avrundat till hela kronor.
- Flakmeter per pallplats: 0,4.
- Upphämtning beställs alltid (ingen `without_pickup`).

## Review Focus

1. **Mottagare utan kontakt, telefon eller e-post** – Sendify avvisar; användaren ska få en svensk lista över vad
   som saknas, inte ett tekniskt fel. Test i Task 7 (`test_hamta_priser_visar_sendifys_faltfel`).
2. **Dubbelklick på Boka / boka en redan bokad Shipment** – andra anropet ska vägras utan nytt Sendify-anrop.
   Test i Task 8 (`test_bokad_shipment_kan_inte_bokas_igen`).
3. **Artikel såld i annan enhet än lagerenheten** (t.ex. 2 Box à 10 st) – kollin räknas på lagerantal (20 st).
   Test i Task 6 (`test_kollin_raknas_pa_lagerantal`).
4. **Två delfakturor från samma följesedel** – frakten läggs bara på den första. Test i Task 10
   (`test_frakt_laggs_bara_pa_forsta_fakturan`).
5. **Prisalternativet har gått ut eller Sendify vägrar boka** – Shipment ska förbli oförändrat utkast och felet
   visas. Test i Task 8 (`test_misslyckad_bokning_lamnar_utkast`).

---

## Filstruktur

| Fil | Ansvar |
|---|---|
| `erpnext_sverige/modules.txt` | + `Frakt` |
| `erpnext_sverige/frakt/__init__.py` | `FraktFel`, `hamta_installningar()`, `leverantor()`, `visa_fraktfel` |
| `erpnext_sverige/frakt/doctype/forpackningstyp/` | Förpackningstyp |
| `erpnext_sverige/frakt/doctype/fraktprodukt/` | Fraktprodukt |
| `erpnext_sverige/frakt/doctype/sparningshandelse/` | Spårningshändelse (undertabell) |
| `erpnext_sverige/frakt/doctype/fraktinstallningar/` | Fraktinställningar (single) + knappar |
| `erpnext_sverige/frakt/custom_fields.py` | Custom fields för frakt |
| `erpnext_sverige/frakt/kollin.py` | Kolliförslag, viktomräkning, artikelvalidering |
| `erpnext_sverige/frakt/sendify.py` | Sendify-API |
| `erpnext_sverige/frakt/parter.py` | Avsändare/mottagare från Address/Contact, upphämtningstid |
| `erpnext_sverige/frakt/fraktpris.py` | Påslag, Fraktprodukt-register, prisförfrågan, fraktrad på faktura |
| `erpnext_sverige/frakt/bokning.py` | Shipment: skapa, priser, spara val, boka, dokument, avbokning |
| `erpnext_sverige/frakt/sparning.py` | Spårning |
| `erpnext_sverige/public/js/frakt_prisdialog.js` | Gemensam prisdialog |
| `erpnext_sverige/public/js/frakt_shipment.js` | Shipment-knappar |
| `erpnext_sverige/public/js/frakt_forsaljning.js` | Följesedel/order/offert-knappar |
| `erpnext_sverige/setup/custom_fields.py` | slår ihop fraktfälten |
| `erpnext_sverige/hooks.py` | `doctype_js`, `doc_events`, `scheduler_events` |
| `erpnext_sverige/locale/sv.po` | doctype-namn |
| `erpnext_sverige/tests/frakt_utils.py` | testhjälpare för frakt |
| `erpnext_sverige/tests/test_frakt_*.py` | tester |

---

### Task 1: Modul, doctypes och inställningar

**Files:**
- Modify: `erpnext_sverige/modules.txt`
- Create: `erpnext_sverige/frakt/.frappe` (tom), `erpnext_sverige/frakt/__init__.py`,
  `erpnext_sverige/frakt/doctype/__init__.py`
- Create: `erpnext_sverige/frakt/doctype/{forpackningstyp,fraktprodukt,sparningshandelse,fraktinstallningar}/`
  med `__init__.py`, `<namn>.json`, `<namn>.py`
- Modify: `erpnext_sverige/locale/sv.po`
- Test: `erpnext_sverige/tests/test_frakt_doctypes.py`

**Interfaces:**
- Produces: `erpnext_sverige.frakt.FraktFel(meddelande, falt_fel=None, request_id=None)` med `.meddelande`,
  `.falt_fel: list[str]`, `.request_id`, `.som_html() -> str`;
  `hamta_installningar() -> Document` (kastar om inte aktiverad);
  `leverantor() -> module` (returnerar `erpnext_sverige.frakt.sendify`);
  dekoratorn `visa_fraktfel` (fångar `FraktFel` → `frappe.throw(fel.som_html(), title="Sendify")`).
- Doctypes: `Forpackningstyp`, `Fraktprodukt`, `Sparningshandelse`, `Fraktinstallningar` (fält enligt nedan).

- [ ] **Step 1: Lägg till modulen**

`erpnext_sverige/modules.txt` får en ny sista rad:

```
Frakt
```

Skapa den tomma filen `erpnext_sverige/frakt/.frappe` och tomma `erpnext_sverige/frakt/doctype/__init__.py`.

- [ ] **Step 2: Skriv `erpnext_sverige/frakt/__init__.py`**

```python
"""Transportbokning (modul Frakt). Leverantörsspecifik kod finns i sendify.py."""

import functools

import frappe
from frappe import _


class FraktFel(Exception):
	"""Fel från fraktleverantören, med fältfel översatta till svenska."""

	def __init__(self, meddelande, falt_fel=None, request_id=None):
		super().__init__(meddelande)
		self.meddelande = meddelande
		self.falt_fel = falt_fel or []
		self.request_id = request_id

	def som_html(self) -> str:
		rader = [frappe.utils.escape_html(self.meddelande)]
		if self.falt_fel:
			rader.append("<ul>" + "".join(f"<li>{frappe.utils.escape_html(f)}</li>" for f in self.falt_fel) + "</ul>")
		if self.request_id:
			rader.append(_("Referens hos Sendify: {0}").format(self.request_id))
		return "<br>".join(rader)


def hamta_installningar():
	inst = frappe.get_cached_doc("Fraktinstallningar")
	if not inst.aktiverad:
		frappe.throw(
			_("Transportbokning är inte aktiverad. Aktivera den i {0}.").format(
				frappe.utils.get_link_to_form("Fraktinstallningar", "Fraktinstallningar", _("Fraktinställningar"))
			)
		)
	return inst


def leverantor():
	"""Modulen för vald leverantör. Bara Sendify finns i etapp 1."""
	from erpnext_sverige.frakt import sendify

	return sendify


def visa_fraktfel(funktion):
	@functools.wraps(funktion)
	def omslag(*args, **kwargs):
		try:
			return funktion(*args, **kwargs)
		except FraktFel as fel:
			frappe.throw(fel.som_html(), title=_("Sendify"))

	return omslag
```

- [ ] **Step 3: Skapa doctype Förpackningstyp**

`erpnext_sverige/frakt/doctype/forpackningstyp/__init__.py` (tom).

`erpnext_sverige/frakt/doctype/forpackningstyp/forpackningstyp.json`:

```json
{
 "actions": [],
 "autoname": "field:forpackningstyp_namn",
 "creation": "2026-10-01 10:00:00.000000",
 "description": "Pall- och kartongtyper som används för att föreslå kollin.",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": ["forpackningstyp_namn", "kollityp", "stapelbar", "column_break_1", "langd_cm", "bredd_cm", "hojd_cm", "egenvikt_kg", "flakmeter"],
 "fields": [
  {"fieldname": "forpackningstyp_namn", "fieldtype": "Data", "label": "Namn", "reqd": 1, "unique": 1, "in_list_view": 1},
  {"fieldname": "kollityp", "fieldtype": "Select", "label": "Kollityp", "options": "Paket\nPall", "default": "Pall", "reqd": 1, "in_list_view": 1},
  {"fieldname": "stapelbar", "fieldtype": "Check", "label": "Stapelbar", "default": "1"},
  {"fieldname": "column_break_1", "fieldtype": "Column Break"},
  {"fieldname": "langd_cm", "fieldtype": "Float", "label": "Längd (cm)", "reqd": 1, "in_list_view": 1},
  {"fieldname": "bredd_cm", "fieldtype": "Float", "label": "Bredd (cm)", "reqd": 1, "in_list_view": 1},
  {"fieldname": "hojd_cm", "fieldtype": "Float", "label": "Höjd (cm)", "reqd": 1, "in_list_view": 1, "description": "Höjd för full förpackning"},
  {"fieldname": "egenvikt_kg", "fieldtype": "Float", "label": "Egenvikt (kg)"},
  {"fieldname": "flakmeter", "fieldtype": "Float", "label": "Flakmeter", "description": "Lämna tomt för att låta transportören räkna från måtten"}
 ],
 "links": [],
 "modified": "2026-10-01 10:00:00.000000",
 "modified_by": "Administrator",
 "module": "Frakt",
 "name": "Forpackningstyp",
 "naming_rule": "By fieldname",
 "owner": "Administrator",
 "permissions": [
  {"role": "Stock Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
  {"role": "Stock User", "read": 1, "report": 1},
  {"role": "Sales User", "read": 1}
 ],
 "sort_field": "creation",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

`forpackningstyp.py`:

```python
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class Forpackningstyp(Document):
	def validate(self):
		for falt in ("langd_cm", "bredd_cm", "hojd_cm"):
			if flt(self.get(falt)) <= 0:
				frappe.throw(_("{0} måste vara större än noll").format(self.meta.get_label(falt)))
		if flt(self.egenvikt_kg) < 0:
			frappe.throw(_("Egenvikten kan inte vara negativ"))
```

- [ ] **Step 4: Skapa doctype Fraktprodukt**

`fraktprodukt.json`:

```json
{
 "actions": [],
 "creation": "2026-10-01 10:00:00.000000",
 "description": "Transportörsprodukter. Skapas automatiskt när priser hämtas.",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": ["leverantor", "transportorskod", "transportor", "produkt"],
 "fields": [
  {"fieldname": "leverantor", "fieldtype": "Data", "label": "Leverantör", "reqd": 1, "read_only": 1, "default": "Sendify"},
  {"fieldname": "transportorskod", "fieldtype": "Data", "label": "Transportörskod", "read_only": 1},
  {"fieldname": "transportor", "fieldtype": "Data", "label": "Transportör", "reqd": 1, "read_only": 1, "in_list_view": 1, "in_standard_filter": 1},
  {"fieldname": "produkt", "fieldtype": "Data", "label": "Produkt", "reqd": 1, "read_only": 1, "in_list_view": 1}
 ],
 "links": [],
 "modified": "2026-10-01 10:00:00.000000",
 "modified_by": "Administrator",
 "module": "Frakt",
 "name": "Fraktprodukt",
 "naming_rule": "By script",
 "owner": "Administrator",
 "permissions": [
  {"role": "Stock Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1},
  {"role": "Stock User", "read": 1, "create": 1, "report": 1},
  {"role": "Sales User", "read": 1, "create": 1}
 ],
 "sort_field": "creation",
 "sort_order": "DESC",
 "states": [],
 "title_field": "produkt"
}
```

`fraktprodukt.py`:

```python
from frappe.model.document import Document


class Fraktprodukt(Document):
	def autoname(self):
		self.name = f"{self.transportor} – {self.produkt}"
```

- [ ] **Step 5: Skapa doctype Spårningshändelse (undertabell)**

`sparningshandelse.json`:

```json
{
 "actions": [],
 "creation": "2026-10-01 10:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "istable": 1,
 "field_order": ["tidpunkt", "status", "beskrivning", "plats"],
 "fields": [
  {"fieldname": "tidpunkt", "fieldtype": "Datetime", "label": "Tidpunkt", "in_list_view": 1, "columns": 2},
  {"fieldname": "status", "fieldtype": "Data", "label": "Status", "in_list_view": 1, "columns": 2},
  {"fieldname": "beskrivning", "fieldtype": "Data", "label": "Beskrivning", "in_list_view": 1, "columns": 4},
  {"fieldname": "plats", "fieldtype": "Data", "label": "Plats", "in_list_view": 1, "columns": 2}
 ],
 "links": [],
 "modified": "2026-10-01 10:00:00.000000",
 "modified_by": "Administrator",
 "module": "Frakt",
 "name": "Sparningshandelse",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "creation",
 "sort_order": "DESC",
 "states": []
}
```

`sparningshandelse.py`:

```python
from frappe.model.document import Document


class Sparningshandelse(Document):
	pass
```

- [ ] **Step 6: Skapa doctype Fraktinställningar (single)**

`fraktinstallningar.json`:

```json
{
 "actions": [],
 "creation": "2026-10-01 10:00:00.000000",
 "description": "Inställningar för transportbokning via Sendify.",
 "doctype": "DocType",
 "engine": "InnoDB",
 "issingle": 1,
 "field_order": [
  "aktiverad", "leverantor", "miljo", "api_nyckel",
  "avsandare_section", "bolag", "avsandaradress", "avsandarkontakt", "column_break_1", "upphamtning_fran", "upphamtning_till",
  "pris_section", "paslag_procent", "paslag_belopp", "column_break_2", "fraktkonto", "prisandring_grans_procent",
  "sparning_section", "sparning_intervall", "senaste_sparningskorning"
 ],
 "fields": [
  {"fieldname": "aktiverad", "fieldtype": "Check", "label": "Aktiverad"},
  {"fieldname": "leverantor", "fieldtype": "Select", "label": "Leverantör", "options": "Sendify", "default": "Sendify", "reqd": 1},
  {"fieldname": "miljo", "fieldtype": "Select", "label": "Miljö", "options": "Sandlåda\nProduktion", "default": "Sandlåda", "reqd": 1},
  {"fieldname": "api_nyckel", "fieldtype": "Password", "label": "API-nyckel", "description": "Skapas i Sendify under Settings → API"},
  {"fieldname": "avsandare_section", "fieldtype": "Section Break", "label": "Avsändare och upphämtning"},
  {"fieldname": "bolag", "fieldtype": "Link", "label": "Bolag", "options": "Company"},
  {"fieldname": "avsandaradress", "fieldtype": "Link", "label": "Avsändaradress", "options": "Address"},
  {"fieldname": "avsandarkontakt", "fieldtype": "Link", "label": "Avsändarkontakt", "options": "Contact"},
  {"fieldname": "column_break_1", "fieldtype": "Column Break"},
  {"fieldname": "upphamtning_fran", "fieldtype": "Time", "label": "Upphämtning från", "default": "09:00:00"},
  {"fieldname": "upphamtning_till", "fieldtype": "Time", "label": "Upphämtning till", "default": "16:00:00"},
  {"fieldname": "pris_section", "fieldtype": "Section Break", "label": "Fraktpris till kund"},
  {"fieldname": "paslag_procent", "fieldtype": "Percent", "label": "Påslag (%)"},
  {"fieldname": "paslag_belopp", "fieldtype": "Currency", "label": "Påslag (kr)", "options": "SEK"},
  {"fieldname": "column_break_2", "fieldtype": "Column Break"},
  {"fieldname": "fraktkonto", "fieldtype": "Link", "label": "Fraktkonto", "options": "Account", "description": "Konto för fraktraden på order och faktura, normalt 3520"},
  {"fieldname": "prisandring_grans_procent", "fieldtype": "Percent", "label": "Bekräfta prisändring över (%)", "default": "5"},
  {"fieldname": "sparning_section", "fieldtype": "Section Break", "label": "Spårning"},
  {"fieldname": "sparning_intervall", "fieldtype": "Select", "label": "Hämta spårning", "options": "Varje timme\nVar fjärde timme\nDagligen", "default": "Varje timme"},
  {"fieldname": "senaste_sparningskorning", "fieldtype": "Datetime", "label": "Senaste spårningskörning", "read_only": 1}
 ],
 "links": [],
 "modified": "2026-10-01 10:00:00.000000",
 "modified_by": "Administrator",
 "module": "Frakt",
 "name": "Fraktinstallningar",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1},
  {"role": "Stock Manager", "read": 1, "write": 1, "create": 1}
 ],
 "sort_field": "creation",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

`fraktinstallningar.py`:

```python
import frappe
from frappe import _
from frappe.model.document import Document


class Fraktinstallningar(Document):
	def validate(self):
		if not self.aktiverad:
			return
		saknas = [
			self.meta.get_label(falt)
			for falt in ("bolag", "avsandaradress", "fraktkonto")
			if not self.get(falt)
		]
		if not self.api_nyckel:
			saknas.append(self.meta.get_label("api_nyckel"))
		if saknas:
			frappe.throw(_("Fyll i {0} innan transportbokning aktiveras").format(", ".join(saknas)))
		if frappe.db.get_value("Account", self.fraktkonto, "company") != self.bolag:
			frappe.throw(_("Fraktkontot tillhör inte bolaget {0}").format(self.bolag))
```

- [ ] **Step 7: Lägg till doctype-namnen i `locale/sv.po`**

Lägg in posterna i bokstavsordning (filen är sorterad på msgid utan hänsyn till versaler):

```
msgid "Forpackningstyp"
msgstr "Förpackningstyp"

msgid "Fraktinstallningar"
msgstr "Fraktinställningar"

msgid "Sparningshandelse"
msgstr "Spårningshändelse"
```

- [ ] **Step 8: Skriv testet `erpnext_sverige/tests/test_frakt_doctypes.py`**

```python
import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.frakt import FraktFel, hamta_installningar, visa_fraktfel


class TestFraktDoctypes(IntegrationTestCase):
	def test_fraktprodukt_namnges_efter_transportor_och_produkt(self):
		doc = frappe.get_doc(
			{"doctype": "Fraktprodukt", "transportor": "_Test Frakt AB", "produkt": "Paket Express"}
		).insert()
		self.assertEqual(doc.name, "_Test Frakt AB – Paket Express")

	def test_forpackningstyp_kraver_matt(self):
		doc = frappe.get_doc(
			{"doctype": "Forpackningstyp", "forpackningstyp_namn": "_Test noll", "langd_cm": 0, "bredd_cm": 80, "hojd_cm": 100}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_inaktiverade_installningar_ger_fel(self):
		frappe.db.set_single_value("Fraktinstallningar", "aktiverad", 0)
		frappe.clear_document_cache("Fraktinstallningar", "Fraktinstallningar")
		self.assertRaises(frappe.ValidationError, hamta_installningar)

	def test_visa_fraktfel_blir_valideringsfel_med_faltlista(self):
		@visa_fraktfel
		def misslyckas():
			raise FraktFel("Ogiltig sändning", falt_fel=["Kolli 1: vikt: The field is required."], request_id="abc")

		with self.assertRaises(frappe.ValidationError) as fel:
			misslyckas()
		self.assertIn("Kolli 1: vikt", str(fel.exception))
		self.assertIn("abc", str(fel.exception))
```

- [ ] **Step 9: Migrera och kör testerna**

Run:
```bash
cd ~/ERPNext/my-frappe-bench
bench --site test-erp.local migrate
bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_doctypes
```
Expected: 4 tests OK.

- [ ] **Step 10: Commit**

```bash
cd apps/erpnext_sverige
pre-commit run --files erpnext_sverige/modules.txt erpnext_sverige/frakt/__init__.py erpnext_sverige/frakt/doctype/*/* erpnext_sverige/tests/test_frakt_doctypes.py
git add erpnext_sverige/modules.txt erpnext_sverige/frakt erpnext_sverige/locale/sv.po erpnext_sverige/tests/test_frakt_doctypes.py
git commit -m "feat(frakt): add Frakt module with packaging, carrier product and settings doctypes"
```

---

### Task 2: Custom fields och artikelvalidering

**Files:**
- Create: `erpnext_sverige/frakt/custom_fields.py`
- Create: `erpnext_sverige/frakt/kollin.py` (bara `validera_artikel` och konstanter i denna task)
- Modify: `erpnext_sverige/setup/custom_fields.py` (`get_custom_fields`)
- Modify: `erpnext_sverige/hooks.py` (`doc_events["Item"]`)
- Test: `erpnext_sverige/tests/test_frakt_kollin.py`

**Interfaces:**
- Consumes: doctypes från Task 1.
- Produces: custom fields (namn exakt enligt tabellerna nedan); `kollin.EGNA_MATT = "Egna mått"`,
  `kollin.FORPACKNING = "Förpackning"`, `kollin.PALLPLATS_FLAKMETER = 0.4`,
  `kollin.validera_artikel(doc, method=None)`.

- [ ] **Step 1: Skriv `erpnext_sverige/frakt/custom_fields.py`**

```python
"""Custom fields för transportbokning. Slås ihop i setup/custom_fields.get_custom_fields."""

EGNA = "eval:doc.fraktsatt=='Egna mått'"
FORP = "eval:doc.fraktsatt=='Förpackning'"


def get_custom_fields():
	return {
		"Item": [
			{"fieldname": "frakt_section", "label": "Frakt", "fieldtype": "Section Break", "insert_after": "weight_uom"},
			{
				"fieldname": "fraktsatt",
				"label": "Fraktsätt",
				"fieldtype": "Select",
				"options": "\nEgna mått\nFörpackning",
				"insert_after": "frakt_section",
				"description": "Egna mått: artikeln är sitt eget kolli. Förpackning: artikeln packas i en förpackningstyp.",
			},
			{"fieldname": "frakt_kollityp", "label": "Kollityp", "fieldtype": "Select", "options": "Paket\nPall", "default": "Paket", "depends_on": EGNA, "insert_after": "fraktsatt"},
			{"fieldname": "frakt_langd_cm", "label": "Längd (cm)", "fieldtype": "Float", "depends_on": EGNA, "insert_after": "frakt_kollityp"},
			{"fieldname": "frakt_bredd_cm", "label": "Bredd (cm)", "fieldtype": "Float", "depends_on": EGNA, "insert_after": "frakt_langd_cm"},
			{"fieldname": "frakt_hojd_cm", "label": "Höjd (cm)", "fieldtype": "Float", "depends_on": EGNA, "insert_after": "frakt_bredd_cm"},
			{"fieldname": "frakt_column", "fieldtype": "Column Break", "insert_after": "frakt_hojd_cm"},
			{"fieldname": "frakt_stapelbar", "label": "Stapelbar", "fieldtype": "Check", "default": "1", "depends_on": EGNA, "insert_after": "frakt_column"},
			{"fieldname": "frakt_flakmeter", "label": "Flakmeter", "fieldtype": "Float", "depends_on": EGNA, "insert_after": "frakt_stapelbar"},
			{
				"fieldname": "frakt_pallplatser",
				"label": "Pallplatser",
				"fieldtype": "Float",
				"depends_on": EGNA,
				"insert_after": "frakt_flakmeter",
				"description": "Fyller i flakmeter (0,4 per pallplats) om flakmeter är tomt",
			},
			{"fieldname": "forpackningstyp", "label": "Förpackningstyp", "fieldtype": "Link", "options": "Forpackningstyp", "depends_on": FORP, "insert_after": "frakt_pallplatser"},
			{
				"fieldname": "antal_per_forpackning",
				"label": "Antal per förpackning",
				"fieldtype": "Float",
				"depends_on": FORP,
				"insert_after": "forpackningstyp",
				"description": "I lagerenhet",
			},
		],
		"Customer": [
			{"fieldname": "forvald_fraktprodukt", "label": "Förvald fraktprodukt", "fieldtype": "Link", "options": "Fraktprodukt", "insert_after": "default_price_list"},
		],
		"Quotation": [
			{"fieldname": "fraktprodukt", "label": "Fraktprodukt", "fieldtype": "Link", "options": "Fraktprodukt", "read_only": 1, "insert_after": "taxes_and_charges"},
		],
		"Sales Order": [
			{"fieldname": "fraktprodukt", "label": "Fraktprodukt", "fieldtype": "Link", "options": "Fraktprodukt", "read_only": 1, "insert_after": "taxes_and_charges"},
		],
		"Shipment": [
			{"fieldname": "frakt_section", "label": "Fraktbokning", "fieldtype": "Section Break", "insert_after": "tracking_status_info"},
			{"fieldname": "avsandarens_referens", "label": "Avsändarens referens", "fieldtype": "Data", "insert_after": "frakt_section"},
			{"fieldname": "mottagarens_referens", "label": "Mottagarens referens", "fieldtype": "Data", "insert_after": "avsandarens_referens"},
			{"fieldname": "fraktprodukt", "label": "Fraktprodukt", "fieldtype": "Link", "options": "Fraktprodukt", "insert_after": "mottagarens_referens"},
			{"fieldname": "frakt_column_1", "fieldtype": "Column Break", "insert_after": "fraktprodukt"},
			{"fieldname": "fraktpris", "label": "Fraktpris", "fieldtype": "Currency", "options": "fraktpris_valuta", "read_only": 1, "insert_after": "frakt_column_1"},
			{"fieldname": "fraktpris_valuta", "label": "Valuta", "fieldtype": "Link", "options": "Currency", "read_only": 1, "insert_after": "fraktpris"},
			{"fieldname": "kundpris", "label": "Fraktpris till kund", "fieldtype": "Currency", "allow_on_submit": 1, "insert_after": "fraktpris_valuta"},
			{"fieldname": "pris_hamtat", "label": "Pris hämtat", "fieldtype": "Datetime", "read_only": 1, "insert_after": "kundpris"},
			{"fieldname": "frakt_column_2", "fieldtype": "Column Break", "insert_after": "pris_hamtat"},
			{"fieldname": "sendify_id", "label": "Sendify-id", "fieldtype": "Data", "read_only": 1, "no_copy": 1, "insert_after": "frakt_column_2"},
			{"fieldname": "dokumenttyper", "label": "Dokumenttyper", "fieldtype": "Data", "read_only": 1, "hidden": 1, "no_copy": 1, "insert_after": "sendify_id"},
			{"fieldname": "etikett_hamtad", "label": "Fraktsedel hämtad", "fieldtype": "Check", "read_only": 1, "no_copy": 1, "insert_after": "dokumenttyper"},
			{"fieldname": "senaste_sparning", "label": "Senaste spårning", "fieldtype": "Data", "read_only": 1, "allow_on_submit": 1, "no_copy": 1, "insert_after": "etikett_hamtad"},
			{"fieldname": "senaste_sparningsstatus", "label": "Spårningsstatus hos transportören", "fieldtype": "Data", "read_only": 1, "hidden": 1, "allow_on_submit": 1, "no_copy": 1, "insert_after": "senaste_sparning"},
			{"fieldname": "sparning_section", "label": "Spårningshändelser", "fieldtype": "Section Break", "collapsible": 1, "insert_after": "senaste_sparningsstatus"},
			{"fieldname": "sparningshandelser", "label": "Spårningshändelser", "fieldtype": "Table", "options": "Sparningshandelse", "read_only": 1, "allow_on_submit": 1, "no_copy": 1, "insert_after": "sparning_section"},
		],
		"Shipment Parcel": [
			{"fieldname": "kollityp", "label": "Kollityp", "fieldtype": "Select", "options": "Paket\nPall\nÖvrigt", "default": "Paket", "in_list_view": 1, "insert_after": "count"},
			{"fieldname": "stapelbar", "label": "Stapelbar", "fieldtype": "Check", "default": "1", "insert_after": "kollityp"},
			{"fieldname": "flakmeter", "label": "Flakmeter", "fieldtype": "Float", "insert_after": "stapelbar"},
			{"fieldname": "beskrivning", "label": "Beskrivning", "fieldtype": "Data", "insert_after": "flakmeter"},
		],
	}
```

- [ ] **Step 2: Slå ihop fälten i `setup/custom_fields.py`**

Lägg till importen överst (efter de befintliga importerna):

```python
from erpnext_sverige.frakt.custom_fields import get_custom_fields as get_frakt_custom_fields
```

Byt namn på den befintliga funktionen `get_custom_fields` till `_get_base_custom_fields` (oförändrad kropp) och
lägg till direkt under den:

```python
def get_custom_fields():
	fields = _get_base_custom_fields()
	for doctype, frakt_fields in get_frakt_custom_fields().items():
		fields.setdefault(doctype, []).extend(frakt_fields)
	return fields
```

- [ ] **Step 3: Skriv testet för artikelvalidering i `erpnext_sverige/tests/test_frakt_kollin.py`**

```python
import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.tests.frakt_utils import make_frakt_item


class TestArtikelvalidering(IntegrationTestCase):
	def test_pallplatser_fyller_flakmeter(self):
		item = make_frakt_item("_Test Frakt Maskin", fraktsatt="Egna mått", frakt_pallplatser=2, frakt_kollityp="Pall",
			frakt_langd_cm=240, frakt_bredd_cm=80, frakt_hojd_cm=150, weight_per_unit=400)
		self.assertAlmostEqual(frappe.db.get_value("Item", item, "frakt_flakmeter"), 0.8)

	def test_forpackning_kraver_antal_per_forpackning(self):
		self.assertRaises(frappe.ValidationError, make_frakt_item, "_Test Frakt Utan Antal",
			fraktsatt="Förpackning", forpackningstyp=make_eur_pall(), antal_per_forpackning=0)
```

och skapa `erpnext_sverige/tests/frakt_utils.py`:

```python
"""Testhjälpare för frakt."""

import frappe


def make_eur_pall(name="_Test EUR-pall", egenvikt=25):
	if not frappe.db.exists("Forpackningstyp", name):
		frappe.get_doc(
			{
				"doctype": "Forpackningstyp",
				"forpackningstyp_namn": name,
				"kollityp": "Pall",
				"langd_cm": 120,
				"bredd_cm": 80,
				"hojd_cm": 150,
				"egenvikt_kg": egenvikt,
				"stapelbar": 0,
				"flakmeter": 0.4,
			}
		).insert()
	return name


def make_frakt_item(item_code, weight_uom="Kg", uoms=None, **fields):
	"""Skapar eller uppdaterar en artikel med fraktfält. uoms: [(uom, conversion_factor)]."""
	doc = frappe.get_doc("Item", item_code) if frappe.db.exists("Item", item_code) else frappe.new_doc("Item")
	doc.update(
		{
			"item_code": item_code,
			"item_name": item_code,
			"item_group": "Services",
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"weight_uom": weight_uom,
			**fields,
		}
	)
	if uoms:
		doc.uoms = []
		doc.append("uoms", {"uom": "Nos", "conversion_factor": 1})
		for uom, factor in uoms:
			doc.append("uoms", {"uom": uom, "conversion_factor": factor})
	doc.save()
	return doc.name
```

Lägg till importen `from erpnext_sverige.tests.frakt_utils import make_eur_pall, make_frakt_item` i testfilen
(ersätt den tidigare importraden).

- [ ] **Step 4: Kör testet och se det misslyckas**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_kollin`
Expected: FAIL – `frakt_flakmeter` är 0 / ingen ValidationError (validera_artikel finns inte).

- [ ] **Step 5: Skriv `erpnext_sverige/frakt/kollin.py` med validering**

```python
"""Kolliförslag från artikelrader (egna mått eller förpackningstyp)."""

import frappe
from frappe import _
from frappe.utils import flt

EGNA_MATT = "Egna mått"
FORPACKNING = "Förpackning"
PALLPLATS_FLAKMETER = 0.4


def validera_artikel(doc, method=None):
	"""Item.validate: pallplatser → flakmeter, och förpackning kräver typ och antal."""
	if doc.fraktsatt == EGNA_MATT and flt(doc.frakt_pallplatser) and not flt(doc.frakt_flakmeter):
		doc.frakt_flakmeter = flt(doc.frakt_pallplatser) * PALLPLATS_FLAKMETER
	if doc.fraktsatt == FORPACKNING and (not doc.forpackningstyp or flt(doc.antal_per_forpackning) <= 0):
		frappe.throw(_("Ange förpackningstyp och antal per förpackning (större än noll)"))
```

- [ ] **Step 6: Koppla valideringen i `hooks.py`**

I `doc_events`, lägg till:

```python
	"Item": {
		"validate": "erpnext_sverige.frakt.kollin.validera_artikel",
	},
```

- [ ] **Step 7: Migrera och kör testerna**

Run:
```bash
bench --site test-erp.local migrate
bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_kollin
```
Expected: 2 tests OK. Kontrollera även att `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_print_formats` fortfarande går igenom (custom_fields-ändringen).

- [ ] **Step 8: Commit**

```bash
pre-commit run --files erpnext_sverige/frakt/custom_fields.py erpnext_sverige/frakt/kollin.py erpnext_sverige/setup/custom_fields.py erpnext_sverige/hooks.py erpnext_sverige/tests/frakt_utils.py erpnext_sverige/tests/test_frakt_kollin.py
git add erpnext_sverige/frakt/custom_fields.py erpnext_sverige/frakt/kollin.py erpnext_sverige/setup/custom_fields.py erpnext_sverige/hooks.py erpnext_sverige/tests/frakt_utils.py erpnext_sverige/tests/test_frakt_kollin.py
git commit -m "feat(frakt): add shipping fields to items, customers, orders and shipments"
```

---

### Task 3: Kolliförslag

**Files:**
- Modify: `erpnext_sverige/frakt/kollin.py`
- Test: `erpnext_sverige/tests/test_frakt_kollin.py`

**Interfaces:**
- Consumes: Item-fälten från Task 2, `Forpackningstyp`.
- Produces: `kollin.vikt_kg(item) -> float` (vikt per lagerenhet i kg);
  `kollin.foresla_kollin(rader: list[tuple[str, float]]) -> tuple[list[dict], list[str]]`, där `rader` är
  `(item_code, lagerantal)` och varje kolli är
  `{"kollityp": "Paket"|"Pall"|"Övrigt", "langd_cm": float, "bredd_cm": float, "hojd_cm": float,
  "vikt_kg": float (per enhet), "antal": int, "stapelbar": 0|1, "flakmeter": float (per enhet), "beskrivning": str}`.

- [ ] **Step 1: Skriv de misslyckade testerna** (lägg till i `test_frakt_kollin.py`)

```python
from erpnext_sverige.frakt.kollin import foresla_kollin


class TestKolliforslag(IntegrationTestCase):
	def setUp(self):
		self.pall = make_eur_pall()
		self.a = make_frakt_item("_Test Frakt A", fraktsatt="Förpackning", forpackningstyp=self.pall, antal_per_forpackning=40, weight_per_unit=2)
		self.b = make_frakt_item("_Test Frakt B", fraktsatt="Förpackning", forpackningstyp=self.pall, antal_per_forpackning=20, weight_per_unit=1)
		self.c = make_frakt_item("_Test Frakt C", fraktsatt="", weight_per_unit=5)

	def test_egna_matt_ger_en_rad_per_artikel(self):
		item = make_frakt_item("_Test Frakt Låda", fraktsatt="Egna mått", frakt_kollityp="Paket",
			frakt_langd_cm=30, frakt_bredd_cm=20, frakt_hojd_cm=10, weight_per_unit=1.5)
		kollin, varningar = foresla_kollin([(item, 2)])
		self.assertEqual(varningar, [])
		self.assertEqual(len(kollin), 1)
		k = kollin[0]
		self.assertEqual((k["kollityp"], k["langd_cm"], k["bredd_cm"], k["hojd_cm"], k["antal"]), ("Paket", 30, 20, 10, 2))
		self.assertAlmostEqual(k["vikt_kg"], 1.5)

	def test_forpackningar_fylls_ihop(self):
		kollin, _ = foresla_kollin([(self.a, 100), (self.b, 10)])  # 2,5 + 0,5 pall
		self.assertEqual(len(kollin), 1)
		k = kollin[0]
		self.assertEqual((k["kollityp"], k["antal"], k["langd_cm"], k["bredd_cm"], k["hojd_cm"]), ("Pall", 3, 120, 80, 150))
		self.assertAlmostEqual(k["vikt_kg"], 25 + (200 + 10) / 3, places=2)
		self.assertAlmostEqual(k["flakmeter"], 0.4)
		self.assertEqual(k["beskrivning"], "_Test Frakt A, _Test Frakt B")

	def test_exakt_full_forpackning_avrundas_inte_upp(self):
		kollin, _ = foresla_kollin([(self.a, 80)])
		self.assertEqual(kollin[0]["antal"], 2)

	def test_artikel_utan_fraktsatt_laggs_pa_forpackningen(self):
		kollin, varningar = foresla_kollin([(self.a, 40), (self.c, 3)])
		self.assertEqual(len(kollin), 1)
		self.assertAlmostEqual(kollin[0]["vikt_kg"], 25 + 80 + 15)
		self.assertIn("_Test Frakt C saknar fraktsätt", varningar)

	def test_artikel_utan_fraktsatt_och_utan_forpackning_blir_ovrigt(self):
		kollin, _ = foresla_kollin([(self.c, 3)])
		self.assertEqual(len(kollin), 1)
		self.assertEqual((kollin[0]["kollityp"], kollin[0]["antal"], kollin[0]["langd_cm"]), ("Övrigt", 1, 0))
		self.assertAlmostEqual(kollin[0]["vikt_kg"], 15)

	def test_inga_kollin_utan_vikt(self):
		item = make_frakt_item("_Test Frakt Viktlös", fraktsatt="", weight_per_unit=0)
		kollin, varningar = foresla_kollin([(item, 1)])
		self.assertEqual(kollin, [])
		self.assertIn("_Test Frakt Viktlös saknar vikt", varningar)

	def test_vikt_i_gram_raknas_om_till_kg(self):
		item = make_frakt_item("_Test Frakt Gram", weight_uom="Gram", fraktsatt="Egna mått", frakt_kollityp="Paket",
			frakt_langd_cm=10, frakt_bredd_cm=10, frakt_hojd_cm=10, weight_per_unit=500)
		kollin, _ = foresla_kollin([(item, 4)])
		self.assertAlmostEqual(kollin[0]["vikt_kg"], 0.5)

	def test_egna_matt_utan_matt_ger_varning(self):
		item = make_frakt_item("_Test Frakt Måttlös", fraktsatt="Egna mått", frakt_kollityp="Paket", weight_per_unit=1,
			frakt_langd_cm=0, frakt_bredd_cm=0, frakt_hojd_cm=0)
		_kollin, varningar = foresla_kollin([(item, 1)])
		self.assertIn("_Test Frakt Måttlös saknar mått", varningar)
```

- [ ] **Step 2: Kör och se dem misslyckas**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_kollin`
Expected: FAIL med `ImportError: cannot import name 'foresla_kollin'`.

- [ ] **Step 3: Implementera i `kollin.py`** (lägg till under `validera_artikel`)

```python
import math

from erpnext.stock.doctype.item.item import get_uom_conv_factor

OVRIGT = "Övrigt"


def vikt_kg(item) -> float:
	"""Artikelns vikt per lagerenhet i kg. Saknas viktenhet räknas vikten som kg."""
	vikt = flt(item.weight_per_unit)
	if not vikt or not item.weight_uom:
		return vikt
	return vikt * flt(get_uom_conv_factor(item.weight_uom, "Kg"))


def foresla_kollin(rader):
	"""rader: [(item_code, lagerantal)] → (kollin, varningar). Se modulens docstring för kollits nycklar."""
	kollin, varningar = [], []
	forpackningar = {}  # förpackningstyp → {"fyllnad", "vikt", "namn"}
	lost_vikt = 0.0  # vikt från artiklar utan fraktsätt

	for item_code, antal in rader:
		antal = flt(antal)
		if antal <= 0:
			continue
		item = frappe.get_cached_doc("Item", item_code)
		vikt = vikt_kg(item)
		if not vikt:
			varningar.append(_("{0} saknar vikt").format(item.item_name))

		if item.fraktsatt == EGNA_MATT:
			if not (flt(item.frakt_langd_cm) and flt(item.frakt_bredd_cm) and flt(item.frakt_hojd_cm)):
				varningar.append(_("{0} saknar mått").format(item.item_name))
			kollin.append(
				{
					"kollityp": item.frakt_kollityp or "Paket",
					"langd_cm": flt(item.frakt_langd_cm),
					"bredd_cm": flt(item.frakt_bredd_cm),
					"hojd_cm": flt(item.frakt_hojd_cm),
					"vikt_kg": round(vikt, 2),
					"antal": math.ceil(antal),
					"stapelbar": int(item.frakt_stapelbar or 0),
					"flakmeter": flt(item.frakt_flakmeter),
					"beskrivning": item.item_name[:100],
				}
			)
		elif item.fraktsatt == FORPACKNING and item.forpackningstyp and flt(item.antal_per_forpackning) > 0:
			f = forpackningar.setdefault(item.forpackningstyp, {"fyllnad": 0.0, "vikt": 0.0, "namn": []})
			f["fyllnad"] += antal / flt(item.antal_per_forpackning)
			f["vikt"] += vikt * antal
			f["namn"].append(item.item_name)
		else:
			varningar.append(_("{0} saknar fraktsätt").format(item.item_name))
			lost_vikt += vikt * antal

	forpackningskollin = []
	for typ, f in forpackningar.items():
		forp = frappe.get_cached_doc("Forpackningstyp", typ)
		antal = max(1, math.ceil(round(f["fyllnad"], 6)))
		forpackningskollin.append(
			{
				"kollityp": forp.kollityp,
				"langd_cm": flt(forp.langd_cm),
				"bredd_cm": flt(forp.bredd_cm),
				"hojd_cm": flt(forp.hojd_cm),
				"vikt_kg": flt(forp.egenvikt_kg) + f["vikt"] / antal,
				"antal": antal,
				"stapelbar": int(forp.stapelbar or 0),
				"flakmeter": flt(forp.flakmeter),
				"beskrivning": ", ".join(dict.fromkeys(f["namn"]))[:100],
			}
		)

	if lost_vikt and forpackningskollin:
		per_enhet = lost_vikt / sum(k["antal"] for k in forpackningskollin)
		for k in forpackningskollin:
			k["vikt_kg"] += per_enhet
	elif lost_vikt:
		kollin.append(
			{
				"kollityp": OVRIGT,
				"langd_cm": 0,
				"bredd_cm": 0,
				"hojd_cm": 0,
				"vikt_kg": round(lost_vikt, 2),
				"antal": 1,
				"stapelbar": 0,
				"flakmeter": 0,
				"beskrivning": _("Övrigt"),
			}
		)

	for k in forpackningskollin:
		k["vikt_kg"] = round(k["vikt_kg"], 2)
	return kollin + forpackningskollin, varningar
```

Flytta `import math` och importen av `get_uom_conv_factor` upp bland modulens övriga importer.

- [ ] **Step 4: Kör testerna**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_kollin`
Expected: 10 tests OK.

- [ ] **Step 5: Commit**

```bash
pre-commit run --files erpnext_sverige/frakt/kollin.py erpnext_sverige/tests/test_frakt_kollin.py
git add erpnext_sverige/frakt/kollin.py erpnext_sverige/tests/test_frakt_kollin.py
git commit -m "feat(frakt): suggest parcels from item dimensions and packaging types"
```

---

### Task 4: Sendify-klient

**Files:**
- Create: `erpnext_sverige/frakt/sendify.py`
- Test: `erpnext_sverige/tests/test_frakt_sendify.py`

**Interfaces:**
- Consumes: `FraktFel`, `hamta_installningar` (Task 1). Kollin enligt Task 3.
- Produces (alla kastar `FraktFel` vid fel):
  - `skapa_sandning(sandning: dict) -> str` (Sendifys id)
  - `uppdatera_sandning(sendify_id: str, sandning: dict) -> None`
  - `radera_sandning(sendify_id: str) -> None`
  - `hamta_priser(sendify_id: str, upphamtning: datetime) -> tuple[list[dict], list[str]]`; pris-dict:
    `{"token", "transportorskod", "transportor", "produkt", "pris": float, "valuta", "dagar_min", "dagar_max",
    "upphamtning": dict, "leverans": dict, "giltig_till": str}`
  - `boka(token: str) -> dict` `{"sparningsnummer": str, "dokumenttyper": list[str]}`
  - `hamta_dokument(sendify_id: str, typ: str) -> bytes` (`typ` = `"label"` eller `"waybill"`)
  - `avboka(sendify_id: str) -> None`
  - `hamta_sparning(sendify_id: str) -> list[dict]` `{"tidpunkt": datetime (systemets tidszon, naiv), "status",
    "beskrivning", "plats", "url"}`
  - `kontrollera_nyckel(installningar=None) -> str` (teamnamn)
  - `sandning`-dict: `{"avsandare": part, "mottagare": part, "kollin": [kolli], "referens_id", "avsandarens_referens",
    "mottagarens_referens"}`; `part` = `{"namn", "adressrad_1", "adressrad_2", "postnummer", "ort", "landskod",
    "kontakt_namn", "telefon", "epost", "privatperson": bool}`

- [ ] **Step 1: Skriv de misslyckade testerna i `erpnext_sverige/tests/test_frakt_sendify.py`**

```python
from datetime import datetime
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.frakt import FraktFel
from erpnext_sverige.frakt import sendify

NYCKEL = "hemlig-nyckel-123"
PART = {
	"namn": "Avsändare AB", "adressrad_1": "Gatan 1", "adressrad_2": "", "postnummer": "41107", "ort": "Göteborg",
	"landskod": "SE", "kontakt_namn": "Anna", "telefon": "0701234567", "epost": "anna@example.com", "privatperson": False,
}
KOLLI = {"kollityp": "Pall", "langd_cm": 120, "bredd_cm": 80, "hojd_cm": 150, "vikt_kg": 95.0, "antal": 3,
	"stapelbar": 0, "flakmeter": 0.4, "beskrivning": "Varor"}
SANDNING = {"avsandare": PART, "mottagare": {**PART, "namn": "Kund AB", "privatperson": True}, "kollin": [KOLLI],
	"referens_id": "SHIP-0001", "avsandarens_referens": "DN-0001", "mottagarens_referens": ""}


def svar(status=200, data=None, headers=None, content=b"x"):
	r = MagicMock()
	r.status_code = status
	r.json.return_value = data if data is not None else {}
	r.headers = headers or {"X-Sendify-Request-ID": "req-1"}
	r.content = content
	r.text = str(data)
	return r


class TestSendify(IntegrationTestCase):
	def setUp(self):
		inst = frappe._dict(miljo="Sandlåda", get_password=lambda falt: NYCKEL)
		self.inst = patch("erpnext_sverige.frakt.sendify.hamta_installningar", return_value=inst)
		self.inst.start()
		self.addCleanup(self.inst.stop)

	def test_skapa_sandning_skickar_sendifys_format(self):
		with patch("erpnext_sverige.frakt.sendify.requests.request", return_value=svar(201, {"id": "S1"})) as req:
			self.assertEqual(sendify.skapa_sandning(SANDNING), "S1")
		metod, url = req.call_args.args
		body = req.call_args.kwargs["json"]
		self.assertEqual((metod, url), ("POST", "https://app.dev.sendify.se/external/v1/shipments"))
		self.assertEqual(req.call_args.kwargs["headers"]["x-api-key"], NYCKEL)
		self.assertTrue(body["enable_bookable_validation"])
		self.assertEqual(body["to"]["is_private_individual"], True)
		self.assertEqual(body["sender_reference"], "DN-0001")
		self.assertNotIn("receiver_reference", body)  # tomma värden skickas inte
		self.assertNotIn("address_line_2", body["from"]["address"])
		self.assertEqual(
			body["packages"][0],
			{"depth_cm": 120, "width_cm": 80, "height_cm": 150, "weight_kg": 95.0, "quantity": 3, "type": "PALLET",
				"stackable": False, "description": "Varor", "loading_meters": 0.4},
		)

	def test_hamta_priser_oversatter_svaret(self):
		data = {
			"rates": [{"booking_token": "T1", "carrier_code": "ups_se", "carrier_name": "UPS Sweden",
				"product_name": "UPS Standard", "price": "127", "currency": "SEK", "transport_business_days_min": 2,
				"transport_business_days_max": 3, "expires_at": "2026-10-02T11:41:56Z", "pickup": {"date": "2026-10-02"},
				"estimated_delivery": {"earliest_date": "2026-10-05"}}],
			"warnings": [{"carrier_name": "DHL", "carrier_product_code": "dhl", "warnings": ["Name too long", "Phone missing"]}],
		}
		with patch("erpnext_sverige.frakt.sendify.requests.request", return_value=svar(200, data)) as req:
			priser, varningar = sendify.hamta_priser("S1", datetime(2026, 10, 2, 9, 0))
		self.assertEqual(req.call_args.kwargs["json"]["shipment_id"], "S1")
		self.assertTrue(req.call_args.kwargs["json"]["requested_pickup_time"].startswith("2026-10-02T09:00:00+0"))
		self.assertEqual(priser[0]["pris"], 127.0)
		self.assertEqual((priser[0]["token"], priser[0]["transportor"], priser[0]["produkt"]), ("T1", "UPS Sweden", "UPS Standard"))
		self.assertEqual(varningar, ["DHL: Name too long; Phone missing"])

	def test_valideringsfel_far_svenska_faltnamn(self):
		data = {"errors": {"packages[0].weight_kg": ["The field is required."], "to.contact.email": ["Invalid email."]}}
		with patch("erpnext_sverige.frakt.sendify.requests.request", return_value=svar(422, data)):
			with self.assertRaises(FraktFel) as fel:
				sendify.skapa_sandning(SANDNING)
		self.assertIn("Kolli 1: vikt: The field is required.", fel.exception.falt_fel)
		self.assertIn("Mottagare: e-post: Invalid email.", fel.exception.falt_fel)
		self.assertEqual(fel.exception.request_id, "req-1")

	def test_serverfel_och_natverksfel(self):
		with patch("erpnext_sverige.frakt.sendify.requests.request", return_value=svar(503, {})):
			self.assertRaisesRegex(FraktFel, "Sendify svarar inte", sendify.skapa_sandning, SANDNING)
		with patch("erpnext_sverige.frakt.sendify.requests.request", side_effect=sendify.requests.ConnectionError()):
			self.assertRaisesRegex(FraktFel, "Sendify svarar inte", sendify.skapa_sandning, SANDNING)

	def test_nyckeln_loggas_aldrig(self):
		with (
			patch("erpnext_sverige.frakt.sendify.requests.request", return_value=svar(400, {"message": "Bad"})),
			patch("erpnext_sverige.frakt.sendify.frappe.log_error") as logg,
		):
			self.assertRaises(FraktFel, sendify.skapa_sandning, SANDNING)
		self.assertTrue(logg.called)
		self.assertNotIn(NYCKEL, str(logg.call_args))

	def test_boka_och_dokument(self):
		with patch("erpnext_sverige.frakt.sendify.requests.request", return_value=svar(200,
			{"shipment_id": "S1", "main_tracking_id": "TRK1", "available_document_types": ["label", "waybill"]})):
			self.assertEqual(sendify.boka("T1"), {"sparningsnummer": "TRK1", "dokumenttyper": ["label", "waybill"]})
		with (
			patch("erpnext_sverige.frakt.sendify.requests.request", return_value=svar(200, {"output_url": "https://x/doc.pdf"})) as req,
			patch("erpnext_sverige.frakt.sendify.requests.get", return_value=svar(200, content=b"%PDF")),
		):
			self.assertEqual(sendify.hamta_dokument("S1", "label"), b"%PDF")
		self.assertEqual(req.call_args.kwargs["json"],
			{"shipment_ids": ["S1"], "document_type": "label", "label_layout": "a4", "output_format": "url"})

	def test_sparning_tolkar_tid_med_nanosekunder(self):
		data = [{"ID": "TRK1", "url": "https://sendify/t/S1", "status": "ORDERED", "description": "Booked",
			"location_name": "Göteborg", "created_at": "2026-10-01T09:17:29.754885247Z"}]
		with patch("erpnext_sverige.frakt.sendify.requests.request", return_value=svar(200, data)):
			handelser = sendify.hamta_sparning("S1")
		self.assertEqual(handelser[0]["status"], "ORDERED")
		self.assertEqual(handelser[0]["tidpunkt"].replace(microsecond=0), datetime(2026, 10, 1, 11, 17, 29))  # CEST
		self.assertEqual(handelser[0]["url"], "https://sendify/t/S1")
```

- [ ] **Step 2: Kör och se dem misslyckas**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_sendify`
Expected: FAIL med `ImportError: cannot import name 'sendify'`.

- [ ] **Step 3: Skriv `erpnext_sverige/frakt/sendify.py`**

```python
"""Sendify-API (https://api.sendify.com/docs). Den enda modulen som känner till Sendify.

Tar och ger dict:ar i fraktmodulens eget format (se docs/superpowers/specs/2026-10-01-frakt-sendify-design.md).
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import frappe
import requests
from frappe import _
from frappe.utils import flt, get_system_timezone

from erpnext_sverige.frakt import FraktFel, hamta_installningar

BAS_URL = {
	"Sandlåda": "https://app.dev.sendify.se/external/v1",
	"Produktion": "https://app.sendify.se/external/v1",
}
TIMEOUT = 30
KOLLITYP = {"Paket": "PACKAGE", "Pall": "PALLET", "Övrigt": "UNSPECIFIED"}
PART = {"from": "Avsändare", "to": "Mottagare"}
FALT = {
	"weight_kg": "vikt",
	"width_cm": "bredd",
	"height_cm": "höjd",
	"depth_cm": "längd",
	"quantity": "antal",
	"type": "kollityp",
	"loading_meters": "flakmeter",
	"address_line_1": "adress",
	"postal_code": "postnummer",
	"city": "ort",
	"country_code": "land",
	"name": "namn",
	"phone": "telefon",
	"email": "e-post",
}
EJ_SVARAR = "Sendify svarar inte, försök igen"


# --- HTTP ---------------------------------------------------------------------------------------------


def _anrop(metod, sokvag, data=None, installningar=None):
	inst = installningar or hamta_installningar()
	try:
		svar = requests.request(
			metod,
			BAS_URL[inst.miljo] + sokvag,
			json=data,
			headers={"x-api-key": inst.get_password("api_nyckel"), "Accept": "application/json"},
			timeout=TIMEOUT,
		)
	except requests.RequestException:
		raise FraktFel(_(EJ_SVARAR)) from None
	request_id = svar.headers.get("X-Sendify-Request-ID")
	if svar.status_code >= 400:
		frappe.log_error(
			title=f"Sendify {metod} {sokvag}",
			message=f"HTTP {svar.status_code}\nX-Sendify-Request-ID: {request_id}\n{svar.text[:2000]}",
		)
		if svar.status_code >= 500:
			raise FraktFel(_(EJ_SVARAR), request_id=request_id)
		raise _fel_fran_svar(svar, request_id)
	if svar.status_code == 204 or not svar.content:
		return None
	return svar.json()


def _fel_fran_svar(svar, request_id):
	try:
		data = svar.json() or {}
	except ValueError:
		data = {}
	falt_fel = []
	for falt, meddelanden in (data.get("errors") or {}).items():
		for meddelande in meddelanden if isinstance(meddelanden, list) else [meddelanden]:
			falt_fel.append(f"{faltnamn(falt)}: {meddelande}")
	meddelande = data.get("message") or data.get("error")
	if not meddelande:
		meddelande = _("Sendify kunde inte behandla sändningen") if falt_fel else _("Sendify avvisade anropet (HTTP {0})").format(svar.status_code)
	return FraktFel(meddelande, falt_fel=falt_fel, request_id=request_id)


def faltnamn(falt: str) -> str:
	"""packages[0].weight_kg → "Kolli 1: vikt", to.contact.email → "Mottagare: e-post"."""
	sista = FALT.get(falt.rsplit(".", 1)[-1], falt.rsplit(".", 1)[-1])
	if m := re.match(r"packages\[(\d+)\]", falt):
		return _("Kolli {0}: {1}").format(int(m.group(1)) + 1, sista)
	if (forsta := falt.split(".", 1)[0]) in PART:
		return f"{_(PART[forsta])}: {sista}"
	return sista


# --- Format --------------------------------------------------------------------------------------------


def _utan_tomma(varde):
	if isinstance(varde, dict):
		return {k: _utan_tomma(v) for k, v in varde.items() if v not in (None, "", [], {})}
	if isinstance(varde, list):
		return [_utan_tomma(v) for v in varde]
	return varde


def _part(p):
	return {
		"name": p.get("namn"),
		"address": {
			"address_line_1": p.get("adressrad_1"),
			"address_line_2": p.get("adressrad_2"),
			"postal_code": p.get("postnummer"),
			"city": p.get("ort"),
			"country_code": p.get("landskod"),
		},
		"contact": {"name": p.get("kontakt_namn"), "phone": p.get("telefon"), "email": p.get("epost")},
	}


def _kolli(k):
	return {
		"depth_cm": flt(k["langd_cm"]),
		"width_cm": flt(k["bredd_cm"]),
		"height_cm": flt(k["hojd_cm"]),
		"weight_kg": flt(k["vikt_kg"]),
		"quantity": int(k["antal"]),
		"type": KOLLITYP.get(k.get("kollityp") or "Paket", "UNSPECIFIED"),
		"stackable": bool(k.get("stapelbar")),
		"description": k.get("beskrivning"),
		"loading_meters": flt(k.get("flakmeter")) or None,
	}


def till_sendify(sandning):
	data = {
		"enable_bookable_validation": True,
		"from": _part(sandning["avsandare"]),
		"to": _part(sandning["mottagare"]),
		"reference_id": sandning.get("referens_id"),
		"sender_reference": sandning.get("avsandarens_referens"),
		"receiver_reference": sandning.get("mottagarens_referens"),
		"packages": [_kolli(k) for k in sandning["kollin"]],
		"system": "ERPNext",
	}
	data = _utan_tomma(data)
	data["to"]["is_private_individual"] = bool(sandning["mottagare"].get("privatperson"))
	return data


def _iso(tid: datetime) -> str:
	return tid.replace(tzinfo=ZoneInfo(get_system_timezone())).isoformat()


def _tid(text: str) -> datetime:
	"""ISO 8601 från Sendify (kan ha nanosekunder och Z) → naiv tid i systemets tidszon."""
	text = re.sub(r"(\.\d{6})\d+", r"\1", text).replace("Z", "+00:00")
	return datetime.fromisoformat(text).astimezone(ZoneInfo(get_system_timezone())).replace(tzinfo=None)


def _pris(r):
	return {
		"token": r["booking_token"],
		"transportorskod": r.get("carrier_code"),
		"transportor": r["carrier_name"],
		"produkt": r["product_name"],
		"pris": flt(r["price"]),
		"valuta": r.get("currency") or "SEK",
		"dagar_min": r.get("transport_business_days_min"),
		"dagar_max": r.get("transport_business_days_max"),
		"upphamtning": r.get("pickup") or {},
		"leverans": r.get("estimated_delivery") or {},
		"giltig_till": r.get("expires_at"),
	}


# --- Funktioner -------------------------------------------------------------------------------------------


def skapa_sandning(sandning) -> str:
	return _anrop("POST", "/shipments", till_sendify(sandning))["id"]


def uppdatera_sandning(sendify_id, sandning) -> None:
	_anrop("PUT", f"/shipments/{sendify_id}", till_sendify(sandning))


def radera_sandning(sendify_id) -> None:
	_anrop("DELETE", f"/shipments/{sendify_id}")


def hamta_priser(sendify_id, upphamtning: datetime):
	data = _anrop("POST", "/shipments/rates", {"shipment_id": sendify_id, "requested_pickup_time": _iso(upphamtning)})
	varningar = [f"{w['carrier_name']}: {'; '.join(w.get('warnings') or [])}" for w in data.get("warnings") or []]
	return [_pris(r) for r in data.get("rates") or []], varningar


def boka(token) -> dict:
	data = _anrop("POST", "/shipments/book", {"booking_token": token})
	return {"sparningsnummer": data.get("main_tracking_id"), "dokumenttyper": data.get("available_document_types") or []}


def hamta_dokument(sendify_id, typ) -> bytes:
	data = _anrop(
		"POST",
		"/shipments/print",
		{"shipment_ids": [sendify_id], "document_type": typ, "label_layout": "a4", "output_format": "url"},
	)
	try:
		pdf = requests.get(data["output_url"], timeout=TIMEOUT)
	except requests.RequestException:
		raise FraktFel(_(EJ_SVARAR)) from None
	if pdf.status_code >= 400:
		raise FraktFel(_("Dokumentet kunde inte hämtas från Sendify (HTTP {0})").format(pdf.status_code))
	return pdf.content


def avboka(sendify_id) -> None:
	_anrop("POST", "/shipments/cancel", {"shipment_id": sendify_id})


def hamta_sparning(sendify_id) -> list[dict]:
	return [
		{
			"tidpunkt": _tid(h["created_at"]),
			"status": h.get("status"),
			"beskrivning": h.get("description"),
			"plats": h.get("location_name"),
			"url": h.get("url"),
		}
		for h in _anrop("GET", f"/shipments/{sendify_id}/tracking") or []
	]


def kontrollera_nyckel(installningar=None) -> str:
	return _anrop("GET", "/status", installningar=installningar).get("team")
```

Obs: `label_layout` skickas bara för `label` i Sendifys exempel men accepteras för alla typer; om sandlådetestet
(Task 13) visar att `waybill` avvisas med `label_layout`, ta bort nyckeln när `typ != "label"`.
Avbokningens body (`{"shipment_id": ...}`) verifieras i sandlådetestet (Task 13) mot sidan
"Cancel a booked shipment" i Sendifys dokumentation.

- [ ] **Step 4: Kör testerna**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_sendify`
Expected: 7 tests OK.

- [ ] **Step 5: Commit**

```bash
pre-commit run --files erpnext_sverige/frakt/sendify.py erpnext_sverige/tests/test_frakt_sendify.py
git add erpnext_sverige/frakt/sendify.py erpnext_sverige/tests/test_frakt_sendify.py
git commit -m "feat(frakt): add Sendify API client"
```

---

### Task 5: Parter, påslag och fraktproduktregister

**Files:**
- Create: `erpnext_sverige/frakt/parter.py`
- Create: `erpnext_sverige/frakt/fraktpris.py`
- Modify: `erpnext_sverige/tests/frakt_utils.py`
- Test: `erpnext_sverige/tests/test_frakt_fraktpris.py`

**Interfaces:**
- Consumes: `hamta_installningar` (Task 1), part-format (Task 4).
- Produces:
  - `parter.part(namn: str, adress: str|None, kontakt: str|None, privatperson: bool) -> dict` (Task 4:s part-format)
  - `parter.avsandare(inst) -> dict`
  - `parter.nasta_arbetsdag(fran: date|None = None) -> date`
  - `parter.upphamtningstid(datum, tid) -> datetime`
  - `fraktpris.kundpris(pris: float) -> float`
  - `fraktpris.registrera_produkter(priser: list[dict]) -> list[dict]` (sätter `"fraktprodukt"` och `"kundpris"` på
    varje pris och returnerar listan sorterad på pris)
  - Testhjälpare `frakt_utils.aktivera_frakt(**andringar)` och `frakt_utils.make_kund_med_adress(namn) -> str`

- [ ] **Step 1: Lägg till testhjälpare i `frakt_utils.py`**

```python
from erpnext_sverige.setup.company import TAX_CATEGORY_SE
from erpnext_sverige.tests.utils import COMPANY, account, ensure_test_company, make_party


def make_adress(titel, lank_doctype, lank_namn, foretag=False):
	namn = frappe.db.get_value("Address", {"address_title": titel})
	if namn:
		return namn
	return frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": titel,
			"address_type": "Shipping" if not foretag else "Billing",
			"address_line1": "Testgatan 1",
			"city": "Göteborg",
			"pincode": "41107",
			"country": "Sweden",
			"is_your_company_address": int(foretag),
			"links": [{"link_doctype": lank_doctype, "link_name": lank_namn}],
		}
	).insert().name


def make_kontakt(fornamn, lank_doctype, lank_namn, epost="test@example.com", telefon="0701234567"):
	namn = frappe.db.get_value("Contact", {"first_name": fornamn})
	if namn:
		return namn
	kontakt = frappe.get_doc(
		{"doctype": "Contact", "first_name": fornamn, "links": [{"link_doctype": lank_doctype, "link_name": lank_namn}]}
	)
	if epost:
		kontakt.append("email_ids", {"email_id": epost, "is_primary": 1})
	if telefon:
		kontakt.append("phone_nos", {"phone": telefon, "is_primary_mobile_no": 1})
	return kontakt.insert().name


def make_kund_med_adress(namn="_Test Fraktkund"):
	make_party("Customer", namn, TAX_CATEGORY_SE)
	make_adress(f"{namn} leverans", "Customer", namn)
	make_kontakt(f"{namn} kontakt", "Customer", namn)
	return namn


def aktivera_frakt(**andringar):
	ensure_test_company()
	inst = frappe.get_doc("Fraktinstallningar")
	inst.update(
		{
			"aktiverad": 1,
			"leverantor": "Sendify",
			"miljo": "Sandlåda",
			"api_nyckel": "test-nyckel",
			"bolag": COMPANY,
			"avsandaradress": make_adress("_Test Svenska AB lager", "Company", COMPANY, foretag=True),
			"avsandarkontakt": make_kontakt("_Test Lagerchef", "Company", COMPANY),
			"upphamtning_fran": "09:00:00",
			"upphamtning_till": "16:00:00",
			"paslag_procent": 10,
			"paslag_belopp": 20,
			"fraktkonto": account("3520"),
			"prisandring_grans_procent": 5,
			**andringar,
		}
	)
	inst.save()
	frappe.clear_document_cache("Fraktinstallningar", "Fraktinstallningar")
	return inst
```

- [ ] **Step 2: Skriv de misslyckade testerna i `erpnext_sverige/tests/test_frakt_fraktpris.py`**

```python
from datetime import date, datetime

import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.frakt import fraktpris, parter
from erpnext_sverige.tests.frakt_utils import aktivera_frakt, make_kund_med_adress


class TestFraktpris(IntegrationTestCase):
	def setUp(self):
		self.inst = aktivera_frakt()

	def test_kundpris_med_paslag_avrundas_till_hela_kronor(self):
		self.assertEqual(fraktpris.kundpris(127), 160)  # 127 * 1,10 + 20 = 159,7

	def test_registrera_produkter_skapar_fraktprodukt_en_gang(self):
		priser = [
			{"transportorskod": "ups_se", "transportor": "_Test UPS", "produkt": "Standard", "pris": 200.0},
			{"transportorskod": "dhl_se", "transportor": "_Test DHL", "produkt": "Paket", "pris": 100.0},
		]
		resultat = fraktpris.registrera_produkter(priser)
		self.assertEqual([p["fraktprodukt"] for p in resultat], ["_Test DHL – Paket", "_Test UPS – Standard"])
		self.assertEqual(resultat[0]["kundpris"], 130)
		fraktpris.registrera_produkter(priser)
		self.assertEqual(frappe.db.count("Fraktprodukt", {"transportor": "_Test UPS"}), 1)

	def test_part_fran_adress_och_kontakt(self):
		kund = make_kund_med_adress()
		adress = frappe.db.get_value("Address", {"address_title": f"{kund} leverans"})
		kontakt = frappe.db.get_value("Contact", {"first_name": f"{kund} kontakt"})
		p = parter.part("Kund AB", adress, kontakt, privatperson=False)
		self.assertEqual(
			{k: p[k] for k in ("namn", "adressrad_1", "postnummer", "ort", "landskod", "telefon", "epost")},
			{"namn": "Kund AB", "adressrad_1": "Testgatan 1", "postnummer": "41107", "ort": "Göteborg",
				"landskod": "SE", "telefon": "0701234567", "epost": "test@example.com"},
		)

	def test_nasta_arbetsdag_hoppar_over_helg(self):
		self.assertEqual(parter.nasta_arbetsdag(date(2026, 10, 2)), date(2026, 10, 5))  # fredag → måndag
		self.assertEqual(parter.nasta_arbetsdag(date(2026, 10, 5)), date(2026, 10, 6))

	def test_upphamtningstid(self):
		self.assertEqual(parter.upphamtningstid("2026-10-05", "09:30:00"), datetime(2026, 10, 5, 9, 30))
```

- [ ] **Step 3: Kör och se dem misslyckas**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_fraktpris`
Expected: FAIL med `ImportError`.

- [ ] **Step 4: Skriv `erpnext_sverige/frakt/parter.py`**

```python
"""Avsändare och mottagare i fraktmodulens part-format, från ERPNext:s Address och Contact."""

from datetime import date, datetime, timedelta

import frappe
from frappe.utils import get_datetime, get_time, getdate, today


def part(namn, adress, kontakt, privatperson=False) -> dict:
	a = frappe.db.get_value(
		"Address", adress, ["address_line1", "address_line2", "pincode", "city", "country"], as_dict=True
	) if adress else frappe._dict()
	k = frappe.db.get_value(
		"Contact", kontakt, ["first_name", "last_name", "mobile_no", "phone", "email_id"], as_dict=True
	) if kontakt else frappe._dict()
	landskod = frappe.db.get_value("Country", a.country, "code") if a.country else None
	return {
		"namn": namn,
		"adressrad_1": a.address_line1,
		"adressrad_2": a.address_line2,
		"postnummer": a.pincode,
		"ort": a.city,
		"landskod": landskod.upper() if landskod else None,
		"kontakt_namn": " ".join(filter(None, [k.first_name, k.last_name])) or None,
		"telefon": k.mobile_no or k.phone,
		"epost": k.email_id,
		"privatperson": bool(privatperson),
	}


def avsandare(inst) -> dict:
	namn = frappe.db.get_value("Company", inst.bolag, "company_name")
	return part(namn, inst.avsandaradress, inst.avsandarkontakt)


def nasta_arbetsdag(fran: date | None = None) -> date:
	dag = getdate(fran or today()) + timedelta(days=1)
	while dag.weekday() >= 5:
		dag += timedelta(days=1)
	return dag


def upphamtningstid(datum, tid) -> datetime:
	return get_datetime(f"{getdate(datum)} {get_time(tid)}")
```

- [ ] **Step 5: Skriv `erpnext_sverige/frakt/fraktpris.py`** (påslag och register)

```python
"""Fraktpris till kund (påslag), register över transportörsprodukter, prisförfrågan och fraktrad på faktura."""

import frappe
from frappe.utils import flt, rounded

from erpnext_sverige.frakt import hamta_installningar


def kundpris(pris: float) -> float:
	inst = hamta_installningar()
	return rounded(flt(pris) * (1 + flt(inst.paslag_procent) / 100) + flt(inst.paslag_belopp), 0)


def registrera_produkter(priser: list[dict]) -> list[dict]:
	"""Skapar saknade Fraktprodukter och sätter "fraktprodukt" och "kundpris" på varje pris."""
	for p in priser:
		namn = f"{p['transportor']} – {p['produkt']}"
		if not frappe.db.exists("Fraktprodukt", namn):
			frappe.get_doc(
				{
					"doctype": "Fraktprodukt",
					"leverantor": hamta_installningar().leverantor,
					"transportorskod": p.get("transportorskod"),
					"transportor": p["transportor"],
					"produkt": p["produkt"],
				}
			).insert(ignore_permissions=True)
		p["fraktprodukt"] = namn
		p["kundpris"] = kundpris(p["pris"])
	return sorted(priser, key=lambda p: p["pris"])
```

- [ ] **Step 6: Kör testerna**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_fraktpris`
Expected: 5 tests OK.

- [ ] **Step 7: Commit**

```bash
pre-commit run --files erpnext_sverige/frakt/parter.py erpnext_sverige/frakt/fraktpris.py erpnext_sverige/tests/frakt_utils.py erpnext_sverige/tests/test_frakt_fraktpris.py
git add erpnext_sverige/frakt/parter.py erpnext_sverige/frakt/fraktpris.py erpnext_sverige/tests/frakt_utils.py erpnext_sverige/tests/test_frakt_fraktpris.py
git commit -m "feat(frakt): add sender/receiver mapping, markup and carrier product register"
```

---

### Task 6: Shipment från följesedel

**Files:**
- Create: `erpnext_sverige/frakt/bokning.py`
- Modify: `erpnext_sverige/tests/frakt_utils.py`
- Test: `erpnext_sverige/tests/test_frakt_bokning.py`

**Interfaces:**
- Consumes: `foresla_kollin` (Task 3), `parter.*` (Task 5), `hamta_installningar` (Task 1).
- Produces:
  - `bokning.skapa_shipment(delivery_note: str) -> str` (whitelist; Shipment-namn)
  - `bokning.foresla_kollin_igen(shipment: str) -> list[str]` (whitelist; varningar)
  - `bokning.satt_kollin(doc, kollin: list[dict]) -> None`
  - `bokning.sandning_fran_shipment(doc) -> dict` (Task 4:s sandning-format)
  - Testhjälpare `frakt_utils.make_foljesedel(kund, rader, po_no=None, sales_order=None) -> Document`
    (`rader` = `[(item_code, qty)]` eller `[(item_code, qty, uom)]`, godkänd)

- [ ] **Step 1: Lägg till testhjälparen i `frakt_utils.py`**

```python
def make_foljesedel(kund, rader, po_no=None):
	"""rader: [(item_code, qty)] eller [(item_code, qty, uom)]. Returnerar en godkänd följesedel."""
	dn = frappe.get_doc(
		{
			"doctype": "Delivery Note",
			"company": COMPANY,
			"customer": kund,
			"po_no": po_no,
			"shipping_address_name": frappe.db.get_value("Address", {"address_title": f"{kund} leverans"}),
			"contact_person": frappe.db.get_value("Contact", {"first_name": f"{kund} kontakt"}),
			"items": [
				{"item_code": r[0], "qty": r[1], "rate": 100, **({"uom": r[2]} if len(r) > 2 else {})}
				for r in rader
			],
		}
	)
	dn.insert()
	dn.submit()
	return dn
```

- [ ] **Step 2: Skriv de misslyckade testerna i `erpnext_sverige/tests/test_frakt_bokning.py`**

```python
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.frakt import bokning
from erpnext_sverige.tests.frakt_utils import (
	aktivera_frakt,
	make_eur_pall,
	make_foljesedel,
	make_frakt_item,
	make_kund_med_adress,
)

SENDIFY = "erpnext_sverige.frakt.sendify"


class FraktTestCase(IntegrationTestCase):
	def setUp(self):
		aktivera_frakt()
		self.kund = make_kund_med_adress()
		self.pall = make_eur_pall()
		self.artikel = make_frakt_item("_Test Frakt Pallvara", fraktsatt="Förpackning", forpackningstyp=self.pall,
			antal_per_forpackning=40, weight_per_unit=2, uoms=[("Box", 10)])

	def shipment(self, rader=None, **dn_falt):
		dn = make_foljesedel(self.kund, rader or [(self.artikel, 100)], **dn_falt)
		return frappe.get_doc("Shipment", bokning.skapa_shipment(dn.name)), dn


class TestSkapaShipment(FraktTestCase):
	def test_shipment_far_kollin_referenser_och_avsandare(self):
		doc, dn = self.shipment(po_no="KUND-PO-7")
		self.assertEqual(doc.docstatus, 0)
		self.assertEqual([r.delivery_note for r in doc.shipment_delivery_note], [dn.name])
		self.assertEqual((doc.avsandarens_referens, doc.mottagarens_referens), (dn.name, "KUND-PO-7"))
		self.assertEqual(doc.pickup_address_name, frappe.db.get_single_value("Fraktinstallningar", "avsandaradress"))
		self.assertEqual(len(doc.shipment_parcel), 1)
		p = doc.shipment_parcel[0]
		self.assertEqual((p.kollityp, p.count, p.length, p.width, p.height), ("Pall", 3, 120, 80, 150))
		self.assertGreater(doc.value_of_goods, 0)

	def test_kollin_raknas_pa_lagerantal(self):
		doc, _dn = self.shipment(rader=[(self.artikel, 8, "Box")])  # 80 st = 2 pallar
		self.assertEqual(doc.shipment_parcel[0].count, 2)

	def test_kundens_forval_forvaljs(self):
		produkt = frappe.get_doc({"doctype": "Fraktprodukt", "transportor": "_Test DSV", "produkt": "Pall"}).insert()
		frappe.db.set_value("Customer", self.kund, "forvald_fraktprodukt", produkt.name)
		doc, _dn = self.shipment()
		self.assertEqual(doc.fraktprodukt, produkt.name)

	def test_sandning_fran_shipment(self):
		doc, dn = self.shipment()
		s = bokning.sandning_fran_shipment(doc)
		self.assertEqual(s["referens_id"], doc.name)
		self.assertEqual(s["avsandarens_referens"], dn.name)
		self.assertEqual(s["mottagare"]["namn"], self.kund)
		self.assertEqual(s["mottagare"]["landskod"], "SE")
		self.assertEqual(s["kollin"][0]["kollityp"], "Pall")
		self.assertEqual(s["kollin"][0]["antal"], 3)

	def test_foresla_kollin_igen_ersatter_tabellen(self):
		doc, _dn = self.shipment()
		doc.shipment_parcel[0].count = 9
		doc.save()
		bokning.foresla_kollin_igen(doc.name)
		doc.reload()
		self.assertEqual(doc.shipment_parcel[0].count, 3)
```

- [ ] **Step 3: Kör och se dem misslyckas**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_bokning`
Expected: FAIL med `ImportError: cannot import name 'bokning'`.

- [ ] **Step 4: Skriv `erpnext_sverige/frakt/bokning.py`**

```python
"""Transportbokning på Shipment: skapa från följesedel, priser, spara val, boka, dokument och avbokning."""

import frappe
from erpnext.stock.doctype.delivery_note.delivery_note import make_shipment
from frappe import _
from frappe.contacts.doctype.address.address import get_address_display

from erpnext_sverige.frakt import hamta_installningar
from erpnext_sverige.frakt.kollin import foresla_kollin
from erpnext_sverige.frakt.parter import avsandare, nasta_arbetsdag, part


def _foljesedlar(doc) -> list[str]:
	return [r.delivery_note for r in doc.shipment_delivery_note if r.delivery_note]


def _lagerrader(foljesedlar) -> list[tuple[str, float]]:
	return frappe.get_all(
		"Delivery Note Item",
		filters={"parent": ["in", foljesedlar], "parenttype": "Delivery Note"},
		fields=["item_code", "stock_qty"],
		as_list=True,
	)


def satt_kollin(doc, kollin) -> None:
	doc.shipment_parcel = []
	for k in kollin:
		doc.append(
			"shipment_parcel",
			{
				"length": k["langd_cm"],
				"width": k["bredd_cm"],
				"height": k["hojd_cm"],
				"weight": k["vikt_kg"],
				"count": k["antal"],
				"kollityp": k["kollityp"],
				"stapelbar": k["stapelbar"],
				"flakmeter": k["flakmeter"],
				"beskrivning": k["beskrivning"],
			},
		)


def _visa_varningar(varningar):
	if varningar:
		frappe.msgprint("<br>".join(varningar), title=_("Kontrollera kollina"), indicator="orange")


def _forvald_fraktprodukt(dn) -> str | None:
	order = next((r.against_sales_order for r in dn.items if r.against_sales_order), None)
	if order and (produkt := frappe.db.get_value("Sales Order", order, "fraktprodukt")):
		return produkt
	return frappe.db.get_value("Customer", dn.customer, "forvald_fraktprodukt")


@frappe.whitelist()
def skapa_shipment(delivery_note: str) -> str:
	inst = hamta_installningar()
	dn = frappe.get_doc("Delivery Note", delivery_note)
	dn.check_permission("read")
	frappe.has_permission("Shipment", "create", throw=True)

	doc = make_shipment(delivery_note)
	doc.shipment_delivery_note = []
	doc.append("shipment_delivery_note", {"delivery_note": dn.name, "grand_total": dn.grand_total})
	doc.pickup_from_type = "Company"
	doc.pickup_company = inst.bolag
	doc.pickup_address_name = inst.avsandaradress
	doc.pickup_address = get_address_display(inst.avsandaradress)
	doc.pickup_date = nasta_arbetsdag()
	doc.pickup_from = inst.upphamtning_fran
	doc.pickup_to = inst.upphamtning_till
	doc.description_of_content = _("Gods enligt följesedel {0}").format(dn.name)
	doc.avsandarens_referens = dn.name
	doc.mottagarens_referens = dn.po_no
	doc.fraktprodukt = _forvald_fraktprodukt(dn)

	kollin, varningar = foresla_kollin(_lagerrader([dn.name]))
	satt_kollin(doc, kollin)
	doc.insert()
	_visa_varningar(varningar)
	return doc.name


def _utkast(shipment: str):
	doc = frappe.get_doc("Shipment", shipment)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(_("Försändelsen {0} är redan bokad eller avbruten").format(doc.name))
	return doc


@frappe.whitelist()
def foresla_kollin_igen(shipment: str) -> list[str]:
	doc = _utkast(shipment)
	kollin, varningar = foresla_kollin(_lagerrader(_foljesedlar(doc)))
	satt_kollin(doc, kollin)
	doc.save()
	return varningar


def sandning_fran_shipment(doc) -> dict:
	kund = frappe.db.get_value("Customer", doc.delivery_customer, ["customer_name", "customer_type"], as_dict=True)
	return {
		"avsandare": avsandare(hamta_installningar()),
		"mottagare": part(kund.customer_name, doc.delivery_address_name, doc.delivery_contact_name,
			privatperson=kund.customer_type == "Individual"),
		"kollin": [
			{
				"kollityp": r.kollityp or "Paket",
				"langd_cm": r.length,
				"bredd_cm": r.width,
				"hojd_cm": r.height,
				"vikt_kg": r.weight,
				"antal": r.count,
				"stapelbar": r.stapelbar,
				"flakmeter": r.flakmeter,
				"beskrivning": r.beskrivning or doc.description_of_content,
			}
			for r in doc.shipment_parcel
		],
		"referens_id": doc.name,
		"avsandarens_referens": doc.avsandarens_referens,
		"mottagarens_referens": doc.mottagarens_referens,
	}
```

- [ ] **Step 5: Kör testerna**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_bokning`
Expected: 5 tests OK. Om `make_shipment` kräver fält som saknas (felmeddelande vid `doc.insert()`), sätt dem
i `skapa_shipment` från följesedeln och notera vilket fält det var i commit-meddelandet.

- [ ] **Step 6: Commit**

```bash
pre-commit run --files erpnext_sverige/frakt/bokning.py erpnext_sverige/tests/frakt_utils.py erpnext_sverige/tests/test_frakt_bokning.py
git add erpnext_sverige/frakt/bokning.py erpnext_sverige/tests/frakt_utils.py erpnext_sverige/tests/test_frakt_bokning.py
git commit -m "feat(frakt): create shipments with suggested parcels from delivery notes"
```

---

### Task 7: Priser och spara val

**Files:**
- Modify: `erpnext_sverige/frakt/bokning.py`
- Test: `erpnext_sverige/tests/test_frakt_bokning.py`

**Interfaces:**
- Consumes: `leverantor()` (Task 1), `sendify.skapa_sandning/uppdatera_sandning/hamta_priser` (Task 4),
  `registrera_produkter` (Task 5), `sandning_fran_shipment` (Task 6), `parter.upphamtningstid`.
- Produces:
  - `bokning.hamta_priser(shipment: str) -> dict` (whitelist) `{"priser": [pris + "fraktprodukt", "kundpris",
    "forvald": bool], "varningar": list[str]}`
  - `bokning.spara_val(shipment: str, fraktprodukt: str, pris: float, valuta: str = "SEK") -> None` (whitelist)

- [ ] **Step 1: Skriv de misslyckade testerna** (lägg till i `test_frakt_bokning.py`)

```python
from erpnext_sverige.frakt import FraktFel

PRISER = [
	{"token": "T-DHL", "transportorskod": "dhl", "transportor": "_Test DHL", "produkt": "Pall", "pris": 900.0,
		"valuta": "SEK", "dagar_min": 2, "dagar_max": 3, "upphamtning": {}, "leverans": {}, "giltig_till": "2099-01-01T00:00:00Z"},
	{"token": "T-DSV", "transportorskod": "dsv", "transportor": "_Test DSV", "produkt": "Pall", "pris": 800.0,
		"valuta": "SEK", "dagar_min": 1, "dagar_max": 2, "upphamtning": {}, "leverans": {}, "giltig_till": "2099-01-01T00:00:00Z"},
]


class TestPriser(FraktTestCase):
	def test_hamta_priser_skapar_sandning_och_sorterar(self):
		doc, _dn = self.shipment()
		with (
			patch(f"{SENDIFY}.skapa_sandning", return_value="S1") as skapa,
			patch(f"{SENDIFY}.hamta_priser", return_value=([dict(p) for p in PRISER], ["UPS: Name too long"])),
		):
			svar = bokning.hamta_priser(doc.name)
		self.assertEqual(skapa.call_args.args[0]["referens_id"], doc.name)
		self.assertEqual(frappe.db.get_value("Shipment", doc.name, "sendify_id"), "S1")
		self.assertEqual([p["token"] for p in svar["priser"]], ["T-DSV", "T-DHL"])
		self.assertEqual(svar["priser"][0]["kundpris"], 900)  # 800 * 1,1 + 20
		self.assertEqual(svar["varningar"], ["UPS: Name too long"])

	def test_andra_prisforfragan_uppdaterar_sandningen(self):
		doc, _dn = self.shipment()
		frappe.db.set_value("Shipment", doc.name, "sendify_id", "S1")
		with (
			patch(f"{SENDIFY}.skapa_sandning") as skapa,
			patch(f"{SENDIFY}.uppdatera_sandning") as uppdatera,
			patch(f"{SENDIFY}.hamta_priser", return_value=([dict(p) for p in PRISER], [])),
		):
			bokning.hamta_priser(doc.name)
		skapa.assert_not_called()
		self.assertEqual(uppdatera.call_args.args[0], "S1")

	def test_forvald_produkt_markeras(self):
		doc, _dn = self.shipment()
		frappe.get_doc({"doctype": "Fraktprodukt", "transportor": "_Test DHL", "produkt": "Pall"}).insert(ignore_if_duplicate=True)
		frappe.db.set_value("Shipment", doc.name, "fraktprodukt", "_Test DHL – Pall")
		with patch(f"{SENDIFY}.skapa_sandning", return_value="S1"), patch(f"{SENDIFY}.hamta_priser", return_value=([dict(p) for p in PRISER], [])):
			svar = bokning.hamta_priser(doc.name)
		self.assertEqual([p["forvald"] for p in svar["priser"]], [False, True])

	def test_hamta_priser_visar_sendifys_faltfel(self):
		doc, _dn = self.shipment()
		fel = FraktFel("Sendify kunde inte behandla sändningen", falt_fel=["Mottagare: e-post: The field is required."])
		with patch(f"{SENDIFY}.skapa_sandning", side_effect=fel):
			with self.assertRaises(frappe.ValidationError) as undantag:
				bokning.hamta_priser(doc.name)
		self.assertIn("Mottagare: e-post", str(undantag.exception))

	def test_spara_val(self):
		doc, _dn = self.shipment()
		frappe.get_doc({"doctype": "Fraktprodukt", "transportor": "_Test DSV", "produkt": "Pall"}).insert(ignore_if_duplicate=True)
		bokning.spara_val(doc.name, "_Test DSV – Pall", 800, "SEK")
		doc.reload()
		self.assertEqual((doc.fraktprodukt, doc.fraktpris, doc.kundpris, doc.docstatus), ("_Test DSV – Pall", 800, 900, 0))
		self.assertTrue(doc.pris_hamtat)
```

- [ ] **Step 2: Kör och se dem misslyckas**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_bokning`
Expected: FAIL med `AttributeError: module 'erpnext_sverige.frakt.bokning' has no attribute 'hamta_priser'`.

- [ ] **Step 3: Implementera i `bokning.py`**

Utöka importerna:

```python
from frappe.utils import flt, now_datetime

from erpnext_sverige.frakt import hamta_installningar, leverantor, visa_fraktfel
from erpnext_sverige.frakt.fraktpris import kundpris, registrera_produkter
from erpnext_sverige.frakt.parter import avsandare, nasta_arbetsdag, part, upphamtningstid
```

och lägg till:

```python
def _synka_sandning(doc) -> str:
	"""Skapar eller uppdaterar sändningen hos leverantören och returnerar dess id."""
	lev = leverantor()
	sandning = sandning_fran_shipment(doc)
	if doc.sendify_id:
		lev.uppdatera_sandning(doc.sendify_id, sandning)
	else:
		doc.db_set("sendify_id", lev.skapa_sandning(sandning))
		frappe.db.commit()  # sändningen finns nu hos Sendify; spara id:t även om prisanropet misslyckas
	return doc.sendify_id


@frappe.whitelist()
@visa_fraktfel
def hamta_priser(shipment: str) -> dict:
	doc = _utkast(shipment)
	sendify_id = _synka_sandning(doc)
	priser, varningar = leverantor().hamta_priser(sendify_id, upphamtningstid(doc.pickup_date, doc.pickup_from))
	priser = registrera_produkter(priser)
	for p in priser:
		p["forvald"] = p["fraktprodukt"] == doc.fraktprodukt
	return {"priser": priser, "varningar": varningar}


@frappe.whitelist()
def spara_val(shipment: str, fraktprodukt: str, pris: float, valuta: str = "SEK") -> None:
	doc = _utkast(shipment)
	doc.update(
		{
			"fraktprodukt": fraktprodukt,
			"fraktpris": flt(pris),
			"fraktpris_valuta": valuta,
			"kundpris": kundpris(pris),
			"pris_hamtat": now_datetime(),
		}
	)
	doc.save()
```

- [ ] **Step 4: Kör testerna**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_bokning`
Expected: 10 tests OK.

- [ ] **Step 5: Commit**

```bash
pre-commit run --files erpnext_sverige/frakt/bokning.py erpnext_sverige/tests/test_frakt_bokning.py
git add erpnext_sverige/frakt/bokning.py erpnext_sverige/tests/test_frakt_bokning.py
git commit -m "feat(frakt): fetch carrier rates and save a chosen product on shipments"
```

---

### Task 8: Boka, boka vald produkt och fraktsedel

**Files:**
- Modify: `erpnext_sverige/frakt/bokning.py`
- Test: `erpnext_sverige/tests/test_frakt_bokning.py`

**Interfaces:**
- Consumes: `sendify.boka/hamta_dokument/hamta_sparning` (Task 4), `hamta_priser` (Task 7).
- Produces:
  - `bokning.boka(shipment: str, token: str, fraktprodukt: str, pris: float, valuta: str = "SEK") -> None` (whitelist)
  - `bokning.boka_vald_produkt(shipment: str, bekraftat: int = 0) -> dict` (whitelist) med `{"status": "bokad"}`,
    `{"status": "prisandring", "gammalt": float, "nytt": float}` eller
    `{"status": "saknas", "priser": [...], "varningar": [...]}`
  - `bokning.hamta_dokument(shipment: str) -> None` (whitelist)
  - `DOKUMENT = {"waybill": "Fraktsedel", "label": "Etikett"}`

- [ ] **Step 1: Skriv de misslyckade testerna** (lägg till i `test_frakt_bokning.py`)

```python
from contextlib import contextmanager


@contextmanager
def mockad_sendify(priser=None, boka=None, dokument=b"%PDF-1.4", sparning=None):
	with (
		patch(f"{SENDIFY}.skapa_sandning", return_value="S1"),
		patch(f"{SENDIFY}.uppdatera_sandning"),
		patch(f"{SENDIFY}.hamta_priser", return_value=([dict(p) for p in (priser or PRISER)], [])),
		patch(f"{SENDIFY}.boka", **({"side_effect": boka} if isinstance(boka, Exception)
			else {"return_value": boka or {"sparningsnummer": "TRK1", "dokumenttyper": ["label", "waybill"]}})) as b,
		patch(f"{SENDIFY}.hamta_dokument", **({"side_effect": dokument} if isinstance(dokument, Exception) else {"return_value": dokument})),
		patch(f"{SENDIFY}.hamta_sparning", return_value=sparning or []),
	):
		yield b


class TestBoka(FraktTestCase):
	def boka_dsv(self, doc):
		bokning.hamta_priser(doc.name)
		bokning.boka(doc.name, "T-DSV", "_Test DSV – Pall", 800, "SEK")
		doc.reload()

	def test_boka_uppdaterar_shipment_och_foljesedel(self):
		doc, dn = self.shipment()
		with mockad_sendify() as b:
			self.boka_dsv(doc)
		b.assert_called_once_with("T-DSV")
		self.assertEqual((doc.docstatus, doc.status), (1, "Booked"))
		self.assertEqual((doc.carrier, doc.carrier_service, doc.awb_number), ("_Test DSV", "Pall", "TRK1"))
		self.assertEqual((doc.shipment_amount, doc.kundpris, doc.service_provider), (800, 900, "Sendify"))
		self.assertEqual(
			frappe.db.get_value("Delivery Note", dn.name, ["transporter_name", "lr_no"]), ("_Test DSV", "TRK1")
		)
		filer = frappe.get_all("File", filters={"attached_to_doctype": "Shipment", "attached_to_name": doc.name}, pluck="file_name")
		self.assertEqual(sorted(filer), sorted([f"Etikett-{doc.name}.pdf", f"Fraktsedel-{doc.name}.pdf"]))
		self.assertTrue(doc.etikett_hamtad)

	def test_bokad_shipment_kan_inte_bokas_igen(self):
		doc, _dn = self.shipment()
		with mockad_sendify() as b:
			self.boka_dsv(doc)
			self.assertRaises(frappe.ValidationError, bokning.boka, doc.name, "T-DSV", "_Test DSV – Pall", 800)
		self.assertEqual(b.call_count, 1)

	def test_misslyckad_bokning_lamnar_utkast(self):
		doc, dn = self.shipment()
		with mockad_sendify(boka=FraktFel("The booking token has expired")):
			bokning.hamta_priser(doc.name)
			with self.assertRaises(frappe.ValidationError) as fel:
				bokning.boka(doc.name, "T-DSV", "_Test DSV – Pall", 800)
		self.assertIn("expired", str(fel.exception))
		self.assertEqual(frappe.db.get_value("Shipment", doc.name, "docstatus"), 0)
		self.assertFalse(frappe.db.get_value("Delivery Note", dn.name, "lr_no"))

	def test_fel_vid_dokumenthamtning_behaller_bokningen(self):
		doc, _dn = self.shipment()
		with mockad_sendify(dokument=FraktFel("Dokumentet kunde inte hämtas")):
			self.boka_dsv(doc)
		self.assertEqual((doc.status, doc.etikett_hamtad), ("Booked", 0))
		with mockad_sendify():
			bokning.hamta_dokument(doc.name)
		self.assertEqual(frappe.db.get_value("Shipment", doc.name, "etikett_hamtad"), 1)

	def test_boka_vald_produkt_utan_prisandring(self):
		doc, _dn = self.shipment()
		with mockad_sendify() as b:
			bokning.hamta_priser(doc.name)
			bokning.spara_val(doc.name, "_Test DSV – Pall", 790)  # 800 är inom 5 %
			self.assertEqual(bokning.boka_vald_produkt(doc.name), {"status": "bokad"})
		b.assert_called_once_with("T-DSV")

	def test_boka_vald_produkt_med_prisandring_kraver_bekraftelse(self):
		doc, _dn = self.shipment()
		with mockad_sendify() as b:
			bokning.hamta_priser(doc.name)
			bokning.spara_val(doc.name, "_Test DSV – Pall", 600)
			self.assertEqual(bokning.boka_vald_produkt(doc.name), {"status": "prisandring", "gammalt": 600, "nytt": 800})
			b.assert_not_called()
			self.assertEqual(bokning.boka_vald_produkt(doc.name, bekraftat=1), {"status": "bokad"})

	def test_boka_vald_produkt_som_saknas(self):
		doc, _dn = self.shipment()
		frappe.get_doc({"doctype": "Fraktprodukt", "transportor": "_Test PostNord", "produkt": "Pall"}).insert(ignore_if_duplicate=True)
		frappe.db.set_value("Shipment", doc.name, "fraktprodukt", "_Test PostNord – Pall")
		with mockad_sendify() as b:
			svar = bokning.boka_vald_produkt(doc.name)
		self.assertEqual(svar["status"], "saknas")
		self.assertEqual(len(svar["priser"]), 2)
		b.assert_not_called()
```

- [ ] **Step 2: Kör och se dem misslyckas**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_bokning`
Expected: FAIL med `AttributeError: ... has no attribute 'boka'`.

- [ ] **Step 3: Implementera i `bokning.py`**

Utöka importen: `from erpnext_sverige.frakt import FraktFel, hamta_installningar, leverantor, visa_fraktfel` och
`from frappe.utils import cint, flt, now_datetime`. Lägg till:

```python
DOKUMENT = {"waybill": "Fraktsedel", "label": "Etikett"}


@frappe.whitelist()
@visa_fraktfel
def boka(shipment: str, token: str, fraktprodukt: str, pris: float, valuta: str = "SEK") -> None:
	doc = _utkast(shipment)
	if not doc.sendify_id:
		frappe.throw(_("Hämta priser innan du bokar"))
	resultat = leverantor().boka(token)
	_spara_bokning(doc, fraktprodukt, flt(pris), valuta, resultat)


def _spara_bokning(doc, fraktprodukt, pris, valuta, resultat):
	produkt = frappe.get_doc("Fraktprodukt", fraktprodukt)
	if not doc.kundpris or doc.fraktprodukt != fraktprodukt:
		doc.kundpris = kundpris(pris)
	doc.update(
		{
			"fraktprodukt": fraktprodukt,
			"fraktpris": pris,
			"fraktpris_valuta": valuta,
			"shipment_amount": pris,
			"carrier": produkt.transportor,
			"carrier_service": produkt.produkt,
			"service_provider": produkt.leverantor,
			"shipment_id": doc.sendify_id,
			"awb_number": resultat["sparningsnummer"],
			"dokumenttyper": ",".join(resultat.get("dokumenttyper") or ["label"]),
		}
	)
	doc.submit()
	doc.db_set("status", "Booked")
	for dn in _foljesedlar(doc):
		frappe.db.set_value(
			"Delivery Note",
			dn,
			{"transporter_name": produkt.transportor, "lr_no": resultat["sparningsnummer"], "lr_date": doc.pickup_date},
		)
	frappe.db.commit()  # bokningen är gjord hos leverantören – spara innan dokument och spårning hämtas

	try:
		_hamta_dokument(doc)
	except FraktFel as fel:
		frappe.msgprint(
			_("Bokningen är klar, men fraktsedeln kunde inte hämtas: {0}. Använd knappen Hämta fraktsedel.").format(
				fel.meddelande
			),
			indicator="orange",
		)
	try:
		from erpnext_sverige.frakt.sparning import uppdatera_shipment

		uppdatera_shipment(doc)
	except (FraktFel, ImportError):
		pass  # spårningen hämtas av schemaläggaren


def _hamta_dokument(doc):
	typer = [t for t in DOKUMENT if t in (doc.dokumenttyper or "label").split(",")]
	for typ in typer:
		pdf = leverantor().hamta_dokument(doc.sendify_id, typ)
		frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{DOKUMENT[typ]}-{doc.name}.pdf",
				"attached_to_doctype": "Shipment",
				"attached_to_name": doc.name,
				"is_private": 1,
				"content": pdf,
			}
		).insert(ignore_permissions=True)
	doc.db_set("etikett_hamtad", 1)


@frappe.whitelist()
@visa_fraktfel
def hamta_dokument(shipment: str) -> None:
	doc = frappe.get_doc("Shipment", shipment)
	doc.check_permission("write")
	if doc.status not in ("Booked", "Completed"):
		frappe.throw(_("Försändelsen är inte bokad"))
	_hamta_dokument(doc)


@frappe.whitelist()
def boka_vald_produkt(shipment: str, bekraftat: int = 0) -> dict:
	doc = _utkast(shipment)
	if not doc.fraktprodukt:
		frappe.throw(_("Välj en fraktprodukt först"))
	svar = hamta_priser(shipment)
	pris = next((p for p in svar["priser"] if p["fraktprodukt"] == doc.fraktprodukt), None)
	if not pris:
		return {"status": "saknas", **svar}
	if flt(doc.fraktpris) and not cint(bekraftat):
		andring = abs(pris["pris"] - flt(doc.fraktpris)) / flt(doc.fraktpris) * 100
		if andring > flt(hamta_installningar().prisandring_grans_procent):
			return {"status": "prisandring", "gammalt": flt(doc.fraktpris), "nytt": pris["pris"]}
	boka(shipment, pris["token"], pris["fraktprodukt"], pris["pris"], pris["valuta"])
	return {"status": "bokad"}
```

`uppdatera_shipment` skapas i Task 11; tills dess fångas `ImportError` och spårningen hoppas över.

- [ ] **Step 4: Kör testerna**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_bokning`
Expected: 17 tests OK.

- [ ] **Step 5: Commit**

```bash
pre-commit run --files erpnext_sverige/frakt/bokning.py erpnext_sverige/tests/test_frakt_bokning.py
git add erpnext_sverige/frakt/bokning.py erpnext_sverige/tests/test_frakt_bokning.py
git commit -m "feat(frakt): book shipments and attach waybill and labels"
```

---

### Task 9: Avbokning och radering

**Files:**
- Modify: `erpnext_sverige/frakt/bokning.py`, `erpnext_sverige/hooks.py`
- Test: `erpnext_sverige/tests/test_frakt_bokning.py`

**Interfaces:**
- Consumes: `sendify.avboka/radera_sandning` (Task 4).
- Produces: `bokning.avboka_vid_avbrott(doc, method=None)` (Shipment `before_cancel`),
  `bokning.radera_vid_borttagning(doc, method=None)` (Shipment `on_trash`).

- [ ] **Step 1: Skriv de misslyckade testerna** (lägg till i `test_frakt_bokning.py`)

```python
class TestAvboka(FraktTestCase):
	def bokad(self):
		doc, dn = self.shipment()
		with mockad_sendify():
			bokning.hamta_priser(doc.name)
			bokning.boka(doc.name, "T-DSV", "_Test DSV – Pall", 800)
		return frappe.get_doc("Shipment", doc.name), dn

	def test_avbryt_avbokar_hos_sendify_och_tommer_foljesedeln(self):
		doc, dn = self.bokad()
		with patch(f"{SENDIFY}.avboka") as avboka:
			doc.cancel()
		avboka.assert_called_once_with("S1")
		self.assertEqual(frappe.db.get_value("Shipment", doc.name, "status"), "Cancelled")
		self.assertFalse(frappe.db.get_value("Delivery Note", dn.name, "lr_no"))

	def test_vagrad_avbokning_stoppar_avbrytandet(self):
		doc, _dn = self.bokad()
		with patch(f"{SENDIFY}.avboka", side_effect=FraktFel("Shipment already picked up")):
			self.assertRaises(frappe.ValidationError, doc.cancel)
		self.assertEqual(frappe.db.get_value("Shipment", doc.name, "docstatus"), 1)

	def test_radera_utkast_raderar_hos_sendify(self):
		doc, _dn = self.shipment()
		frappe.db.set_value("Shipment", doc.name, "sendify_id", "S9")
		with patch(f"{SENDIFY}.radera_sandning") as radera:
			frappe.delete_doc("Shipment", doc.name)
		radera.assert_called_once_with("S9")
```

- [ ] **Step 2: Kör och se dem misslyckas**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_bokning`
Expected: FAIL – `avboka` anropas inte.

- [ ] **Step 3: Implementera i `bokning.py`**

```python
def _aktiverad() -> bool:
	return bool(frappe.db.get_single_value("Fraktinstallningar", "aktiverad"))


def avboka_vid_avbrott(doc, method=None):
	"""Shipment.before_cancel: avboka hos leverantören innan försändelsen avbryts i ERPNext."""
	if not (doc.sendify_id and doc.status == "Booked"):
		return
	if not _aktiverad():
		frappe.throw(_("Aktivera transportbokning i Fraktinställningar för att kunna avboka hos Sendify"))
	try:
		leverantor().avboka(doc.sendify_id)
	except FraktFel as fel:
		frappe.throw(fel.som_html(), title=_("Sendify kunde inte avboka"))
	for dn in _foljesedlar(doc):
		frappe.db.set_value("Delivery Note", dn, {"transporter_name": None, "lr_no": None, "lr_date": None})


def radera_vid_borttagning(doc, method=None):
	"""Shipment.on_trash: radera ett obokat utkast hos leverantören."""
	if not (doc.sendify_id and doc.docstatus == 0 and _aktiverad()):
		return
	try:
		leverantor().radera_sandning(doc.sendify_id)
	except FraktFel:
		frappe.log_error(title="Sendify: kunde inte radera sändning", message=doc.sendify_id)
```

I `hooks.py` `doc_events`, lägg till:

```python
	"Shipment": {
		"before_cancel": "erpnext_sverige.frakt.bokning.avboka_vid_avbrott",
		"on_trash": "erpnext_sverige.frakt.bokning.radera_vid_borttagning",
	},
```

- [ ] **Step 4: Kör testerna**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_bokning`
Expected: 20 tests OK.

- [ ] **Step 5: Commit**

```bash
pre-commit run --files erpnext_sverige/frakt/bokning.py erpnext_sverige/hooks.py erpnext_sverige/tests/test_frakt_bokning.py
git add erpnext_sverige/frakt/bokning.py erpnext_sverige/hooks.py erpnext_sverige/tests/test_frakt_bokning.py
git commit -m "feat(frakt): cancel and delete shipments at Sendify"
```

---

### Task 10: Frakt på fakturan

**Files:**
- Modify: `erpnext_sverige/frakt/fraktpris.py`, `erpnext_sverige/hooks.py`
- Test: `erpnext_sverige/tests/test_frakt_faktura.py`

**Interfaces:**
- Consumes: bokad Shipment (Task 8), `kundpris`-fältet.
- Produces: `fraktpris.fraktrad(konto: str, beskrivning: str, belopp: float, cost_center: str) -> dict`;
  `fraktpris.lagg_frakt_pa_faktura(doc, method=None)` (Sales Invoice `before_insert`).

- [ ] **Step 1: Skriv de misslyckade testerna i `erpnext_sverige/tests/test_frakt_faktura.py`**

```python
from unittest.mock import patch

import frappe
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

from erpnext_sverige.frakt import bokning
from erpnext_sverige.tests.test_frakt_bokning import PRISER, SENDIFY, FraktTestCase, mockad_sendify


class TestFraktPaFaktura(FraktTestCase):
	def bokad_foljesedel(self):
		doc, dn = self.shipment()
		with mockad_sendify():
			bokning.hamta_priser(doc.name)
			bokning.boka(doc.name, "T-DSV", "_Test DSV – Pall", 800)
		return doc.name, dn

	def fraktrader(self, faktura):
		konto = frappe.db.get_single_value("Fraktinstallningar", "fraktkonto")
		return [t for t in faktura.taxes if t.account_head == konto]

	def test_faktura_far_fraktrad_med_kundpris(self):
		shipment, dn = self.bokad_foljesedel()
		faktura = make_sales_invoice(dn.name)
		faktura.insert()
		rader = self.fraktrader(faktura)
		self.assertEqual(len(rader), 1)
		self.assertEqual((rader[0].charge_type, rader[0].tax_amount), ("Actual", 900))
		self.assertIn(f"({shipment})", rader[0].description)

	def test_andrat_kundpris_anvands(self):
		shipment, dn = self.bokad_foljesedel()
		frappe.db.set_value("Shipment", shipment, "kundpris", 750)
		faktura = make_sales_invoice(dn.name)
		faktura.insert()
		self.assertEqual(self.fraktrader(faktura)[0].tax_amount, 750)

	def test_frakt_laggs_bara_pa_forsta_fakturan(self):
		_shipment, dn = self.bokad_foljesedel()
		forsta = make_sales_invoice(dn.name)
		forsta.items[0].qty = 50
		forsta.insert()
		andra = make_sales_invoice(dn.name)
		andra.insert()
		self.assertEqual(len(self.fraktrader(forsta)), 1)
		self.assertEqual(len(self.fraktrader(andra)), 0)

	def test_ingen_dubbel_frakt_om_fakturan_redan_har_fraktrad(self):
		_shipment, dn = self.bokad_foljesedel()
		faktura = make_sales_invoice(dn.name)
		konto = frappe.db.get_single_value("Fraktinstallningar", "fraktkonto")
		faktura.append("taxes", {"charge_type": "Actual", "account_head": konto, "description": "Frakt", "tax_amount": 100,
			"cost_center": frappe.db.get_value("Company", faktura.company, "cost_center")})
		faktura.insert()
		self.assertEqual([t.tax_amount for t in self.fraktrader(faktura)], [100])

	def test_obokad_shipment_ger_ingen_frakt(self):
		_doc, dn = self.shipment()
		faktura = make_sales_invoice(dn.name)
		faktura.insert()
		self.assertEqual(self.fraktrader(faktura), [])
```

- [ ] **Step 2: Kör och se dem misslyckas**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_faktura`
Expected: FAIL – ingen fraktrad.

- [ ] **Step 3: Implementera i `fraktpris.py`**

Utöka importerna med `from frappe import _`. Lägg till:

```python
def fraktrad(konto, beskrivning, belopp, cost_center) -> dict:
	return {
		"charge_type": "Actual",
		"account_head": konto,
		"description": beskrivning,
		"tax_amount": flt(belopp),
		"cost_center": cost_center,
	}


def lagg_frakt_pa_faktura(doc, method=None):
	"""Sales Invoice.before_insert: fraktrad per bokad Shipment på fakturans följesedlar, en gång per Shipment."""
	inst = frappe.get_cached_doc("Fraktinstallningar")
	if not (inst.aktiverad and inst.fraktkonto and doc.company == inst.bolag):
		return
	if any(t.account_head == inst.fraktkonto for t in doc.taxes):
		return
	foljesedlar = list({r.delivery_note for r in doc.items if r.delivery_note})
	if not foljesedlar:
		return
	shipments = frappe.get_all(
		"Shipment Delivery Note",
		filters={"delivery_note": ["in", foljesedlar], "parenttype": "Shipment"},
		pluck="parent",
		distinct=True,
	)
	cost_center = doc.cost_center or frappe.get_cached_value("Company", doc.company, "cost_center")
	for s in frappe.get_all(
		"Shipment",
		filters={"name": ["in", shipments], "docstatus": 1, "status": ["in", ["Booked", "Completed"]]},
		fields=["name", "kundpris", "carrier", "carrier_service"],
		order_by="name",
	):
		if not flt(s.kundpris) or _redan_fakturerad(s.name):
			continue
		beskrivning = _("Frakt {0} {1} ({2})").format(s.carrier, s.carrier_service, s.name)
		doc.append("taxes", fraktrad(inst.fraktkonto, beskrivning, s.kundpris, cost_center))


def _redan_fakturerad(shipment) -> bool:
	return bool(
		frappe.db.exists(
			"Sales Taxes and Charges",
			{"parenttype": "Sales Invoice", "description": ["like", f"%({shipment})"], "docstatus": ["<", 2]},
		)
	)
```

I `hooks.py`, lägg till `"before_insert": "erpnext_sverige.frakt.fraktpris.lagg_frakt_pa_faktura",` i den
befintliga posten `doc_events["Sales Invoice"]`.

- [ ] **Step 4: Kör testerna**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_faktura`
Expected: 5 tests OK. Kör även `--module erpnext_sverige.tests.test_invoice` och `test_print_formats` för att se att
befintliga fakturatester inte påverkas.

- [ ] **Step 5: Commit**

```bash
pre-commit run --files erpnext_sverige/frakt/fraktpris.py erpnext_sverige/hooks.py erpnext_sverige/tests/test_frakt_faktura.py
git add erpnext_sverige/frakt/fraktpris.py erpnext_sverige/hooks.py erpnext_sverige/tests/test_frakt_faktura.py
git commit -m "feat(frakt): add booked freight to sales invoices once per shipment"
```

---

### Task 11: Spårning

**Files:**
- Create: `erpnext_sverige/frakt/sparning.py`
- Modify: `erpnext_sverige/hooks.py`
- Test: `erpnext_sverige/tests/test_frakt_sparning.py`

**Interfaces:**
- Consumes: `sendify.hamta_sparning` (Task 4), bokad Shipment (Task 8).
- Produces: `sparning.uppdatera_shipment(doc) -> None`; `sparning.uppdatera(shipment: str) -> None` (whitelist);
  `sparning.uppdatera_alla() -> None` (scheduler `hourly`).

- [ ] **Step 1: Skriv de misslyckade testerna i `erpnext_sverige/tests/test_frakt_sparning.py`**

```python
from datetime import datetime, timedelta
from unittest.mock import patch

import frappe
from frappe.utils import now_datetime

from erpnext_sverige.frakt import bokning, sparning
from erpnext_sverige.tests.test_frakt_bokning import SENDIFY, FraktTestCase, mockad_sendify


def handelse(status, timme, beskrivning="Händelse"):
	return {"tidpunkt": datetime(2026, 10, 5, timme), "status": status, "beskrivning": beskrivning, "plats": "Borås",
		"url": "https://sendify/t/S1"}


class TestSparning(FraktTestCase):
	def bokad(self):
		doc, _dn = self.shipment()
		with mockad_sendify():
			bokning.hamta_priser(doc.name)
			bokning.boka(doc.name, "T-DSV", "_Test DSV – Pall", 800)
		return doc.name

	def test_nya_handelser_laggs_till_en_gang(self):
		namn = self.bokad()
		with patch(f"{SENDIFY}.hamta_sparning", return_value=[handelse("ORDERED", 8), handelse("IN_TRANSIT", 12, "På väg")]):
			sparning.uppdatera(namn)
			sparning.uppdatera(namn)
		doc = frappe.get_doc("Shipment", namn)
		self.assertEqual([h.status for h in doc.sparningshandelser], ["ORDERED", "IN_TRANSIT"])
		self.assertEqual((doc.tracking_status, doc.senaste_sparningsstatus), ("In Progress", "IN_TRANSIT"))
		self.assertEqual(doc.senaste_sparning, "På väg (Borås)")
		self.assertEqual(doc.tracking_url, "https://sendify/t/S1")

	def test_levererad_slutfor_shipment(self):
		namn = self.bokad()
		with patch(f"{SENDIFY}.hamta_sparning", return_value=[handelse("DELIVERED", 14, "Levererad")]):
			sparning.uppdatera(namn)
		self.assertEqual(frappe.db.get_value("Shipment", namn, ["tracking_status", "status"]), ("Delivered", "Completed"))

	def test_schemalagt_jobb_respekterar_intervall(self):
		namn = self.bokad()
		frappe.db.set_single_value("Fraktinstallningar", {"sparning_intervall": "Var fjärde timme",
			"senaste_sparningskorning": now_datetime() - timedelta(hours=1)})
		frappe.clear_document_cache("Fraktinstallningar", "Fraktinstallningar")
		with patch(f"{SENDIFY}.hamta_sparning", return_value=[handelse("IN_TRANSIT", 12)]) as hamta:
			sparning.uppdatera_alla()
			hamta.assert_not_called()
			frappe.db.set_single_value("Fraktinstallningar", "senaste_sparningskorning", now_datetime() - timedelta(hours=5))
			frappe.clear_document_cache("Fraktinstallningar", "Fraktinstallningar")
			sparning.uppdatera_alla()
		self.assertIn("S1", [c.args[0] for c in hamta.call_args_list])
		self.assertEqual(frappe.db.get_value("Shipment", namn, "tracking_status"), "In Progress")
```

- [ ] **Step 2: Kör och se dem misslyckas**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_sparning`
Expected: FAIL med `ImportError: cannot import name 'sparning'`.

- [ ] **Step 3: Skriv `erpnext_sverige/frakt/sparning.py`**

```python
"""Spårning av bokade försändelser."""

from datetime import timedelta

import frappe
from frappe.utils import get_datetime, now_datetime

from erpnext_sverige.frakt import FraktFel, leverantor, visa_fraktfel

LEVERERAD = "DELIVERED"
INTERVALL_TIMMAR = {"Varje timme": 1, "Var fjärde timme": 4, "Dagligen": 24}


def uppdatera_shipment(doc) -> None:
	handelser = sorted(leverantor().hamta_sparning(doc.sendify_id), key=lambda h: h["tidpunkt"])
	if not handelser:
		return
	kanda = {(get_datetime(h.tidpunkt), h.status) for h in doc.sparningshandelser}
	for h in handelser:
		if (get_datetime(h["tidpunkt"]), h["status"]) not in kanda:
			doc.append(
				"sparningshandelser",
				{"tidpunkt": h["tidpunkt"], "status": h["status"], "beskrivning": h["beskrivning"], "plats": h["plats"]},
			)
	senaste = handelser[-1]
	doc.senaste_sparning = f"{senaste['beskrivning']} ({senaste['plats']})" if senaste["plats"] else senaste["beskrivning"]
	doc.senaste_sparningsstatus = senaste["status"]
	doc.save(ignore_permissions=True)
	if senaste.get("url"):
		doc.db_set("tracking_url", senaste["url"])
	if senaste["status"] == LEVERERAD:
		doc.db_set({"tracking_status": "Delivered", "status": "Completed"})
	else:
		doc.db_set("tracking_status", "In Progress")


@frappe.whitelist()
@visa_fraktfel
def uppdatera(shipment: str) -> None:
	doc = frappe.get_doc("Shipment", shipment)
	doc.check_permission("read")
	if doc.sendify_id and doc.docstatus == 1:
		uppdatera_shipment(doc)


def uppdatera_alla() -> None:
	inst = frappe.get_cached_doc("Fraktinstallningar")
	if not inst.aktiverad:
		return
	timmar = INTERVALL_TIMMAR.get(inst.sparning_intervall, 1)
	if inst.senaste_sparningskorning and now_datetime() - get_datetime(inst.senaste_sparningskorning) < timedelta(
		hours=timmar, minutes=-5
	):
		return
	for namn in frappe.get_all(
		"Shipment", filters={"docstatus": 1, "status": "Booked", "sendify_id": ["is", "set"]}, pluck="name"
	):
		doc = frappe.get_doc("Shipment", namn)
		if doc.tracking_status in ("Returned", "Lost"):
			continue
		try:
			uppdatera_shipment(doc)
			frappe.db.commit()
		except FraktFel:
			frappe.db.rollback()
			frappe.log_error(title=f"Sendify: spårning misslyckades för {namn}")
	frappe.db.set_single_value("Fraktinstallningar", "senaste_sparningskorning", now_datetime())
```

I `hooks.py`, lägg till (ny nyckel på modulnivå):

```python
scheduler_events = {
	"hourly": ["erpnext_sverige.frakt.sparning.uppdatera_alla"],
}
```

- [ ] **Step 4: Kör testerna**

Run:
```bash
bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_sparning
bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_bokning
```
Expected: 3 + 20 tests OK.

- [ ] **Step 5: Commit**

```bash
pre-commit run --files erpnext_sverige/frakt/sparning.py erpnext_sverige/hooks.py erpnext_sverige/tests/test_frakt_sparning.py
git add erpnext_sverige/frakt/sparning.py erpnext_sverige/hooks.py erpnext_sverige/tests/test_frakt_sparning.py
git commit -m "feat(frakt): poll Sendify tracking for booked shipments"
```

---

### Task 12: Prisförfrågan på offert och order, och transportörsprodukter

**Files:**
- Modify: `erpnext_sverige/frakt/fraktpris.py`
- Modify: `erpnext_sverige/frakt/doctype/fraktinstallningar/fraktinstallningar.py`
- Test: `erpnext_sverige/tests/test_frakt_fraktpris.py`

**Interfaces:**
- Consumes: `foresla_kollin`, `parter.*`, `leverantor()`, `registrera_produkter`, `fraktrad`.
- Produces (whitelist):
  - `fraktpris.kontrollera(doctype: str, name: str) -> dict` (`{"priser", "varningar"}` som `bokning.hamta_priser`)
  - `fraktpris.lagg_till_frakt(doctype: str, name: str, fraktprodukt: str, kundpris: float) -> None`
  - `fraktpris.spara_val_order(doctype: str, name: str, fraktprodukt: str) -> None`
  - `fraktinstallningar.testa_anslutning() -> str`, `fraktinstallningar.hamta_transportorsprodukter() -> int`

- [ ] **Step 1: Skriv de misslyckade testerna** (lägg till i `test_frakt_fraktpris.py`)

```python
from unittest.mock import patch

from erpnext_sverige.frakt.doctype.fraktinstallningar import fraktinstallningar
from erpnext_sverige.tests.frakt_utils import make_eur_pall, make_frakt_item
from erpnext_sverige.tests.test_frakt_bokning import PRISER, SENDIFY
from erpnext_sverige.tests.utils import COMPANY


class TestPrisforfragan(IntegrationTestCase):
	def setUp(self):
		aktivera_frakt()
		self.kund = make_kund_med_adress()
		self.artikel = make_frakt_item("_Test Frakt Pallvara", fraktsatt="Förpackning", forpackningstyp=make_eur_pall(),
			antal_per_forpackning=40, weight_per_unit=2)

	def order(self):
		return frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": COMPANY,
				"customer": self.kund,
				"delivery_date": frappe.utils.add_days(frappe.utils.today(), 7),
				"shipping_address_name": frappe.db.get_value("Address", {"address_title": f"{self.kund} leverans"}),
				"items": [{"item_code": self.artikel, "qty": 60, "rate": 100,
					"delivery_date": frappe.utils.add_days(frappe.utils.today(), 7)}],
			}
		).insert()

	def test_kontrollera_skapar_och_raderar_tillfallig_sandning(self):
		so = self.order()
		with (
			patch(f"{SENDIFY}.skapa_sandning", return_value="TMP1") as skapa,
			patch(f"{SENDIFY}.hamta_priser", return_value=([dict(p) for p in PRISER], [])),
			patch(f"{SENDIFY}.radera_sandning") as radera,
		):
			svar = fraktpris.kontrollera("Sales Order", so.name)
		self.assertEqual(skapa.call_args.args[0]["kollin"][0]["antal"], 2)
		radera.assert_called_once_with("TMP1")
		self.assertEqual([p["transportor"] for p in svar["priser"]], ["_Test DSV", "_Test DHL"])

	def test_tillfallig_sandning_raderas_aven_vid_fel(self):
		so = self.order()
		from erpnext_sverige.frakt import FraktFel

		with (
			patch(f"{SENDIFY}.skapa_sandning", return_value="TMP1"),
			patch(f"{SENDIFY}.hamta_priser", side_effect=FraktFel("Route not supported")),
			patch(f"{SENDIFY}.radera_sandning") as radera,
		):
			self.assertRaises(frappe.ValidationError, fraktpris.kontrollera, "Sales Order", so.name)
		radera.assert_called_once_with("TMP1")

	def test_lagg_till_frakt_pa_utkast_ersatter_befintlig_rad(self):
		so = self.order()
		frappe.get_doc({"doctype": "Fraktprodukt", "transportor": "_Test DSV", "produkt": "Pall"}).insert(ignore_if_duplicate=True)
		fraktpris.lagg_till_frakt("Sales Order", so.name, "_Test DSV – Pall", 900)
		fraktpris.lagg_till_frakt("Sales Order", so.name, "_Test DSV – Pall", 950)
		so.reload()
		konto = frappe.db.get_single_value("Fraktinstallningar", "fraktkonto")
		self.assertEqual([t.tax_amount for t in so.taxes if t.account_head == konto], [950])
		self.assertEqual(so.fraktprodukt, "_Test DSV – Pall")

	def test_lagg_till_frakt_pa_godkand_order_vagras(self):
		so = self.order()
		so.submit()
		self.assertRaises(frappe.ValidationError, fraktpris.lagg_till_frakt, "Sales Order", so.name, "_Test DSV – Pall", 900)

	def test_hamta_transportorsprodukter(self):
		with (
			patch(f"{SENDIFY}.skapa_sandning", return_value="TMP2"),
			patch(f"{SENDIFY}.hamta_priser", return_value=([dict(p) for p in PRISER], [])),
			patch(f"{SENDIFY}.radera_sandning"),
		):
			self.assertEqual(fraktinstallningar.hamta_transportorsprodukter(), 2)
		self.assertTrue(frappe.db.exists("Fraktprodukt", "_Test DHL – Pall"))
```

- [ ] **Step 2: Kör och se dem misslyckas**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_fraktpris`
Expected: FAIL med `AttributeError: ... has no attribute 'kontrollera'`.

- [ ] **Step 3: Implementera i `fraktpris.py`**

Utöka importerna:

```python
from erpnext_sverige.frakt import FraktFel, hamta_installningar, leverantor, visa_fraktfel
from erpnext_sverige.frakt.kollin import foresla_kollin
from erpnext_sverige.frakt.parter import avsandare, nasta_arbetsdag, part, upphamtningstid
```

och lägg till:

```python
FORSALJNING = ("Quotation", "Sales Order")


def priser_for_tillfallig_sandning(sandning, upphamtning) -> dict:
	"""Skapar en sändning hos leverantören, hämtar priser och raderar sändningen igen."""
	lev = leverantor()
	sendify_id = lev.skapa_sandning(sandning)
	try:
		priser, varningar = lev.hamta_priser(sendify_id, upphamtning)
	finally:
		try:
			lev.radera_sandning(sendify_id)
		except FraktFel:
			frappe.log_error(title="Sendify: kunde inte radera tillfällig sändning", message=sendify_id)
	return {"priser": registrera_produkter(priser), "varningar": varningar}


@frappe.whitelist()
@visa_fraktfel
def kontrollera(doctype: str, name: str) -> dict:
	if doctype not in FORSALJNING:
		frappe.throw(_("Fraktpris kan bara kontrolleras på offert och försäljningsorder"))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	inst = hamta_installningar()
	kollin, varningar = foresla_kollin([(r.item_code, r.stock_qty) for r in doc.items])
	if not kollin:
		frappe.throw(_("Inga kollin kunde föreslås: {0}").format(", ".join(varningar)))
	kund = doc.customer if doctype == "Sales Order" else (doc.party_name if doc.quotation_to == "Customer" else None)
	privat = bool(kund) and frappe.db.get_value("Customer", kund, "customer_type") == "Individual"
	sandning = {
		"avsandare": avsandare(inst),
		"mottagare": part(doc.customer_name, doc.shipping_address_name or doc.customer_address, doc.contact_person, privat),
		"kollin": kollin,
		"referens_id": f"{doctype} {name}",
	}
	datum = doc.get("delivery_date") or nasta_arbetsdag()
	svar = priser_for_tillfallig_sandning(sandning, upphamtningstid(datum, inst.upphamtning_fran))
	svar["varningar"] = varningar + svar["varningar"]
	for p in svar["priser"]:
		p["forvald"] = p["fraktprodukt"] == doc.get("fraktprodukt")
	return svar


@frappe.whitelist()
def lagg_till_frakt(doctype: str, name: str, fraktprodukt: str, kundpris: float) -> None:
	if doctype not in FORSALJNING:
		frappe.throw(_("Frakt kan bara läggas till på offert och försäljningsorder"))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(_("Frakt kan bara läggas till på ett utkast. Använd Spara val på godkända dokument."))
	inst = hamta_installningar()
	produkt = frappe.get_doc("Fraktprodukt", fraktprodukt)
	beskrivning = _("Frakt {0} {1}").format(produkt.transportor, produkt.produkt)
	befintlig = next((t for t in doc.taxes if t.account_head == inst.fraktkonto), None)
	if befintlig:
		befintlig.update({"charge_type": "Actual", "tax_amount": flt(kundpris), "description": beskrivning})
	else:
		cost_center = frappe.get_cached_value("Company", doc.company, "cost_center")
		doc.append("taxes", fraktrad(inst.fraktkonto, beskrivning, kundpris, cost_center))
	doc.fraktprodukt = fraktprodukt
	doc.save()


@frappe.whitelist()
def spara_val_order(doctype: str, name: str, fraktprodukt: str) -> None:
	if doctype not in FORSALJNING:
		frappe.throw(_("Fel dokumenttyp"))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")
	doc.db_set("fraktprodukt", fraktprodukt)
```

- [ ] **Step 4: Lägg till knappfunktionerna i `fraktinstallningar.py`** (modulnivå, under klassen)

```python
from erpnext_sverige.frakt import hamta_installningar, leverantor, visa_fraktfel


@frappe.whitelist()
@visa_fraktfel
def testa_anslutning() -> str:
	frappe.only_for(("System Manager", "Stock Manager"))
	return leverantor().kontrollera_nyckel(hamta_installningar())


@frappe.whitelist()
@visa_fraktfel
def hamta_transportorsprodukter() -> int:
	"""Prisförfrågan på en exempelsändning (en EUR-pall från avsändaren till sig själv) för att fylla registret."""
	from erpnext_sverige.frakt.fraktpris import priser_for_tillfallig_sandning
	from erpnext_sverige.frakt.parter import avsandare, nasta_arbetsdag, upphamtningstid

	frappe.only_for(("System Manager", "Stock Manager"))
	inst = hamta_installningar()
	part = avsandare(inst)
	sandning = {
		"avsandare": part,
		"mottagare": part,
		"kollin": [
			{"kollityp": "Pall", "langd_cm": 120, "bredd_cm": 80, "hojd_cm": 100, "vikt_kg": 200, "antal": 1,
				"stapelbar": 0, "flakmeter": 0, "beskrivning": _("Exempelsändning")},
		],
		"referens_id": "ERPNext exempelsändning",
	}
	svar = priser_for_tillfallig_sandning(sandning, upphamtningstid(nasta_arbetsdag(), inst.upphamtning_fran))
	return len(svar["priser"])
```

- [ ] **Step 5: Kör testerna**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_fraktpris`
Expected: 10 tests OK.

- [ ] **Step 6: Commit**

```bash
pre-commit run --files erpnext_sverige/frakt/fraktpris.py erpnext_sverige/frakt/doctype/fraktinstallningar/fraktinstallningar.py erpnext_sverige/tests/test_frakt_fraktpris.py
git add erpnext_sverige/frakt/fraktpris.py erpnext_sverige/frakt/doctype/fraktinstallningar/fraktinstallningar.py erpnext_sverige/tests/test_frakt_fraktpris.py
git commit -m "feat(frakt): check freight prices on quotations and sales orders"
```

---

### Task 13: Gränssnitt (knappar och prisdialog)

**Files:**
- Create: `erpnext_sverige/public/js/frakt_prisdialog.js`, `erpnext_sverige/public/js/frakt_shipment.js`,
  `erpnext_sverige/public/js/frakt_forsaljning.js`,
  `erpnext_sverige/frakt/doctype/fraktinstallningar/fraktinstallningar.js`
- Modify: `erpnext_sverige/hooks.py` (`doctype_js`)

**Interfaces:**
- Consumes: whitelistade metoder från Task 6–12 (exakta sökvägar nedan).
- Produces: `window.erpnext_sverige_frakt.visa_priser(svar, alternativ)` där `alternativ` =
  `{title, primar: {label, action(pris)}, sekundar: {label, action(pris)} | null}`.

- [ ] **Step 1: Skriv `public/js/frakt_prisdialog.js`**

```javascript
// Gemensam prisdialog för Shipment, offert och försäljningsorder.
window.erpnext_sverige_frakt = {
	format_dagar(p) {
		if (p.dagar_min == null) return "";
		return p.dagar_min === p.dagar_max ? `${p.dagar_min}` : `${p.dagar_min}–${p.dagar_max}`;
	},

	visa_priser(svar, alternativ) {
		const priser = svar.priser || [];
		const esc = frappe.utils.escape_html;
		const rader = priser
			.map(
				(p, i) => `
			<tr data-index="${i}" class="${p.forvald ? "table-active" : ""}" style="cursor:pointer">
				<td><input type="radio" name="frakt_pris" value="${i}" ${p.forvald ? "checked" : ""}></td>
				<td>${esc(p.transportor)}${p.forvald ? ` <span class="indicator-pill blue">${__("Förval")}</span>` : ""}</td>
				<td>${esc(p.produkt)}</td>
				<td class="text-right">${format_currency(p.pris, p.valuta)}</td>
				<td class="text-right">${format_currency(p.kundpris, p.valuta)}</td>
				<td class="text-center">${this.format_dagar(p)}</td>
				<td>${esc((p.upphamtning && p.upphamtning.date) || "")}</td>
				<td>${esc((p.leverans && p.leverans.earliest_date) || "")}</td>
			</tr>`
			)
			.join("");
		const varningar = (svar.varningar || []).length
			? `<div class="alert alert-warning mt-3"><b>${__("Transportörer som inte kunde erbjudas")}</b><ul>${svar.varningar
					.map((v) => `<li>${esc(v)}</li>`)
					.join("")}</ul></div>`
			: "";
		const tabell = priser.length
			? `<table class="table table-bordered table-hover">
				<thead><tr><th></th><th>${__("Transportör")}</th><th>${__("Produkt")}</th>
				<th class="text-right">${__("Pris")}</th><th class="text-right">${__("Kundpris")}</th>
				<th class="text-center">${__("Dagar")}</th><th>${__("Upphämtning")}</th><th>${__("Leverans")}</th></tr></thead>
				<tbody>${rader}</tbody></table>`
			: `<p>${__("Inga priser hittades.")}</p>`;

		const valt = () => {
			const v = dialog.$wrapper.find("input[name=frakt_pris]:checked").val();
			if (v === undefined) {
				frappe.msgprint(__("Välj ett alternativ"));
				return null;
			}
			return priser[cint(v)];
		};
		const dialog = new frappe.ui.Dialog({
			title: alternativ.title || __("Fraktpriser"),
			size: "extra-large",
			fields: [{ fieldtype: "HTML", fieldname: "priser", options: tabell + varningar }],
			primary_action_label: alternativ.primar.label,
			primary_action: () => {
				const p = valt();
				if (!p) return;
				if (p.giltig_till && new Date(p.giltig_till) < new Date()) {
					frappe.msgprint(__("Priset har gått ut. Hämta priser igen."));
					dialog.hide();
					return;
				}
				dialog.hide();
				alternativ.primar.action(p);
			},
			secondary_action_label: alternativ.sekundar ? alternativ.sekundar.label : __("Stäng"),
			secondary_action: () => {
				if (!alternativ.sekundar) return dialog.hide();
				const p = valt();
				if (!p) return;
				dialog.hide();
				alternativ.sekundar.action(p);
			},
		});
		dialog.$wrapper.on("click", "tr[data-index]", function () {
			$(this).find("input[name=frakt_pris]").prop("checked", true);
		});
		dialog.show();
		return dialog;
	},
};
```

- [ ] **Step 2: Skriv `public/js/frakt_shipment.js`**

```javascript
// Knappar för transportbokning på Shipment.
const FRAKT_BOKNING = "erpnext_sverige.frakt.bokning";

frappe.ui.form.on("Shipment", {
	refresh(frm) {
		if (frm.is_new()) return;
		const grupp = __("Sendify");
		const frakt = window.erpnext_sverige_frakt;

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Föreslå kollin igen"), () =>
				frappe.confirm(__("Kollitabellen ersätts med ett nytt förslag. Fortsätta?"), () =>
					frappe.call({ method: `${FRAKT_BOKNING}.foresla_kollin_igen`, args: { shipment: frm.doc.name }, freeze: true })
						.then(() => frm.reload_doc())
				), grupp);

			frm.add_custom_button(__("Hämta priser"), () => hamta_priser(frm), grupp);

			if (frm.doc.fraktprodukt) {
				const label = frm.doc.fraktpris ? __("Boka vald produkt") : __("Boka med förval");
				frm.add_custom_button(label, () => boka_vald(frm, 0), grupp);
			}
		}

		if (["Booked", "Completed"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Hämta fraktsedel"), () =>
				frappe.call({ method: `${FRAKT_BOKNING}.hamta_dokument`, args: { shipment: frm.doc.name }, freeze: true })
					.then(() => frm.reload_doc()), grupp);
			frm.add_custom_button(__("Uppdatera spårning"), () =>
				frappe.call({ method: "erpnext_sverige.frakt.sparning.uppdatera", args: { shipment: frm.doc.name }, freeze: true })
					.then(() => frm.reload_doc()), grupp);
			if (frm.doc.tracking_url) {
				frm.add_custom_button(__("Öppna spårning"), () => window.open(frm.doc.tracking_url), grupp);
			}
		}

		if (frm.doc.senaste_sparningsstatus === "EXCEPTION") {
			frm.dashboard.set_headline_alert(__("Avvikelse hos transportören: {0}", [frm.doc.senaste_sparning]), "red");
		}

		function hamta_priser(frm) {
			frappe.call({
				method: `${FRAKT_BOKNING}.hamta_priser`,
				args: { shipment: frm.doc.name },
				freeze: true,
				freeze_message: __("Hämtar priser från Sendify …"),
			}).then(({ message }) => visa(frm, message));
		}

		function visa(frm, svar) {
			frakt.visa_priser(svar, {
				title: __("Fraktpriser för {0}", [frm.doc.name]),
				primar: {
					label: __("Boka"),
					action: (p) =>
						frappe.call({
							method: `${FRAKT_BOKNING}.boka`,
							args: { shipment: frm.doc.name, token: p.token, fraktprodukt: p.fraktprodukt, pris: p.pris, valuta: p.valuta },
							freeze: true,
							freeze_message: __("Bokar …"),
						}).then(() => frm.reload_doc()),
				},
				sekundar: {
					label: __("Spara val"),
					action: (p) =>
						frappe.call({
							method: `${FRAKT_BOKNING}.spara_val`,
							args: { shipment: frm.doc.name, fraktprodukt: p.fraktprodukt, pris: p.pris, valuta: p.valuta },
						}).then(() => frm.reload_doc()),
				},
			});
		}

		function boka_vald(frm, bekraftat) {
			frappe.call({
				method: `${FRAKT_BOKNING}.boka_vald_produkt`,
				args: { shipment: frm.doc.name, bekraftat },
				freeze: true,
				freeze_message: __("Bokar …"),
			}).then(({ message: svar }) => {
				if (svar.status === "bokad") return frm.reload_doc();
				if (svar.status === "prisandring") {
					return frappe.confirm(
						__("Priset har ändrats från {0} till {1}. Boka ändå?", [format_currency(svar.gammalt), format_currency(svar.nytt)]),
						() => boka_vald(frm, 1)
					);
				}
				frappe.show_alert({ message: __("{0} finns inte bland alternativen just nu", [frm.doc.fraktprodukt]), indicator: "orange" });
				visa(frm, svar);
			});
		}
	},
});
```

- [ ] **Step 3: Skriv `public/js/frakt_forsaljning.js`**

```javascript
// "Boka transport" på följesedel och "Kontrollera fraktpris" på offert och försäljningsorder.
const FRAKT_PRIS = "erpnext_sverige.frakt.fraktpris";

frappe.ui.form.on("Delivery Note", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		if (frm.doc.lr_no) {
			// Spårningslänk från den bokade försändelsen
			frappe.db
				.get_list("Shipment", {
					filters: [["Shipment Delivery Note", "delivery_note", "=", frm.doc.name], ["docstatus", "=", 1]],
					fields: ["name", "tracking_url", "senaste_sparning"],
					limit: 1,
				})
				.then(([s]) => {
					if (!s || !s.tracking_url) return;
					frm.dashboard.add_comment(
						__("Spårning {0}: {1}", [
							`<a href="${encodeURI(s.tracking_url)}" target="_blank" rel="noopener">${frappe.utils.escape_html(frm.doc.lr_no)}</a>`,
							frappe.utils.escape_html(s.senaste_sparning || ""),
						]),
						"blue",
						true
					);
				});
		}
		frm.add_custom_button(
			__("Boka transport"),
			() =>
				frappe.call({
					method: "erpnext_sverige.frakt.bokning.skapa_shipment",
					args: { delivery_note: frm.doc.name },
					freeze: true,
				}).then(({ message }) => frappe.set_route("Form", "Shipment", message)),
			__("Create")
		);
	},
});

const erpnext_sverige_fraktpris = {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus === 2) return;
		frm.add_custom_button(__("Kontrollera fraktpris"), () => {
			frappe.call({
				method: `${FRAKT_PRIS}.kontrollera`,
				args: { doctype: frm.doctype, name: frm.doc.name },
				freeze: true,
				freeze_message: __("Hämtar priser från Sendify …"),
			}).then(({ message }) => {
				const utkast = frm.doc.docstatus === 0;
				window.erpnext_sverige_frakt.visa_priser(message, {
					title: __("Fraktpris för {0}", [frm.doc.name]),
					primar: utkast
						? {
								label: __("Lägg till frakt"),
								action: (p) =>
									frappe.call({
										method: `${FRAKT_PRIS}.lagg_till_frakt`,
										args: { doctype: frm.doctype, name: frm.doc.name, fraktprodukt: p.fraktprodukt, kundpris: p.kundpris },
									}).then(() => frm.reload_doc()),
							}
						: {
								label: __("Spara val"),
								action: (p) =>
									frappe.call({
										method: `${FRAKT_PRIS}.spara_val_order`,
										args: { doctype: frm.doctype, name: frm.doc.name, fraktprodukt: p.fraktprodukt },
									}).then(() => frm.reload_doc()),
							},
					sekundar: null,
				});
			});
		});
	},
};

frappe.ui.form.on("Quotation", erpnext_sverige_fraktpris);
frappe.ui.form.on("Sales Order", erpnext_sverige_fraktpris);
```

- [ ] **Step 4: Skriv `frakt/doctype/fraktinstallningar/fraktinstallningar.js`**

```javascript
const FRAKT_INST = "erpnext_sverige.frakt.doctype.fraktinstallningar.fraktinstallningar";

frappe.ui.form.on("Fraktinstallningar", {
	refresh(frm) {
		if (!frm.doc.aktiverad) return;
		frm.add_custom_button(__("Testa anslutning"), () =>
			frappe.call({ method: `${FRAKT_INST}.testa_anslutning`, freeze: true }).then(({ message }) =>
				frappe.msgprint({ title: __("Anslutningen fungerar"), indicator: "green", message: __("Sendify-team: {0}", [message]) })
			)
		);
		frm.add_custom_button(__("Hämta transportörsprodukter"), () =>
			frappe.call({ method: `${FRAKT_INST}.hamta_transportorsprodukter`, freeze: true }).then(({ message }) =>
				frappe.msgprint(__("{0} transportörsprodukter finns nu i registret Fraktprodukt", [message]))
			)
		);
	},
});
```

- [ ] **Step 5: Koppla JS i `hooks.py`**

Ersätt `doctype_js` med:

```python
doctype_js = {
	"Customer": "public/js/vies.js",
	"Supplier": "public/js/vies.js",
	"Shipment": ["public/js/frakt_prisdialog.js", "public/js/frakt_shipment.js"],
	"Delivery Note": ["public/js/frakt_forsaljning.js"],
	"Quotation": ["public/js/frakt_prisdialog.js", "public/js/frakt_forsaljning.js"],
	"Sales Order": ["public/js/frakt_prisdialog.js", "public/js/frakt_forsaljning.js"],
}
```

- [ ] **Step 6: Bygg, kör prettier/eslint och verifiera i webbläsaren**

Run:
```bash
cd ~/ERPNext/my-frappe-bench/apps/erpnext_sverige
pre-commit run --files erpnext_sverige/public/js/frakt_*.js erpnext_sverige/frakt/doctype/fraktinstallningar/fraktinstallningar.js erpnext_sverige/hooks.py
cd ~/ERPNext/my-frappe-bench
bench build --app erpnext_sverige
bench --site test-erp.local clear-cache
bench --site test-erp.local serve --port 8001   # Redis måste vara igång (bench start eller redis-server)
```

Kontrollera manuellt på http://localhost:8001 (Administrator/admin), med mockfri Sendify först efter Task 14:
1. Fraktinställningar: knapparna syns bara när *Aktiverad* är ikryssad.
2. Godkänd följesedel: *Skapa → Boka transport* öppnar en Shipment med kollin och referenser.
3. Shipment-utkast: gruppen *Sendify* har *Föreslå kollin igen* och *Hämta priser*.
4. Försäljningsorder: *Kontrollera fraktpris* finns.
4b. Följesedel med bokad försändelse (sätt `lr_no` och Shipmentens `tracking_url` för hand om ingen riktig
    bokning finns): en blå rad "Spårning …" med länk visas överst i formuläret.
5. Webbläsarens konsol visar inga JS-fel när formulären öppnas.

- [ ] **Step 7: Commit**

```bash
git add erpnext_sverige/public/js/frakt_prisdialog.js erpnext_sverige/public/js/frakt_shipment.js erpnext_sverige/public/js/frakt_forsaljning.js erpnext_sverige/frakt/doctype/fraktinstallningar/fraktinstallningar.js erpnext_sverige/hooks.py
git commit -m "feat(frakt): add booking buttons and rate dialog"
```

---

### Task 14: Röktest mot Sendifys sandlåda och slutkontroll

**Förutsättning:** Ett Sendify-sandlådekonto (https://se.sendify-staging.com/sign-up, *Settings → API*). Lägg nyckeln
i `sites/test-erp.local/site_config.json` som `"sendify_sandbox_api_key": "<nyckel>"`. Utan nyckel hoppas testet
över – be användaren skapa kontot innan detta steg.

**Files:**
- Create: `erpnext_sverige/tests/test_frakt_sandlada.py`

- [ ] **Step 1: Skriv `erpnext_sverige/tests/test_frakt_sandlada.py`**

```python
"""Röktest mot Sendifys sandlåda. Körs bara om sendify_sandbox_api_key finns i site_config."""

import unittest
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.frakt import sendify
from erpnext_sverige.frakt.parter import nasta_arbetsdag, upphamtningstid

NYCKEL = frappe.conf.get("sendify_sandbox_api_key")
PART = {"adressrad_1": "Testgatan 1", "postnummer": "41107", "ort": "Göteborg", "landskod": "SE",
	"kontakt_namn": "Test Testsson", "telefon": "0701234567", "epost": "test@example.com", "privatperson": False}


@unittest.skipUnless(NYCKEL, "sendify_sandbox_api_key saknas i site_config")
class TestSendifySandlada(IntegrationTestCase):
	def setUp(self):
		inst = frappe._dict(miljo="Sandlåda", get_password=lambda falt: NYCKEL)
		p = patch("erpnext_sverige.frakt.sendify.hamta_installningar", return_value=inst)
		p.start()
		self.addCleanup(p.stop)

	def test_hela_flodet(self):
		self.assertTrue(sendify.kontrollera_nyckel())
		sandning = {
			"avsandare": {**PART, "namn": "ERPNext Test AB"},
			"mottagare": {**PART, "namn": "Mottagare AB", "adressrad_1": "Drottninggatan 1", "postnummer": "11151", "ort": "Stockholm"},
			"kollin": [{"kollityp": "Paket", "langd_cm": 40, "bredd_cm": 30, "hojd_cm": 20, "vikt_kg": 5, "antal": 1,
				"stapelbar": 1, "flakmeter": 0, "beskrivning": "Testgods"}],
			"referens_id": "erpnext-sandlada",
			"avsandarens_referens": "DN-TEST",
		}
		sendify_id = sendify.skapa_sandning(sandning)
		priser, _varningar = sendify.hamta_priser(sendify_id, upphamtningstid(nasta_arbetsdag(), "10:00:00"))
		self.assertTrue(priser, "inga priser i sandlådan")
		valt = next(p for p in priser if any(t in (p["transportorskod"] or p["transportor"]).lower() for t in ("dhl", "ups", "dsv")))
		bokad = sendify.boka(valt["token"])
		self.assertTrue(bokad["sparningsnummer"])
		self.assertTrue(sendify.hamta_dokument(sendify_id, "label").startswith(b"%PDF"))
		self.assertEqual(sendify.hamta_sparning(sendify_id)[0]["status"], "ORDERED")
		sendify.avboka(sendify_id)
```

- [ ] **Step 2: Kör röktestet**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_frakt_sandlada`
Expected: 1 test OK (eller *skipped* om nyckeln saknas – rapportera det, markera inte steget som klart).
Om `avboka` eller `hamta_dokument` avvisas: läs sidan "Cancel a booked shipment" resp. "Print shipping documents" i
https://api.sendify.com/docs, rätta request-body i `sendify.py` och uppdatera motsvarande test i
`test_frakt_sendify.py`.

- [ ] **Step 3: Kör hela testsviten**

Run: `bench --site test-erp.local run-tests --app erpnext_sverige`
Expected: alla tester OK (sandlådetestet OK eller skipped).

- [ ] **Step 4: Commit**

```bash
pre-commit run --files erpnext_sverige/tests/test_frakt_sandlada.py erpnext_sverige/frakt/sendify.py
git add erpnext_sverige/tests/test_frakt_sandlada.py erpnext_sverige/frakt/sendify.py erpnext_sverige/tests/test_frakt_sendify.py
git commit -m "test(frakt): add Sendify sandbox smoke test"
```
