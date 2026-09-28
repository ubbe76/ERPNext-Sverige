"""Gemensamma testdata: ett eget testbolag med ERPNext:s BAS-kontoplan."""

import frappe

from erpnext_sverige.setup.company import TAX_CATEGORY_SE, setup_swedish_company

COMPANY = "_Test Svenska AB"
COMPANY_ABBR = "_TSA"
BAS_CHART = "BAS 2024 med Nummer"


def ensure_test_company():
	"""Skapa testbolaget första gången; kör alltid den (idempotenta) grunduppsättningen."""
	if not frappe.db.exists("Company", COMPANY):
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": COMPANY,
				"abbr": COMPANY_ABBR,
				"country": "Sweden",
				"default_currency": "SEK",
				"tax_id": "5560000000",
				"create_chart_of_accounts_based_on": "Standard Template",
				"chart_of_accounts": BAS_CHART,
			}
		).insert()
	setup_swedish_company(COMPANY)  # committar


def account(number: str) -> str:
	return frappe.db.get_value("Account", {"company": COMPANY, "account_number": number, "is_group": 0})


def make_item(item_code, kind, template=None):
	if not frappe.db.exists("Item", item_code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_group": "Services",
				"stock_uom": "Nos",
				"is_stock_item": 0,
				"se_goods_or_service": kind,
				"taxes": [{"item_tax_template": template, "tax_category": TAX_CATEGORY_SE}]
				if template
				else [],
			}
		).insert()
	return item_code


def make_party(doctype, name, tax_category):
	if not frappe.db.exists(doctype, name):
		doc = frappe.new_doc(doctype)
		doc.update({f"{doctype.lower()}_name": name, "tax_category": tax_category})
		if doctype == "Supplier":
			doc.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0})
		doc.insert()
	return name


def make_invoice(doctype, party, items, posting_date=None, submit=True):
	"""items: [(item_code, rate)]"""
	party_field = "customer" if doctype == "Sales Invoice" else "supplier"
	doc = frappe.get_doc(
		{
			"doctype": doctype,
			party_field: party,
			"company": COMPANY,
			"posting_date": posting_date or frappe.utils.today(),
			"set_posting_time": 1,
			"items": [{"item_code": item, "qty": 1, "rate": rate} for item, rate in items],
		}
	)
	if doctype == "Purchase Invoice":
		doc.bill_no = frappe.generate_hash(length=8)
	doc.set_missing_values()
	doc.insert()
	if submit:
		doc.submit()
	return doc
