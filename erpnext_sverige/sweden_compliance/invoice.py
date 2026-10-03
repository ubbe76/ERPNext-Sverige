"""Svensk faktura: OCR-nummer, momssammanställning och uppgifter till utskriftsmallen "Faktura Sverige".

Fakturainnehåll enligt mervärdesskattelagen (17 kap. 24 §): säljarens och köparens momsregistreringsnummer
(köparens vid EU-försäljning), underlag och moms per skattesats, samt hänvisning vid undantag från skatt
eller omvänd skattskyldighet.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import flt

from erpnext_sverige.accounting.account_selection import VAT_RATE_BY_ACCOUNT, get_item_kind
from erpnext_sverige.setup.company import TAX_CATEGORY_EU, TAX_CATEGORY_NON_EU
from erpnext_sverige.setup.custom_fields import GOODS

# Hänvisningar skrivs på svenska och engelska, som Skatteverket rekommenderar för utländska köpare
NOTE_REVERSE_CHARGE = "Omvänd skattskyldighet / Reverse charge"
NOTE_EU_GOODS = (
	"Unionsintern leverans, undantagen från skatt enligt artikel 138 i mervärdesskattedirektivet / "
	"Intra-Community supply of goods, exempt under Article 138 of the VAT Directive"
)
NOTE_EXPORT = "Export, undantagen från skatteplikt / Export, exempt from VAT"


# OCR ------------------------------------------------------------------------------------------------


def make_ocr(reference: str) -> str | None:
	"""OCR-nummer enligt Bankgirot: siffrorna i referensen + längdsiffra + kontrollsiffra (Luhn/10-modul)."""
	digits = re.sub(r"\D", "", reference or "").lstrip("0")
	if not digits:
		return None
	digits = digits[-23:]  # högst 25 siffror totalt
	length_digit = str((len(digits) + 2) % 10)
	base = digits + length_digit
	return base + luhn_check_digit(base)


def luhn_check_digit(number: str) -> str:
	total = 0
	for index, char in enumerate(reversed(number)):
		value = int(char)
		if index % 2 == 0:  # varannan siffra från höger, med början på den sista, dubbleras
			value *= 2
			if value > 9:
				value -= 9
		total += value
	return str((10 - total % 10) % 10)


def set_ocr(doc, method=None):
	"""doc_events-hook för Sales Invoice (validate)."""
	if doc.get("se_ocr") or not doc.name or doc.name.startswith("new-"):
		return
	# Kreditfakturor ska inte betalas och kassafakturor betalas direkt: ingen betalningsreferens
	if doc.get("is_return") or doc.get("is_pos"):
		return
	if frappe.get_cached_value("Company", doc.company, "se_use_ocr"):
		doc.se_ocr = make_ocr(doc.name)


# Momssammanställning -------------------------------------------------------------------------------


def get_vat_summary(doc) -> list[dict]:
	"""Underlag och moms per skattesats: [{rate, base, vat}], sorterat efter sats (högst först)."""
	account_rates = {}
	for number, rate in VAT_RATE_BY_ACCOUNT.items():
		account = frappe.db.get_value("Account", {"company": doc.company, "account_number": number})
		if account:
			account_rates[account] = rate

	summary: dict[int, dict] = {}
	for item in doc.get("items"):
		rate = _item_rate(item, doc, account_rates)
		row = summary.setdefault(rate, {"rate": rate, "base": 0.0, "vat": 0.0})
		row["base"] += flt(item.net_amount)

	for tax in doc.get("taxes"):
		rate = account_rates.get(tax.account_head)
		if rate is not None and rate in summary:
			summary[rate]["vat"] += flt(tax.tax_amount_after_discount_amount or tax.tax_amount)

	return sorted(summary.values(), key=lambda row: -row["rate"])


def _item_rate(item, doc, account_rates) -> int:
	"""Momssats för raden: artikelmoms om den finns, annars mallens sats för kontot."""
	item_rates = json.loads(item.item_tax_rate or "{}")
	for tax in doc.get("taxes"):
		rate = account_rates.get(tax.account_head)
		if rate is None:
			continue
		effective = item_rates.get(tax.account_head, tax.rate)
		if flt(effective):
			return rate
	return 0


# Uppgifter till utskriftsmallen -------------------------------------------------------------------


def get_invoice_context(doc) -> dict:
	"""Jinja-metod: allt fakturamallen behöver utöver fakturans egna fält."""
	from erpnext_sverige.sweden_compliance.print_context import get_print_context  # undviker cirkulär import

	credit_for = doc.get("return_against")
	return {
		**get_print_context(doc),
		"ocr": doc.get("se_ocr"),
		# Fakturanumret sätts vid bokföring; utkast och äldre fakturor visar ERPNext:s namn
		"invoice_no": doc.get("se_fakturanummer") or doc.name,
		"credit_for_invoice_no": (
			frappe.db.get_value("Sales Invoice", credit_for, "se_fakturanummer") or credit_for
		)
		if credit_for
		else None,
	}


def get_exemption_notes(doc) -> list[str]:
	if doc.tax_category == TAX_CATEGORY_EU:
		kinds = {get_item_kind(item.item_code) for item in doc.get("items") if item.item_code}
		notes = []
		if GOODS in kinds:
			notes.append(NOTE_EU_GOODS)
		if kinds - {GOODS}:
			notes.append(NOTE_REVERSE_CHARGE)
		return notes
	if doc.tax_category == TAX_CATEGORY_NON_EU:
		return [NOTE_EXPORT]
	return []


def get_payment_details(company: str) -> dict:
	"""Bolagets standardbankkonto (Bank Account med is_company_account)."""
	accounts = frappe.get_all(
		"Bank Account",
		filters={"company": company, "is_company_account": 1, "disabled": 0},
		fields=["bank", "iban", "bank_account_no", "branch_code", "se_bankgiro", "se_plusgiro"],
		order_by="is_default desc, creation",
		limit=1,
	)
	if not accounts:
		return {}
	account = accounts[0]
	return {
		"bankgiro": account.se_bankgiro,
		"plusgiro": account.se_plusgiro,
		"iban": account.iban,
		"bic": frappe.get_cached_value("Bank", account.bank, "swift_number") if account.bank else None,
		"clearing": account.branch_code,
		"account_no": account.bank_account_no,
		"bank": account.bank,
	}


def _ten_digits(tax_id: str | None) -> str | None:
	value = (tax_id or "").strip().upper()
	digits = re.sub(r"\D", "", value)
	if value.startswith("SE") and len(digits) == 12 and digits.endswith("01"):
		digits = digits[:10]
	if len(digits) == 12:
		digits = digits[2:]
	return digits if len(digits) == 10 else None


def format_org_nr(tax_id: str | None) -> str | None:
	digits = _ten_digits(tax_id)
	return f"{digits[:6]}-{digits[6:]}" if digits else None


def vat_number(tax_id: str | None) -> str | None:
	"""Momsregistreringsnummer: SE + organisationsnummer (10 siffror) + 01."""
	digits = _ten_digits(tax_id)
	return f"SE{digits}01" if digits else None


def satt_momsregnr(doc, method=None):
	"""Bolagets momsregistreringsnummer (Company.validate).

	Fylls i när organisationsnumret anges eller ändras. Ett tomt fält betyder att bolaget inte är momsregistrerat
	och fylls inte i igen så länge organisationsnumret är oförändrat. Ett ifyllt nummer kontrolleras mot
	organisationsnumret.
	"""
	# Fältet saknas tills sajten har migrerats; bolag i andra länder har inget svenskt nummer
	if not doc.meta.has_field("se_momsregnr") or (doc.country and doc.country != "Sweden"):
		return
	foregaende = doc.get_doc_before_save()
	org_nr_andrat = doc.is_new() or not foregaende or foregaende.tax_id != doc.tax_id
	# Följer med när organisationsnumret ändras, om numret var det som räknats fram ur det gamla
	if org_nr_andrat and (
		not doc.get("se_momsregnr")
		or (foregaende and doc.get("se_momsregnr") == vat_number(foregaende.tax_id))
	):
		doc.se_momsregnr = vat_number(doc.tax_id)
	if not doc.get("se_momsregnr"):
		return
	nummer = re.sub(r"[\s-]", "", doc.get("se_momsregnr")).upper()
	if not re.fullmatch(r"SE\d{10}01", nummer):
		frappe.throw(
			_(
				"Momsregistreringsnumret ska vara SE följt av organisationsnumrets 10 siffror och 01, t.ex. {0}"
			).format(vat_number(doc.tax_id) or "SE556000000001")
		)
	org_nr = _ten_digits(doc.tax_id)
	if org_nr and nummer[2:12] != org_nr:
		frappe.throw(
			_("Momsregistreringsnumret {0} stämmer inte med organisationsnumret {1}").format(
				nummer, format_org_nr(doc.tax_id)
			)
		)
	doc.se_momsregnr = nummer
