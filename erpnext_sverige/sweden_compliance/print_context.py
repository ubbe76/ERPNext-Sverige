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
