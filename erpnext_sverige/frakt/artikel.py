"""Fraktartikeln: icke-lagerförd vara som frakten faktureras som (moms och konto följer av vanlig artikellogik)."""

import frappe

FRAKTARTIKEL = "Frakt"
FRAKTKONTO = "3520"


def sakerstall_fraktartikel() -> None:
	"""Skapar artikeln "Frakt" med intäktskonto 3520 per bolag och pekar ut den i Fraktinställningar.

	Idempotent: befintliga artiklar och ett redan valt värde i inställningarna lämnas orörda.
	"""
	from erpnext_sverige.setup.custom_fields import GOODS

	if not frappe.db.exists("Item", FRAKTARTIKEL):
		item_group = "Services" if frappe.db.exists("Item Group", "Services") else None
		item_group = item_group or frappe.db.get_value("Item Group", {"is_group": 0})
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": FRAKTARTIKEL,
				"item_name": "Frakt",
				"item_group": item_group,
				"stock_uom": "Nos",
				"is_stock_item": 0,
				"is_sales_item": 1,
				"is_purchase_item": 0,
				"se_goods_or_service": GOODS,
			}
		).insert(ignore_permissions=True)

	item = frappe.get_doc("Item", FRAKTARTIKEL)
	andrad = False
	for company in frappe.get_all("Company", pluck="name"):
		konto = frappe.db.get_value(
			"Account", {"company": company, "account_number": FRAKTKONTO, "is_group": 0}
		)
		if konto and not any(d.company == company for d in item.item_defaults):
			item.append("item_defaults", {"company": company, "income_account": konto})
			andrad = True
	if andrad:
		item.save(ignore_permissions=True)

	if not frappe.db.get_single_value("Fraktinstallningar", "fraktartikel"):
		frappe.db.set_single_value("Fraktinstallningar", "fraktartikel", FRAKTARTIKEL)
		frappe.clear_document_cache("Fraktinstallningar", "Fraktinstallningar")
