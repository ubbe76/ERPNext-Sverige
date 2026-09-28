"""Uppgifter som de svenska utskriftsmallarna behöver utöver dokumentets egna fält."""

import frappe
from frappe.utils import flt

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
	vat_total, other_charges = split_charges(doc)
	return {
		"org_nr": format_org_nr(company.tax_id),
		"vat_no": vat_number(company.tax_id),
		"f_skatt": company.get("se_f_skatt"),
		"payment": get_payment_details(doc.company),
		"vat_summary": get_vat_summary(doc) if doc.doctype in VAT_SUMMARY_DOCTYPES else [],
		"notes": get_exemption_notes(doc) if doc.doctype in NOTE_DOCTYPES else [],
		"vat_total": vat_total,
		"other_charges": other_charges,
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


def split_charges(doc) -> tuple[float, float]:
	"""(moms, övriga avgifter) i dokumentvalutan.

	Skatterader på momskonton (kontotyp Tax) är moms; frakt och andra avgifter bokas på andra konton.
	Rader som bara påverkar värderingen (kategori Valuation) ingår inte i totalen och räknas inte.
	"""
	vat = other = 0.0
	for tax in doc.get("taxes"):
		if tax.get("category") == "Valuation":
			continue
		amount = flt(tax.tax_amount_after_discount_amount or tax.tax_amount)
		if tax.get("add_deduct_tax") == "Deduct":
			amount = -amount
		if frappe.get_cached_value("Account", tax.account_head, "account_type") == "Tax":
			vat += amount
		else:
			other += amount
	return vat, other
