# Svenska utskriftsmallar – implementationsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Svenska utskriftsmallar för Offert, Orderbekräftelse, Följesedel och Inköpsorder, byggda på samma
Jinja-byggstenar som en ombyggd "Faktura Sverige", och förvalda för sina dokumenttyper.

**Architecture:** En gemensam makrofil (`templates/includes/se_print.html`) med stil, sidhuvud, artikeltabell,
summor, noter, villkor och sidfot. En Jinja-metod `get_print_context(doc)` samlar bolags-, moms- och
partsuppgifter för alla dokumenttyper; `get_invoice_context` bygger vidare på den med OCR. Varje mall är en kort
`.html` + `.json` under `sweden_compliance/print_format/`. `set_default_print_formats()` sätter mallarna som
standard vid install/migrate.

**Tech Stack:** Frappe/ERPNext v16, Jinja, gettext (`locale/sv.po`), Frappe `IntegrationTestCase`.

**Spec:** `docs/superpowers/specs/2026-09-28-svenska-utskriftsmallar-design.md`

## Global Constraints

- Allt körs från bench-roten `~/ERPNext/my-frappe-bench`; git-kommandon i `apps/erpnext_sverige`.
- Koden indenteras med **tabbar** (som resten av appen); radlängd 110; kommentarer och docstrings på svenska.
- Etiketter skrivs på engelska i `_()` och översätts i `erpnext_sverige/locale/sv.po`. Frappe trimmar blanksteg
  före uppslag – msgid får inte ha inledande/avslutande blanksteg.
- `sv.po` är inte strikt sorterad: sätt in nya poster intill sin närmaste alfabetiska granne (samma ställe som
  en befintlig post med samma prefix), aldrig överst.
- Efter ändring i `sv.po`: `bench compile-po-to-mo --app erpnext_sverige --locale sv --force` och
  `bench --site svensk-erp.local clear-cache`.
- Standardmallens HTML-fil måste ligga i `sweden_compliance/print_format/<scrub(namn)>/<scrub(namn)>.html`, där
  `scrub` = gemener och blanksteg → `_` (Frappe `www/printview.py:get_print_format`). Därför får katalogerna å/ä/ö:
  `orderbekräftelse_sverige`, `följesedel_sverige`, `inköpsorder_sverige`.
- Mallnamn (exakt): `Faktura Sverige`, `Offert Sverige`, `Orderbekräftelse Sverige`, `Följesedel Sverige`,
  `Inköpsorder Sverige`.
- Inget belopp i ord på någon mall. Betalningsuppgifter bara på fakturan.
- Nya `.json`-mallar laddas in med `bench --site svensk-erp.local migrate` (synkar standardmallar från appen).
- Tester: `bench --site svensk-erp.local run-tests --app erpnext_sverige --module <modul>`.
- Commits avslutas med:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_018awd8auunYMsxaaSB8yCPG
  ```

## Review Focus

1. Offert till en **Lead** (inte Customer): ingen "Kundnummer"-rad, inget kundmomsnummer, ingen krasch – test i Task 3.
2. **Tomma** kontaktperson/ordernummer/transportör: raden utelämnas, ingen tom etikett – test i Task 4 och 5.
3. **Utländsk valuta** på offert/order: belopp i dokumentvalutan och en rad "Moms i SEK" – test i Task 3.
4. Följesedel skapad från **två försäljningsordrar**: båda ordernumren visas en gång vardera – test i Task 5.
5. **EU-inköp med omvänd skattskyldighet** (momsen nettas till 0): ingen momsrad, totalen = nettot – test i Task 6.

---

### Task 1: `get_print_context` – gemensam kontext för alla mallar

**Files:**
- Create: `erpnext_sverige/sweden_compliance/print_context.py`
- Modify: `erpnext_sverige/sweden_compliance/invoice.py` (funktionen `get_invoice_context`, ca rad 105–117)
- Modify: `erpnext_sverige/hooks.py:83-87` (`jinja.methods`)
- Test: `erpnext_sverige/tests/test_print_formats.py` (ny)

**Interfaces:**
- Produces: `get_print_context(doc) -> dict` med nycklarna `org_nr`, `vat_no`, `f_skatt`, `payment` (dict),
  `vat_summary` (list[dict]), `notes` (list[str]), `customer` (str | None), `customer_vat_no` (str | None),
  `sales_orders` (str, kommaseparerad, tom sträng om inga).
- Produces: `get_invoice_context(doc) -> dict` = `get_print_context(doc)` + `ocr`. Oförändrat returvärde för
  befintliga anropare.
- Produces (testhjälpare i `test_print_formats.py`, används av Task 3–7): `make_doc(doctype, items, submit=False, **fields)`,
  `render(doc) -> str`.

- [ ] **Step 1: Skriv de fallerande testerna**

Skapa `erpnext_sverige/tests/test_print_formats.py`:

```python
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from erpnext_sverige.setup.company import TAX_CATEGORY_EU, TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import GOODS, SERVICE
from erpnext_sverige.sweden_compliance.print_context import get_print_context
from erpnext_sverige.tests.utils import COMPANY, ensure_test_company, make_item, make_party

# Datum som krävs på raderna för att dokumenten ska gå att spara
ROW_DATES = {
	"Sales Order": {"delivery_date": add_days(today(), 14)},
	"Purchase Order": {"schedule_date": add_days(today(), 14)},
}


def make_doc(doctype, items, submit=False, **fields):
	"""items: [(item_code, rate)]; qty är alltid 2."""
	doc = frappe.get_doc(
		{
			"doctype": doctype,
			"company": COMPANY,
			**fields,
			"items": [
				{"item_code": code, "qty": 2, "rate": rate, **ROW_DATES.get(doctype, {})} for code, rate in items
			],
		}
	)
	doc.update(ROW_DATES.get(doctype, {}))
	doc.set_missing_values()
	doc.insert()
	if submit:
		doc.submit()
	return doc


def render(doc) -> str:
	from erpnext_sverige.setup.custom_fields import PRINT_FORMATS

	frappe.local.lang = "sv"
	return frappe.get_print(doc.doctype, doc.name, print_format=PRINT_FORMATS[doc.doctype], doc=doc)


class PrintTestCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		frappe.db.set_value("Company", COMPANY, {"tax_id": "5560000000", "se_f_skatt": 1})
		frappe.db.commit()

	def setUp(self):
		self.service = make_item("TEST-SE-TJANST", kind=SERVICE)
		self.goods = make_item("TEST-SE-VARA", kind=GOODS)
		self.customer_se = make_party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)
		self.customer_eu = make_party("Customer", "Test EU Kunde GmbH", TAX_CATEGORY_EU)
		self.supplier_se = make_party("Supplier", "Test SE Leverantör AB", TAX_CATEGORY_SE)
		self.supplier_eu = make_party("Supplier", "Test EU Lieferant GmbH", TAX_CATEGORY_EU)

	def tearDown(self):
		frappe.db.rollback()
		frappe.local.lang = "en"


class TestPrintContext(PrintTestCase):
	def test_sales_order_context(self):
		so = make_doc("Sales Order", [(self.service, 1000)], customer=self.customer_se)
		ctx = get_print_context(so)
		self.assertEqual(ctx["org_nr"], "556000-0000")
		self.assertEqual(ctx["vat_no"], "SE556000000001")
		self.assertEqual(ctx["customer"], self.customer_se)
		self.assertEqual({row["rate"]: row["vat"] for row in ctx["vat_summary"]}, {25: 500})
		self.assertEqual(ctx["notes"], [])

	def test_eu_quotation_has_notes_and_customer_vat_number(self):
		qtn = make_doc("Quotation", [(self.service, 100)], quotation_to="Customer", party_name=self.customer_eu)
		ctx = get_print_context(qtn)
		self.assertTrue(ctx["notes"])
		self.assertEqual(ctx["customer"], self.customer_eu)
		self.assertEqual(ctx["customer_vat_no"], "DE123456789")

	def test_purchase_order_has_no_vat_summary_or_customer(self):
		po = make_doc("Purchase Order", [(self.service, 100)], supplier=self.supplier_se)
		ctx = get_print_context(po)
		self.assertEqual(ctx["vat_summary"], [])
		self.assertEqual(ctx["notes"], [])
		self.assertIsNone(ctx["customer"])
		self.assertIsNone(ctx["customer_vat_no"])
```

- [ ] **Step 2: Kör testerna – de ska fallera**

Run: `bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_print_formats`
Expected: FAIL/ERROR med `ModuleNotFoundError: No module named 'erpnext_sverige.sweden_compliance.print_context'`

- [ ] **Step 3: Skapa `print_context.py`**

```python
"""Uppgifter som de svenska utskriftsmallarna behöver utöver dokumentets egna fält."""

import frappe

from erpnext_sverige.sweden_compliance.invoice import (
	format_org_nr,
	get_exemption_notes,
	get_payment_details,
	get_vat_summary,
	vat_number,
)

# Momssammanställningen bygger på kontona för utgående moms och gäller bara försäljning med priser
VAT_SUMMARY_DOCTYPES = ("Quotation", "Sales Order", "Sales Invoice")
# Hänvisning vid undantag från skatt eller omvänd skattskyldighet
NOTE_DOCTYPES = ("Quotation", "Sales Order", "Sales Invoice")


def get_print_context(doc) -> dict:
	"""Jinja-metod: bolags-, moms- och partsuppgifter till utskriftsmallarna."""
	company = frappe.get_cached_doc("Company", doc.company)
	customer = get_customer(doc)
	return {
		"org_nr": format_org_nr(company.tax_id),
		"vat_no": vat_number(company.tax_id),
		"f_skatt": company.get("se_f_skatt"),
		"payment": get_payment_details(doc.company),
		"vat_summary": get_vat_summary(doc) if doc.doctype in VAT_SUMMARY_DOCTYPES else [],
		"notes": get_exemption_notes(doc) if doc.doctype in NOTE_DOCTYPES else [],
		"customer": customer,
		"customer_vat_no": (doc.get("tax_id") or frappe.get_cached_value("Customer", customer, "tax_id"))
		if customer
		else None,
		"sales_orders": ", ".join(
			sorted({item.against_sales_order for item in doc.get("items") if item.get("against_sales_order")})
		),
	}


def get_customer(doc) -> str | None:
	"""Kunden på dokumentet; en offert kan i stället gälla en Lead."""
	if doc.doctype == "Quotation":
		return doc.party_name if doc.quotation_to == "Customer" else None
	return doc.get("customer")
```

- [ ] **Step 4: Låt `get_invoice_context` bygga på `get_print_context`**

Ersätt hela funktionen `get_invoice_context` i `invoice.py` med:

```python
def get_invoice_context(doc) -> dict:
	"""Jinja-metod: allt fakturamallen behöver utöver fakturans egna fält."""
	from erpnext_sverige.sweden_compliance.print_context import get_print_context  # undviker cirkulär import

	return {**get_print_context(doc), "ocr": doc.get("se_ocr")}
```

- [ ] **Step 5: Registrera Jinja-metoden i `hooks.py`**

```python
jinja = {
	"methods": [
		"erpnext_sverige.sweden_compliance.invoice.get_invoice_context",
		"erpnext_sverige.sweden_compliance.print_context.get_print_context",
	],
}
```

- [ ] **Step 6: Kör de nya och de befintliga fakturatesterna**

Run:
```bash
bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_print_formats
bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_invoice
bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_credit_notes
```
Expected: alla PASS. (`test_print_formats` importerar `PRINT_FORMATS` först i `render`, som inte anropas än.)

- [ ] **Step 7: Commit**

```bash
cd apps/erpnext_sverige
git add erpnext_sverige/sweden_compliance/print_context.py erpnext_sverige/sweden_compliance/invoice.py \
	erpnext_sverige/hooks.py erpnext_sverige/tests/test_print_formats.py
git commit -m "feat: add print context shared by Swedish print formats"
```

---

### Task 2: Gemensamma makron och ombyggd "Faktura Sverige"

**Files:**
- Create: `erpnext_sverige/templates/includes/se_print.html`
- Modify: `erpnext_sverige/sweden_compliance/print_format/faktura_sverige/faktura_sverige.html` (skrivs om helt)
- Modify: `erpnext_sverige/locale/sv.po` ("Your Order No")
- Test: `erpnext_sverige/tests/test_invoice.py` (utöka `test_print_format_renders_in_swedish`)

**Interfaces:**
- Consumes: `get_invoice_context(doc)` från Task 1.
- Produces (Jinja-makron, importeras med
  `{%- from "erpnext_sverige/templates/includes/se_print.html" import styles, header, items, totals, notes, terms, footer with context -%}`):
  - `styles()`
  - `header(title, meta_rows, party_label, party_name, address, vat_no=None, extra=[])` – `meta_rows` och
    `extra` är listor av `(etikett, värde)`; poster med falskt värde hoppas över.
  - `items(doc, show_prices=True)`
  - `totals(doc, ctx, grand_label)`
  - `notes(ctx)`, `terms(doc)`, `footer(doc, ctx, show_payment=False)`
  - Omslutande `<div class="se-doc">` skrivs av varje mall.

- [ ] **Step 1: Spara fakturans nuvarande text som referens**

Skapa en tillfällig modul `apps/erpnext_sverige/erpnext_sverige/_tmp_invoice_text.py` (committas inte):

```python
import re

import frappe

from erpnext_sverige.setup.company import TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import GOODS, SERVICE
from erpnext_sverige.tests.utils import COMPANY_ABBR, ensure_test_company, make_invoice, make_item, make_party


def run():
	ensure_test_company()
	service = make_item("TEST-SE-TJANST", kind=SERVICE)
	goods_12 = make_item("TEST-SE-VARA-12", kind=GOODS, template=f"Moms 12 % - {COMPANY_ABBR}")
	customer = make_party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)
	si = make_invoice("Sales Invoice", customer, [(service, 1000), (goods_12, 500)], posting_date="2026-09-01")
	si.po_no = "PO-4711"
	frappe.local.lang = "sv"
	html = frappe.get_print("Sales Invoice", si.name, print_format="Faktura Sverige", doc=si)
	frappe.db.rollback()
	text = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
	text = re.sub(r"<[^>]+>", "\n", text)
	text = text.replace(si.name, "<NAMN>").replace(si.se_ocr or "-", "<OCR>")
	print("\n".join(line.strip() for line in text.splitlines() if line.strip()))
```

Run:
```bash
bench --site svensk-erp.local execute erpnext_sverige._tmp_invoice_text.run > /tmp/claude-1000/faktura_fore.txt
```
Expected: filen innehåller bl.a. "Faktura", "Förfallodatum", "Er referens", "PO-4711", "Att betala".

- [ ] **Step 2: Utöka fakturatestet med referensraderna (fallerar)**

I `test_invoice.py`, `test_print_format_renders_in_swedish`, sätt före `get_print`:

```python
		si.po_no = "PO-4711"
		si.contact_display = "Anna Andersson"
```

och lägg till sist i testet:

```python
		self.assertIn("Ert ordernr", html)
		self.assertIn("PO-4711", html)
		self.assertIn("Er referens", html)
		self.assertIn("Anna Andersson", html)
		self.assertNotIn(">Nos<", html)
```

Run: `bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_invoice`
Expected: FAIL på `assertIn("Ert ordernr", html)`.

- [ ] **Step 3: Skapa `templates/includes/se_print.html`**

```jinja
{#- Byggstenar för de svenska utskriftsmallarna (sweden_compliance/print_format). -#}

{%- macro money(doc, value) -%}{{ frappe.utils.fmt_money(value, currency=doc.currency) }}{%- endmacro -%}

{%- macro styles() -%}
<style>
	.se-doc { font-size: 10pt; color: #222; }
	.se-doc h1 { font-size: 20pt; margin: 0 0 4px 0; }
	.se-doc .se-muted { color: #666; }
	.se-doc .se-label { color: #666; font-size: 8pt; text-transform: uppercase; letter-spacing: .03em; }
	.se-doc table td { line-height: 1.35; }
	.se-doc table.se-meta td { padding: 1px 12px 1px 0 !important; vertical-align: top; border: 0 !important; }
	.se-doc table.se-items { width: 100%; border-collapse: collapse; margin-top: 18px; }
	.se-doc table.se-items th { border-bottom: 1px solid #222; font-weight: 600; padding: 4px; }
	.se-doc table.se-items td { border-bottom: 1px solid #ddd; padding: 4px; vertical-align: top; }
	.se-doc .se-right { text-align: right; white-space: nowrap; }
	.se-doc .se-nowrap { white-space: nowrap; }
	.se-doc table.se-totals { margin-left: auto; margin-top: 12px; border-collapse: collapse; }
	.se-doc table.se-totals td { padding: 2px 0 2px 24px !important; border: 0 !important; }
	.se-doc table.se-totals tr.se-grand td { border-top: 1px solid #222 !important; padding-top: 6px !important; font-weight: 700; font-size: 12pt; }
	.se-doc .se-notes { margin-top: 14px; padding: 6px 8px; border: 1px solid #ccc; }
	.se-doc .se-footer { margin-top: 28px; padding-top: 8px; border-top: 1px solid #999; font-size: 8pt; }
	.se-doc .se-footer td { padding: 0 18px 0 0 !important; vertical-align: top; border: 0 !important; }
</style>
{%- endmacro -%}

{%- macro header(title, meta_rows, party_label, party_name, address, vat_no=None, extra=[]) -%}
<table style="width: 100%; margin-top: 8px;">
	<tr>
		<td style="width: 55%; vertical-align: top;">
			<h1>{{ title }}</h1>
			<table class="se-meta">
				{% for label, value in meta_rows %}{% if value %}
				<tr><td class="se-label">{{ label }}</td><td>{{ value }}</td></tr>
				{% endif %}{% endfor %}
			</table>
		</td>
		<td style="width: 45%; vertical-align: top;">
			<div class="se-label">{{ party_label }}</div>
			<div><b>{{ party_name }}</b></div>
			{% if address %}<div>{{ address }}</div>{% endif %}
			{% if vat_no %}
			<div style="margin-top: 4px;"><span class="se-label">{{ _("Customer VAT Reg. No.") }}</span> {{ vat_no }}</div>
			{% endif %}
			{% for label, value in extra %}{% if value %}
			<div class="se-label" style="margin-top: 8px;">{{ label }}</div>
			<div>{{ value }}</div>
			{% endif %}{% endfor %}
		</td>
	</tr>
</table>
{%- endmacro -%}

{%- macro items(doc, show_prices=True) -%}
<table class="se-items">
	<thead>
		<tr>
			<th>{{ _("Description") }}</th>
			<th class="se-right">{{ _("Qty") }}</th>
			<th>{{ _("Unit") }}</th>
			{% if show_prices %}
			<th class="se-right">{{ _("Unit Price") }}</th>
			<th class="se-right">{{ _("Amount") }}</th>
			{% endif %}
		</tr>
	</thead>
	<tbody>
		{% for item in doc.items %}
		<tr>
			<td>
				<b>{{ item.item_name }}</b>
				{% if item.description and item.description != item.item_name %}<div class="se-muted">{{ item.description }}</div>{% endif %}
				{% if doc.doctype == "Sales Invoice" and item.delivery_date and item.delivery_date != doc.posting_date %}<div class="se-muted">{{ _("Delivered") }} {{ item.get_formatted("delivery_date") }}</div>{% endif %}
			</td>
			<td class="se-right">{{ item.get_formatted("qty") }}</td>
			<td>{{ _(item.uom) }}</td>
			{% if show_prices %}
			<td class="se-right">{{ money(doc, item.net_rate) }}</td>
			<td class="se-right">{{ money(doc, item.net_amount) }}</td>
			{% endif %}
		</tr>
		{% endfor %}
	</tbody>
</table>
{%- endmacro -%}

{%- macro totals(doc, ctx, grand_label) -%}
<table class="se-totals">
	<tr><td>{{ _("Total excl. VAT") }}</td><td class="se-right">{{ money(doc, doc.net_total) }}</td></tr>
	{% if ctx.vat_summary %}
		{% for row in ctx.vat_summary %}
			{% if row.rate %}
			<tr>
				<td>{{ _("VAT {0} % on {1}").format(row.rate, money(doc, row.base)) }}</td>
				<td class="se-right">{{ money(doc, row.vat) }}</td>
			</tr>
			{% elif row.base %}
			<tr><td>{{ _("Exempt from VAT") }}</td><td class="se-right">{{ money(doc, row.base) }}</td></tr>
			{% endif %}
		{% endfor %}
	{% elif doc.total_taxes_and_charges %}
	<tr><td>{{ _("VAT") }}</td><td class="se-right">{{ money(doc, doc.total_taxes_and_charges) }}</td></tr>
	{% endif %}
	{% if doc.rounding_adjustment %}
	<tr><td>{{ _("Rounding Adjustment") }}</td><td class="se-right">{{ money(doc, doc.rounding_adjustment) }}</td></tr>
	{% endif %}
	<tr class="se-grand">
		<td>{{ grand_label }}</td>
		<td class="se-right">{{ money(doc, doc.rounded_total or doc.grand_total) }}</td>
	</tr>
	{% if doc.currency != doc.company_currency %}
	<tr><td class="se-muted">{{ _("VAT in {0}").format(doc.company_currency) }}</td>
		<td class="se-right se-muted">{{ frappe.utils.fmt_money(doc.base_total_taxes_and_charges, currency=doc.company_currency) }}</td></tr>
	{% endif %}
</table>
{%- endmacro -%}

{%- macro notes(ctx) -%}
{% if ctx.notes %}
<div class="se-notes">
	{% for note in ctx.notes %}<div>{{ note }}</div>{% endfor %}
</div>
{% endif %}
{%- endmacro -%}

{%- macro terms(doc) -%}
{% if doc.terms %}<div style="margin-top: 12px;">{{ doc.terms }}</div>{% endif %}
{%- endmacro -%}

{%- macro footer(doc, ctx, show_payment=False) -%}
{%- set pay = ctx.payment -%}
<div class="se-footer">
	<table>
		<tr>
			<td>
				<b>{{ doc.company }}</b><br>
				{% if doc.company_address_display %}{{ doc.company_address_display }}{% endif %}
			</td>
			<td>
				{% if ctx.org_nr %}{{ _("Corporate ID No.") }}: {{ ctx.org_nr }}<br>{% endif %}
				{% if ctx.vat_no %}{{ _("VAT Reg. No.") }}: {{ ctx.vat_no }}<br>{% endif %}
				{% if ctx.f_skatt %}{{ _("Approved for F-tax") }}{% endif %}
			</td>
			{% if show_payment and pay %}
			<td>
				{% if pay.bankgiro %}{{ _("Bankgiro") }}: {{ pay.bankgiro }}<br>{% endif %}
				{% if pay.plusgiro %}{{ _("Plusgiro") }}: {{ pay.plusgiro }}<br>{% endif %}
				{% if pay.clearing and pay.account_no %}{{ _("Bank Account") }}: {{ pay.clearing }}-{{ pay.account_no }}<br>{% endif %}
				{% if pay.iban %}<span class="se-nowrap">IBAN: {{ pay.iban }}</span><br>{% endif %}
				{% if pay.bic %}BIC: {{ pay.bic }}{% endif %}
			</td>
			{% endif %}
		</tr>
	</table>
</div>
{%- endmacro -%}
```

- [ ] **Step 4: Skriv om `faktura_sverige.html`**

```jinja
{%- from "erpnext_sverige/templates/includes/se_print.html" import styles, header, items, totals, notes, terms, footer with context -%}
{%- set ctx = get_invoice_context(doc) -%}
{{ styles() }}
<div class="se-doc">
	{% if letter_head and not no_letterhead %}<div class="letter-head">{{ letter_head }}</div>{% endif %}

	{{ header(
		_("Credit Note") if doc.is_return else _("Invoice"),
		[
			(_("Invoice No"), doc.name),
			(_("Invoice Date"), doc.get_formatted("posting_date")),
			(_("Due Date"), "<b>" ~ doc.get_formatted("due_date") ~ "</b>" if not doc.is_return),
			(_("OCR"), "<b>" ~ ctx.ocr ~ "</b>" if ctx.ocr),
			(_("Credit for invoice"), doc.return_against),
			(_("Your Reference"), doc.contact_display),
			(_("Your Order No"), doc.po_no),
			(_("Customer No"), doc.customer),
		],
		_("Bill To"), doc.customer_name, doc.address_display, ctx.customer_vat_no
	) }}

	{{ items(doc) }}
	{{ totals(doc, ctx, _("Total Credit") if doc.is_return else _("Total to Pay")) }}
	{{ notes(ctx) }}
	{{ terms(doc) }}
	{{ footer(doc, ctx, show_payment=True) }}
</div>
```

- [ ] **Step 5: Översätt "Your Order No"**

I `sv.po`, intill övriga `msgid "Your …"`-poster:

```
msgid "Your Order No"
msgstr "Ert ordernr"
```

Kompilera och töm cachen (se Global Constraints).

- [ ] **Step 6: Kör fakturatesterna**

Run:
```bash
bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_invoice
bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_credit_notes
```
Expected: alla PASS.

- [ ] **Step 7: Jämför fakturans text med referensen**

Run:
```bash
bench --site svensk-erp.local execute erpnext_sverige._tmp_invoice_text.run > /tmp/claude-1000/faktura_efter.txt
diff /tmp/claude-1000/faktura_fore.txt /tmp/claude-1000/faktura_efter.txt
```
Expected: enda skillnaden är att raden "Er referens" före "PO-4711" nu heter "Ert ordernr". (Testfakturan har
ingen kontaktperson, så ingen ny "Er referens"-rad.) Allt annat identiskt. Ta sedan bort den tillfälliga modulen:
`rm apps/erpnext_sverige/erpnext_sverige/_tmp_invoice_text.py`.

- [ ] **Step 8: Commit**

```bash
cd apps/erpnext_sverige
git add erpnext_sverige/templates/includes/se_print.html \
	erpnext_sverige/sweden_compliance/print_format/faktura_sverige/faktura_sverige.html \
	erpnext_sverige/locale/sv.po erpnext_sverige/tests/test_invoice.py
git commit -m "refactor: build Faktura Sverige from shared print macros"
```

---

### Task 3: Offert Sverige

**Files:**
- Create: `erpnext_sverige/sweden_compliance/print_format/offert_sverige/__init__.py` (tom)
- Create: `erpnext_sverige/sweden_compliance/print_format/offert_sverige/offert_sverige.json`
- Create: `erpnext_sverige/sweden_compliance/print_format/offert_sverige/offert_sverige.html`
- Modify: `erpnext_sverige/setup/custom_fields.py` (konstanten `PRINT_FORMATS`)
- Modify: `erpnext_sverige/locale/sv.po`
- Test: `erpnext_sverige/tests/test_print_formats.py`

**Interfaces:**
- Consumes: makrona från Task 2, `get_print_context` och testhjälparna `make_doc`/`render` från Task 1.
- Produces: `PRINT_FORMATS: dict[str, str]` i `setup/custom_fields.py` (doctype → mallnamn); Task 4–7 lägger
  till sina rader.

- [ ] **Step 1: Lägg till `PRINT_FORMATS` i `setup/custom_fields.py`**

Direkt under `INVOICE_PRINT_FORMAT = "Faktura Sverige"`:

```python
# Svenska utskriftsmallar (sweden_compliance/print_format) per doctype
PRINT_FORMATS = {
	"Quotation": "Offert Sverige",
	"Sales Invoice": INVOICE_PRINT_FORMAT,
}
```

- [ ] **Step 2: Skriv de fallerande testerna**

Lägg till i `test_print_formats.py`:

```python
class TestQuotationPrint(PrintTestCase):
	def test_renders_in_swedish(self):
		qtn = make_doc("Quotation", [(self.service, 1000)], quotation_to="Customer", party_name=self.customer_se)
		qtn.contact_display = "Anna Andersson"
		html = render(qtn)
		for text in ("Offert", "Offertnr", "Giltig till", "Er referens", "Anna Andersson", "Kundnummer"):
			self.assertIn(text, html)
		for text in ("Moms 25 % på", "Totalt inkl. moms", ">St<", "556000-0000"):
			self.assertIn(text, html)
		for text in ("Customer Name", "Bill to", ">Nos<", "In Words", "Grand Total", "Bankgiro"):
			self.assertNotIn(text, html)

	def test_quotation_to_lead(self):
		lead = frappe.get_doc({"doctype": "Lead", "lead_name": "Test Leadsson"}).insert()
		qtn = make_doc("Quotation", [(self.service, 1000)], quotation_to="Lead", party_name=lead.name)
		html = render(qtn)
		self.assertIn("Offert", html)
		self.assertNotIn("Kundnummer", html)
		self.assertNotIn("Er referens", html)

	def test_foreign_currency_shows_vat_in_sek(self):
		qtn = make_doc(
			"Quotation",
			[(self.service, 1000)],
			quotation_to="Customer",
			party_name=self.customer_se,
			currency="EUR",
			conversion_rate=11.5,
		)
		html = render(qtn)
		self.assertIn(frappe._("VAT in {0}", lang="sv").format("SEK"), html)
```

- [ ] **Step 3: Kör – ska fallera**

Run: `bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_print_formats`
Expected: `TestQuotationPrint` ERROR, "Print Format Offert Sverige not found" eller liknande.

- [ ] **Step 4: Skapa `offert_sverige.json`**

```json
{
 "align_labels_right": 0,
 "creation": "2026-09-28 20:00:00.000000",
 "css": "",
 "custom_format": 1,
 "default_print_language": "sv",
 "disabled": 0,
 "doc_type": "Quotation",
 "docstatus": 0,
 "doctype": "Print Format",
 "font": "Default",
 "idx": 0,
 "line_breaks": 0,
 "modified": "2026-09-28 20:00:00.000000",
 "modified_by": "Administrator",
 "module": "Sweden Compliance",
 "name": "Offert Sverige",
 "owner": "Administrator",
 "print_format_builder": 0,
 "print_format_type": "Jinja",
 "raw_printing": 0,
 "show_section_headings": 0,
 "standard": "Yes"
}
```

- [ ] **Step 5: Skapa `offert_sverige.html`**

```jinja
{%- from "erpnext_sverige/templates/includes/se_print.html" import styles, header, items, totals, notes, terms, footer with context -%}
{%- set ctx = get_print_context(doc) -%}
{{ styles() }}
<div class="se-doc">
	{% if letter_head and not no_letterhead %}<div class="letter-head">{{ letter_head }}</div>{% endif %}

	{{ header(
		_("Quotation", context="Swedish print"),
		[
			(_("Quotation No"), doc.name),
			(_("Date"), doc.get_formatted("transaction_date")),
			(_("Valid Till"), doc.get_formatted("valid_till") if doc.valid_till),
			(_("Your Reference"), doc.contact_display),
			(_("Customer No"), ctx.customer),
		],
		_("Customer"), doc.customer_name, doc.address_display, ctx.customer_vat_no
	) }}

	{{ items(doc) }}
	{{ totals(doc, ctx, _("Total incl. VAT")) }}
	{{ notes(ctx) }}
	{{ terms(doc) }}
	{{ footer(doc, ctx) }}
</div>
```

- [ ] **Step 6: Översättningar i `sv.po`**

Sätt in intill närmaste granne:

```
msgctxt "Swedish print"
msgid "Quotation"
msgstr "Offert"

msgid "Quotation No"
msgstr "Offertnr"

msgid "Total incl. VAT"
msgstr "Totalt inkl. moms"
```

(`msgctxt` behövs eftersom "Quotation" redan översätts till "Försäljningsoffert" i menyerna.) Kompilera och töm
cachen.

- [ ] **Step 7: Ladda in mallen och kör testerna**

Run:
```bash
bench --site svensk-erp.local migrate
bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_print_formats
```
Expected: alla PASS. Om `test_quotation_to_lead` fallerar på att Lead kräver fler fält: lägg till de fält
felmeddelandet anger i `frappe.get_doc({...})`, inget annat.

- [ ] **Step 8: Commit**

```bash
cd apps/erpnext_sverige
git add erpnext_sverige/sweden_compliance/print_format/offert_sverige erpnext_sverige/setup/custom_fields.py \
	erpnext_sverige/locale/sv.po erpnext_sverige/tests/test_print_formats.py
git commit -m "feat: add Swedish quotation print format"
```

---

### Task 4: Orderbekräftelse Sverige

**Files:**
- Create: `erpnext_sverige/sweden_compliance/print_format/orderbekräftelse_sverige/__init__.py` (tom)
- Create: `erpnext_sverige/sweden_compliance/print_format/orderbekräftelse_sverige/orderbekräftelse_sverige.json`
- Create: `erpnext_sverige/sweden_compliance/print_format/orderbekräftelse_sverige/orderbekräftelse_sverige.html`
- Modify: `erpnext_sverige/setup/custom_fields.py` (`PRINT_FORMATS`)
- Modify: `erpnext_sverige/locale/sv.po`
- Test: `erpnext_sverige/tests/test_print_formats.py`

**Interfaces:**
- Consumes: makrona (Task 2), `get_print_context` (Task 1), `PRINT_FORMATS`, `make_doc`, `render`.

- [ ] **Step 1: Lägg till i `PRINT_FORMATS`**

```python
	"Sales Order": "Orderbekräftelse Sverige",
```

- [ ] **Step 2: Skriv de fallerande testerna**

```python
class TestSalesOrderPrint(PrintTestCase):
	def test_renders_in_swedish(self):
		so = make_doc("Sales Order", [(self.service, 1000)], customer=self.customer_se, po_no="PO-4711")
		so.contact_display = "Anna Andersson"
		html = render(so)
		for text in ("Orderbekräftelse", "Orderdatum", "Leveransdatum", "Ert ordernr", "PO-4711"):
			self.assertIn(text, html)
		for text in ("Er referens", "Anna Andersson", "Moms 25 % på", "Totalt inkl. moms", ">St<"):
			self.assertIn(text, html)
		for text in ("Customer Name", "Bill to", ">Nos<", "In Words", "Grand Total", ">Nej<"):
			self.assertNotIn(text, html)

	def test_empty_references_are_left_out(self):
		so = make_doc("Sales Order", [(self.service, 1000)], customer=self.customer_se)
		so.contact_display = None
		html = render(so)
		self.assertNotIn("Ert ordernr", html)
		self.assertNotIn("Er referens", html)
```

- [ ] **Step 3: Kör – ska fallera**

Run: `bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_print_formats`
Expected: `TestSalesOrderPrint` ERROR (mallen finns inte).

- [ ] **Step 4: Skapa `orderbekräftelse_sverige.json`**

Samma innehåll som `offert_sverige.json` i Task 3 Step 4, men med:

```json
 "doc_type": "Sales Order",
 "name": "Orderbekräftelse Sverige",
```

Hela filen:

```json
{
 "align_labels_right": 0,
 "creation": "2026-09-28 20:00:00.000000",
 "css": "",
 "custom_format": 1,
 "default_print_language": "sv",
 "disabled": 0,
 "doc_type": "Sales Order",
 "docstatus": 0,
 "doctype": "Print Format",
 "font": "Default",
 "idx": 0,
 "line_breaks": 0,
 "modified": "2026-09-28 20:00:00.000000",
 "modified_by": "Administrator",
 "module": "Sweden Compliance",
 "name": "Orderbekräftelse Sverige",
 "owner": "Administrator",
 "print_format_builder": 0,
 "print_format_type": "Jinja",
 "raw_printing": 0,
 "show_section_headings": 0,
 "standard": "Yes"
}
```

- [ ] **Step 5: Skapa `orderbekräftelse_sverige.html`**

```jinja
{%- from "erpnext_sverige/templates/includes/se_print.html" import styles, header, items, totals, notes, terms, footer with context -%}
{%- set ctx = get_print_context(doc) -%}
{{ styles() }}
<div class="se-doc">
	{% if letter_head and not no_letterhead %}<div class="letter-head">{{ letter_head }}</div>{% endif %}

	{{ header(
		_("Order Confirmation"),
		[
			(_("Order No"), doc.name),
			(_("Order Date"), doc.get_formatted("transaction_date")),
			(_("Delivery Date"), doc.get_formatted("delivery_date") if doc.delivery_date),
			(_("Your Reference"), doc.contact_display),
			(_("Your Order No"), doc.po_no),
			(_("Customer No"), doc.customer),
		],
		_("Customer"), doc.customer_name, doc.address_display, ctx.customer_vat_no,
		[(_("Delivery Address"), doc.shipping_address_display if doc.shipping_address_display != doc.address_display)]
	) }}

	{{ items(doc) }}
	{{ totals(doc, ctx, _("Total incl. VAT")) }}
	{{ notes(ctx) }}
	{{ terms(doc) }}
	{{ footer(doc, ctx) }}
</div>
```

- [ ] **Step 6: Översättningar i `sv.po`**

```
msgid "Order Confirmation"
msgstr "Orderbekräftelse"

msgid "Delivery Address"
msgstr "Leveransadress"
```

("Order No", "Order Date", "Delivery Date", "Your Reference", "Customer No" finns redan.) Kompilera och töm cachen.

- [ ] **Step 7: Migrera och kör testerna**

Run:
```bash
bench --site svensk-erp.local migrate
bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_print_formats
```
Expected: alla PASS.

- [ ] **Step 8: Commit**

```bash
cd apps/erpnext_sverige
git add "erpnext_sverige/sweden_compliance/print_format/orderbekräftelse_sverige" \
	erpnext_sverige/setup/custom_fields.py erpnext_sverige/locale/sv.po erpnext_sverige/tests/test_print_formats.py
git commit -m "feat: add Swedish sales order confirmation print format"
```

---

### Task 5: Följesedel Sverige

**Files:**
- Create: `erpnext_sverige/sweden_compliance/print_format/följesedel_sverige/__init__.py` (tom)
- Create: `erpnext_sverige/sweden_compliance/print_format/följesedel_sverige/följesedel_sverige.json`
- Create: `erpnext_sverige/sweden_compliance/print_format/följesedel_sverige/följesedel_sverige.html`
- Modify: `erpnext_sverige/setup/custom_fields.py` (`PRINT_FORMATS`)
- Modify: `erpnext_sverige/locale/sv.po`
- Test: `erpnext_sverige/tests/test_print_formats.py`

**Interfaces:**
- Consumes: makrona (Task 2), `get_print_context(doc)["sales_orders"]` (Task 1), `PRINT_FORMATS`, `make_doc`, `render`.

- [ ] **Step 1: Lägg till i `PRINT_FORMATS`**

```python
	"Delivery Note": "Följesedel Sverige",
```

- [ ] **Step 2: Skriv de fallerande testerna**

Lägg till importen överst i testfilen:

```python
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
```

och klassen:

```python
class TestDeliveryNotePrint(PrintTestCase):
	def make_delivery_note(self, *orders):
		dn = make_delivery_note(orders[0].name)
		for order in orders[1:]:
			dn = make_delivery_note(order.name, target_doc=dn)
		dn.insert()
		return dn

	def test_renders_without_prices(self):
		so = make_doc("Sales Order", [(self.service, 1000)], submit=True, customer=self.customer_se, po_no="PO-4711")
		dn = self.make_delivery_note(so)
		dn.transporter_name = "Schenker"
		dn.lr_no = "FS-123"
		html = render(dn)
		for text in ("Följesedel", "Följesedelsnr", "Leveransadress", so.name, "Ert ordernr", "PO-4711"):
			self.assertIn(text, html)
		for text in ("Transportör", "Schenker", "Fraktsedelsnr", "FS-123", ">St<"):
			self.assertIn(text, html)
		for text in ("Enhetspris", "Belopp", "Totalt", "Moms", ">Nos<", "Customer Name", "Bankgiro"):
			self.assertNotIn(text, html)

	def test_lists_each_sales_order_once(self):
		first = make_doc("Sales Order", [(self.service, 100)], submit=True, customer=self.customer_se)
		second = make_doc("Sales Order", [(self.service, 200), (self.goods, 300)], submit=True, customer=self.customer_se)
		dn = self.make_delivery_note(first, second)
		html = render(dn)
		self.assertIn(", ".join(sorted([first.name, second.name])), html)
		self.assertEqual(html.count(second.name), 1)

	def test_empty_carrier_is_left_out(self):
		so = make_doc("Sales Order", [(self.service, 1000)], submit=True, customer=self.customer_se)
		html = render(self.make_delivery_note(so))
		self.assertNotIn("Transportör", html)
		self.assertNotIn("Fraktsedelsnr", html)
```

Obs: "Moms" som `assertNotIn` fångar också sidfotens "Momsregistreringsnummer". Om testet fallerar av just det
skälet: byt `"Moms"` mot `"Moms 25"`.

- [ ] **Step 3: Kör – ska fallera**

Run: `bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_print_formats`
Expected: `TestDeliveryNotePrint` ERROR (mallen finns inte).

- [ ] **Step 4: Skapa `följesedel_sverige.json`**

```json
{
 "align_labels_right": 0,
 "creation": "2026-09-28 20:00:00.000000",
 "css": "",
 "custom_format": 1,
 "default_print_language": "sv",
 "disabled": 0,
 "doc_type": "Delivery Note",
 "docstatus": 0,
 "doctype": "Print Format",
 "font": "Default",
 "idx": 0,
 "line_breaks": 0,
 "modified": "2026-09-28 20:00:00.000000",
 "modified_by": "Administrator",
 "module": "Sweden Compliance",
 "name": "Följesedel Sverige",
 "owner": "Administrator",
 "print_format_builder": 0,
 "print_format_type": "Jinja",
 "raw_printing": 0,
 "show_section_headings": 0,
 "standard": "Yes"
}
```

- [ ] **Step 5: Skapa `följesedel_sverige.html`**

```jinja
{%- from "erpnext_sverige/templates/includes/se_print.html" import styles, header, items, terms, footer with context -%}
{%- set ctx = get_print_context(doc) -%}
{{ styles() }}
<div class="se-doc">
	{% if letter_head and not no_letterhead %}<div class="letter-head">{{ letter_head }}</div>{% endif %}

	{{ header(
		_("Delivery Note", context="Swedish print"),
		[
			(_("Delivery Note No", context="Swedish print"), doc.name),
			(_("Date"), doc.get_formatted("posting_date")),
			(_("Order No"), ctx.sales_orders),
			(_("Your Reference"), doc.contact_display),
			(_("Your Order No"), doc.po_no),
			(_("Carrier", context="Swedish print"), doc.transporter_name),
			(_("Waybill No"), doc.lr_no),
			(_("Customer No"), doc.customer),
		],
		_("Delivery Address"), doc.customer_name, doc.shipping_address_display or doc.address_display
	) }}

	{{ items(doc, show_prices=False) }}
	{{ terms(doc) }}
	{{ footer(doc, ctx) }}
</div>
```

- [ ] **Step 6: Översättningar i `sv.po`**

```
msgctxt "Swedish print"
msgid "Delivery Note"
msgstr "Följesedel"

msgctxt "Swedish print"
msgid "Delivery Note No"
msgstr "Följesedelsnr"

msgctxt "Swedish print"
msgid "Carrier"
msgstr "Transportör"

msgid "Waybill No"
msgstr "Fraktsedelsnr"
```

(`msgctxt` eftersom "Delivery Note" → "Försäljningsföljesedel" och "Carrier" → "Leverantör" redan finns.)
Kompilera och töm cachen.

- [ ] **Step 7: Migrera och kör testerna**

Run:
```bash
bench --site svensk-erp.local migrate
bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_print_formats
```
Expected: alla PASS. Om `make_delivery_note` inte tar med tjänsteartiklar (tom följesedel): byt
`self.service` mot `self.goods` i Task 5-testerna.

- [ ] **Step 8: Commit**

```bash
cd apps/erpnext_sverige
git add "erpnext_sverige/sweden_compliance/print_format/följesedel_sverige" \
	erpnext_sverige/setup/custom_fields.py erpnext_sverige/locale/sv.po erpnext_sverige/tests/test_print_formats.py
git commit -m "feat: add Swedish delivery note print format without prices"
```

---

### Task 6: Inköpsorder Sverige

**Files:**
- Create: `erpnext_sverige/sweden_compliance/print_format/inköpsorder_sverige/__init__.py` (tom)
- Create: `erpnext_sverige/sweden_compliance/print_format/inköpsorder_sverige/inköpsorder_sverige.json`
- Create: `erpnext_sverige/sweden_compliance/print_format/inköpsorder_sverige/inköpsorder_sverige.html`
- Modify: `erpnext_sverige/setup/custom_fields.py` (`PRINT_FORMATS`)
- Modify: `erpnext_sverige/locale/sv.po`
- Test: `erpnext_sverige/tests/test_print_formats.py`

**Interfaces:**
- Consumes: makrona (Task 2; `totals` visar en momsrad när `ctx.vat_summary` är tom), `get_print_context`,
  `PRINT_FORMATS`, `make_doc`, `render`.

- [ ] **Step 1: Lägg till i `PRINT_FORMATS`**

```python
	"Purchase Order": "Inköpsorder Sverige",
```

- [ ] **Step 2: Skriv de fallerande testerna**

```python
class TestPurchaseOrderPrint(PrintTestCase):
	def test_renders_in_swedish(self):
		po = make_doc("Purchase Order", [(self.service, 1000)], supplier=self.supplier_se)
		html = render(po)
		for text in ("Inköpsorder", "Inköpsordernr", "Önskat leveransdatum", "Leverantörsnr", "Leverantör"):
			self.assertIn(text, html)
		for text in ("Test SE Leverantör AB", ">Moms<", "Totalt inkl. moms", ">St<"):
			self.assertIn(text, html)
		for text in ("Kundnummer", "Moms 25 % på", ">Nos<", "In Words", "Bankgiro"):
			self.assertNotIn(text, html)

	def test_eu_reverse_charge_has_no_vat_row(self):
		po = make_doc("Purchase Order", [(self.service, 1000)], supplier=self.supplier_eu)
		self.assertFalse(po.total_taxes_and_charges)
		html = render(po)
		self.assertNotIn(">Moms<", html)
		self.assertEqual(po.grand_total, po.net_total)
```

- [ ] **Step 3: Kör – ska fallera**

Run: `bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_print_formats`
Expected: `TestPurchaseOrderPrint` ERROR (mallen finns inte).

- [ ] **Step 4: Skapa `inköpsorder_sverige.json`**

```json
{
 "align_labels_right": 0,
 "creation": "2026-09-28 20:00:00.000000",
 "css": "",
 "custom_format": 1,
 "default_print_language": "sv",
 "disabled": 0,
 "doc_type": "Purchase Order",
 "docstatus": 0,
 "doctype": "Print Format",
 "font": "Default",
 "idx": 0,
 "line_breaks": 0,
 "modified": "2026-09-28 20:00:00.000000",
 "modified_by": "Administrator",
 "module": "Sweden Compliance",
 "name": "Inköpsorder Sverige",
 "owner": "Administrator",
 "print_format_builder": 0,
 "print_format_type": "Jinja",
 "raw_printing": 0,
 "show_section_headings": 0,
 "standard": "Yes"
}
```

- [ ] **Step 5: Skapa `inköpsorder_sverige.html`**

```jinja
{%- from "erpnext_sverige/templates/includes/se_print.html" import styles, header, items, totals, terms, footer with context -%}
{%- set ctx = get_print_context(doc) -%}
{{ styles() }}
<div class="se-doc">
	{% if letter_head and not no_letterhead %}<div class="letter-head">{{ letter_head }}</div>{% endif %}

	{{ header(
		_("Purchase Order"),
		[
			(_("Purchase Order No"), doc.name),
			(_("Date"), doc.get_formatted("transaction_date")),
			(_("Requested Delivery Date"), doc.get_formatted("schedule_date") if doc.schedule_date),
			(_("Supplier No"), doc.supplier),
		],
		_("Supplier"), doc.supplier_name, doc.address_display, None,
		[(_("Delivery Address"), doc.shipping_address_display)]
	) }}

	{{ items(doc) }}
	{{ totals(doc, ctx, _("Total incl. VAT")) }}
	{{ terms(doc) }}
	{{ footer(doc, ctx) }}
</div>
```

- [ ] **Step 6: Översättningar i `sv.po`**

```
msgid "Purchase Order No"
msgstr "Inköpsordernr"

msgid "Requested Delivery Date"
msgstr "Önskat leveransdatum"

msgid "Supplier No"
msgstr "Leverantörsnr"

msgid "VAT"
msgstr "Moms"
```

Kontrollera först med `grep -n '^msgid "VAT"$' erpnext_sverige/locale/sv.po` att "VAT" inte redan finns; finns den
med annan översättning, använd `_("VAT", context="Swedish print")` i `totals` och en `msgctxt`-post i stället.
Kompilera och töm cachen.

- [ ] **Step 7: Migrera och kör testerna**

Run:
```bash
bench --site svensk-erp.local migrate
bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_print_formats
```
Expected: alla PASS.

- [ ] **Step 8: Commit**

```bash
cd apps/erpnext_sverige
git add "erpnext_sverige/sweden_compliance/print_format/inköpsorder_sverige" \
	erpnext_sverige/setup/custom_fields.py erpnext_sverige/locale/sv.po erpnext_sverige/tests/test_print_formats.py
git commit -m "feat: add Swedish purchase order print format"
```

---

### Task 7: Förvalda mallar och slutkontroll

**Files:**
- Modify: `erpnext_sverige/setup/custom_fields.py` (`create_custom_fields`, `set_default_invoice_print_format`)
- Test: `erpnext_sverige/tests/test_print_formats.py`

**Interfaces:**
- Consumes: `PRINT_FORMATS` (fullständig efter Task 3–6).
- Produces: `set_default_print_formats() -> None` (ersätter `set_default_invoice_print_format`).

- [ ] **Step 1: Skriv de fallerande testerna**

```python
from erpnext_sverige.setup.custom_fields import PRINT_FORMATS, set_default_print_formats
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


class TestDefaultPrintFormats(PrintTestCase):
	def test_swedish_formats_are_default(self):
		set_default_print_formats()
		for doctype, print_format in PRINT_FORMATS.items():
			frappe.clear_cache(doctype=doctype)
			self.assertEqual(frappe.get_meta(doctype).default_print_format, print_format, doctype)

	def test_own_print_format_is_kept(self):
		own = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": "Test egen offert",
				"doc_type": "Quotation",
				"standard": "No",
				"custom_format": 1,
				"print_format_type": "Jinja",
				"html": "<p>egen</p>",
			}
		).insert()
		make_property_setter("Quotation", None, "default_print_format", own.name, "Data", for_doctype=True)
		set_default_print_formats()
		frappe.clear_cache(doctype="Quotation")
		self.assertEqual(frappe.get_meta("Quotation").default_print_format, own.name)
```

Lägg importerna överst i filen tillsammans med de andra.

- [ ] **Step 2: Kör – ska fallera**

Run: `bench --site svensk-erp.local run-tests --app erpnext_sverige --module erpnext_sverige.tests.test_print_formats`
Expected: ImportError `cannot import name 'set_default_print_formats'`.

- [ ] **Step 3: Ersätt `set_default_invoice_print_format` med `set_default_print_formats`**

I `setup/custom_fields.py`: ändra anropet i `create_custom_fields` till `set_default_print_formats()` och ersätt
funktionen med:

```python
def set_default_print_formats():
	"""Gör de svenska mallarna (PRINT_FORMATS) till standardmallar.

	ERPNext:s egna standardmallar ersätts, men en egen (icke-standard) mall som valts lämnas orörd.
	"""
	for doctype, print_format in PRINT_FORMATS.items():
		if not frappe.db.exists("Print Format", print_format):
			continue
		current = frappe.get_meta(doctype).default_print_format
		if current == print_format:
			continue
		if current and frappe.db.get_value("Print Format", current, "standard") == "No":
			continue
		make_property_setter(doctype, None, "default_print_format", print_format, "Data", for_doctype=True)
```

Kontrollera att inget annat anropar den gamla funktionen:
`grep -rn set_default_invoice_print_format apps/erpnext_sverige` – ska inte ge några träffar.

- [ ] **Step 4: Kör hela appens tester**

Run: `bench --site svensk-erp.local run-tests --app erpnext_sverige`
Expected: alla PASS.

- [ ] **Step 5: Migrera och kontrollera sajten**

Run:
```bash
bench --site svensk-erp.local migrate
bench --site svensk-erp.local mariadb -e "select doc_type, value from \`tabProperty Setter\` where property='default_print_format' and doc_type in ('Quotation','Sales Order','Delivery Note','Sales Invoice','Purchase Order');"
```
Expected: Quotation → Offert Sverige, Sales Order → Orderbekräftelse Sverige, Delivery Note → Följesedel Sverige,
Sales Invoice → Faktura Sverige, Purchase Order → Inköpsorder Sverige.

- [ ] **Step 6: Rendera ordern från skärmbilden**

Skapa tillfälligt `apps/erpnext_sverige/erpnext_sverige/_tmp_render.py` (committas inte):

```python
import re

import frappe


def run():
	frappe.local.lang = "sv"
	doc = frappe.get_doc("Sales Order", "SAL-ORD-2026-00001")
	html = frappe.get_print("Sales Order", doc.name, print_format="Orderbekräftelse Sverige", doc=doc)
	text = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
	print(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)))
```

Run: `bench --site svensk-erp.local execute erpnext_sverige._tmp_render.run`, sedan
`rm apps/erpnext_sverige/erpnext_sverige/_tmp_render.py`.
Expected: texten innehåller "Orderbekräftelse", "Kund", "Orderdatum", "Leveransdatum", "St", "Totalt inkl. moms"
och inga av "Customer Name", "Bill to", "Nej", "Nos", "In Words".

- [ ] **Step 7: Lint**

Run: `cd apps/erpnext_sverige && pre-commit run --files $(git diff --name-only 0ccb48e)` (0ccb48e = sista
spec-commiten före Task 1; diffen mot den tar med både committade och ocommittade ändringar)
Expected: Passed (rätta det ruff/prettier anmärker på).

- [ ] **Step 8: Commit**

```bash
cd apps/erpnext_sverige
git add erpnext_sverige/setup/custom_fields.py erpnext_sverige/tests/test_print_formats.py
git commit -m "feat: make Swedish print formats the default for sales and purchase documents"
```
