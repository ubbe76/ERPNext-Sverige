"""Momskategori utifrån land och kundtyp, och kontroll av momsregistreringsnummer (format och VIES).

- Adress: kategorin sätts utifrån adressens land när den sparas. ERPNext använder adressens kategori
  före kundens/leverantörens på fakturan.
- Kund/leverantör: får kategorin från sin primära adress (eller leverantörens land) om den saknar kategori.
- Privatpersoner i andra EU-länder får svensk moms (distansförsäljning under tröskeln). Omvänd
  skattskyldighet gäller bara företag.
- En manuellt vald kategori skrivs inte över, utom när land eller kundtyp ändras.
"""

import re

import frappe
import requests
from frappe import _

from erpnext_sverige.setup.company import TAX_CATEGORY_EU, TAX_CATEGORY_NON_EU, TAX_CATEGORY_SE

SWEDEN = "se"
EU_COUNTRY_CODES = set(
	"at be bg cy cz de dk ee es fi fr gr hr hu ie it lt lu lv mt nl pl pt ro si sk".split()
)
# Momsregistreringsnummer: prefix (Grekland använder EL) och format efter prefixet
VAT_FORMATS = {
	"AT": r"U\d{8}",
	"BE": r"[01]\d{9}",
	"BG": r"\d{9,10}",
	"CY": r"\d{8}[A-Z]",
	"CZ": r"\d{8,10}",
	"DE": r"\d{9}",
	"DK": r"\d{8}",
	"EE": r"\d{9}",
	"EL": r"\d{9}",
	"ES": r"[A-Z0-9]\d{7}[A-Z0-9]",
	"FI": r"\d{8}",
	"FR": r"[A-HJ-NP-Z0-9]{2}\d{9}",
	"HR": r"\d{11}",
	"HU": r"\d{8}",
	"IE": r"\d[A-Z0-9+*]\d{5}[A-Z]{1,2}",
	"IT": r"\d{11}",
	"LT": r"(\d{9}|\d{12})",
	"LU": r"\d{8}",
	"LV": r"\d{11}",
	"MT": r"\d{8}",
	"NL": r"\d{9}B\d{2}",
	"PL": r"\d{10}",
	"PT": r"\d{9}",
	"RO": r"\d{2,10}",
	"SE": r"\d{10}01",
	"SI": r"\d{8}",
	"SK": r"\d{10}",
}
VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{country}/vat/{number}"
INDIVIDUAL = "Individual"


def country_code(country: str | None) -> str | None:
	return (frappe.get_cached_value("Country", country, "code") or "").lower() or None if country else None


def category_for(country: str | None, is_individual: bool = False) -> str | None:
	"""Momskategori för ett land, eller None om landet saknas."""
	code = country_code(country)
	if not code:
		return None
	if code == SWEDEN:
		return TAX_CATEGORY_SE
	if code in EU_COUNTRY_CODES:
		return TAX_CATEGORY_SE if is_individual else TAX_CATEGORY_EU
	return TAX_CATEGORY_NON_EU


def vat_prefix(code: str) -> str:
	return "EL" if code == "gr" else code.upper()


# Momsregistreringsnummer ----------------------------------------------------------------------


def normalize_vat_number(value: str | None) -> str:
	return re.sub(r"[\s.\-]", "", (value or "").upper())


def is_valid_vat_format(vat_number: str) -> bool:
	pattern = VAT_FORMATS.get(vat_number[:2])
	return bool(pattern and re.fullmatch(pattern, vat_number[2:]))


def validate_vat_number(vat_number: str, country: str | None = None) -> None:
	"""Kasta fel om numret har fel format, eller fel landskod för landet."""
	if not is_valid_vat_format(vat_number):
		frappe.throw(
			_(
				"Momsregistreringsnumret {0} har fel format. Det ska börja med landskoden, t.ex. DE123456789."
			).format(vat_number),
			title=_("Ogiltigt momsregistreringsnummer"),
		)
	code = country_code(country)
	if code in EU_COUNTRY_CODES | {SWEDEN} and vat_number[:2] != vat_prefix(code):
		frappe.throw(
			_("Momsregistreringsnumret {0} hör inte till {1} (landskod {2}).").format(
				vat_number, country, vat_prefix(code)
			),
			title=_("Ogiltigt momsregistreringsnummer"),
		)


@frappe.whitelist()
def check_vies(vat_number: str) -> dict:
	"""Fråga EU-kommissionens VIES-register om numret är giltigt."""
	vat_number = normalize_vat_number(vat_number)
	if not is_valid_vat_format(vat_number):
		return {"valid": False, "error": _("Fel format på momsregistreringsnumret")}
	try:
		response = requests.get(VIES_URL.format(country=vat_number[:2], number=vat_number[2:]), timeout=15)
		response.raise_for_status()
		data = response.json()
	except Exception:
		return {"valid": None, "error": _("VIES kunde inte nås just nu. Försök igen senare.")}

	if data.get("userError") not in (None, "VALID", "INVALID"):
		return {"valid": None, "error": _("VIES svarade: {0}").format(data.get("userError"))}
	return {
		"valid": bool(data.get("isValid")),
		"name": (data.get("name") or "").strip("- "),
		"address": (data.get("address") or "").strip("- "),
		"vat_number": vat_number,
	}


# Hooks ----------------------------------------------------------------------------------------


def set_address_tax_category(doc, method=None):
	"""Address validate: kategori utifrån land (och om adressen hör till en privatperson)."""
	if doc.tax_category and not doc.has_value_changed("country"):
		return
	category = category_for(doc.country, _address_belongs_to_individual(doc))
	if category:
		doc.tax_category = category


def propagate_address_tax_category(doc, method=None):
	"""Address on_update: kunder/leverantörer utan kategori får adressens."""
	if not doc.tax_category:
		return
	for link in doc.get("links"):
		if link.link_doctype in ("Customer", "Supplier") and not frappe.db.get_value(
			link.link_doctype, link.link_name, "tax_category"
		):
			frappe.db.set_value(link.link_doctype, link.link_name, "tax_category", doc.tax_category)


def set_party_tax_category(doc, method=None):
	"""Customer/Supplier validate: kategori från primär adress (eller leverantörens land), och kontroll av momsnr."""
	is_customer = doc.doctype == "Customer"
	is_individual = is_customer and doc.customer_type == INDIVIDUAL
	type_changed = is_customer and doc.has_value_changed("customer_type") and not doc.is_new()

	if not doc.tax_category or type_changed:
		category = category_for(_party_country(doc), is_individual)
		if category:
			doc.tax_category = category

	# Svenska kunder har ofta organisationsnumret i tax_id; formatet kontrolleras bara för EU-företag
	if doc.tax_id and doc.tax_category == TAX_CATEGORY_EU:
		doc.tax_id = normalize_vat_number(doc.tax_id)
		# Jämför landskoden med adressens land; leverantörens landsfält är förifyllt med Sverige
		validate_vat_number(doc.tax_id, _address_country(doc))


def update_addresses_on_customer_type_change(doc, method=None):
	"""Customer on_update: räkna om adressernas kategori när kundtypen ändras."""
	if not doc.has_value_changed("customer_type"):
		return
	for address in _linked_addresses("Customer", doc.name):
		category = category_for(address.country, doc.customer_type == INDIVIDUAL)
		if category and category != address.tax_category:
			frappe.db.set_value("Address", address.name, "tax_category", category)


def validate_invoice_vat_number(doc, method=None):
	"""Sales Invoice before_submit: EU-försäljning med omvänd skattskyldighet kräver kundens momsnr."""
	if doc.tax_category != TAX_CATEGORY_EU:
		return
	vat_number = normalize_vat_number(doc.tax_id or frappe.db.get_value("Customer", doc.customer, "tax_id"))
	if not vat_number:
		frappe.throw(
			_(
				"Kunden {0} saknar momsregistreringsnummer. Det krävs på fakturan vid försäljning till "
				"företag i andra EU-länder (omvänd skattskyldighet)."
			).format(doc.customer_name or doc.customer),
			title=_("Momsregistreringsnummer saknas"),
		)
	validate_vat_number(vat_number)


def _party_country(doc) -> str | None:
	return _address_country(doc) or doc.get("country")


def _address_country(doc) -> str | None:
	address = doc.get("customer_primary_address") or doc.get("supplier_primary_address")
	if address:
		country = frappe.db.get_value("Address", address, "country")
		if country:
			return country
	addresses = _linked_addresses(doc.doctype, doc.name) if not doc.is_new() else []
	return addresses[0].country if addresses else None


def _linked_addresses(doctype: str, name: str) -> list:
	return frappe.db.sql(
		"""
		select addr.name, addr.country, addr.tax_category
		from `tabAddress` addr
		join `tabDynamic Link` dl on dl.parent = addr.name and dl.parenttype = 'Address'
		where dl.link_doctype = %s and dl.link_name = %s
		order by addr.is_primary_address desc, addr.creation
		""",
		(doctype, name),
		as_dict=True,
	)


def _address_belongs_to_individual(doc) -> bool:
	for link in doc.get("links"):
		if link.link_doctype == "Customer":
			return frappe.db.get_value("Customer", link.link_name, "customer_type") == INDIVIDUAL
	return False
