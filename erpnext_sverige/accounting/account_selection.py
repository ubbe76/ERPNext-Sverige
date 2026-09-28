"""Välj BAS-konto på fakturarader utifrån momskategori, momssats och vara/tjänst.

ERPNext väljer intäkts- och kostnadskonto per artikel och bolag, oberoende av momsen. Dessutom sparar
`set_default_income_account_for_item` första avvikande intäktskonto som artikelns standard, så ett
EU-konto kan följa med till svenska fakturor. Den här modulen körs på `validate`, efter ERPNext:s egen
logik, och sätter kontot enligt BAS.

Bara "hanterade" konton skrivs över (se MANAGED_*). Ett manuellt valt annat konto lämnas orört.
"""

import frappe

from erpnext_sverige.setup.company import TAX_CATEGORY_EU, TAX_CATEGORY_NON_EU, TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import GOODS, SERVICE

SALES = "Sales"
PURCHASE = "Purchase"

SALES_SE_BY_RATE = {25: "3001", 12: "3002", 6: "3003", 0: "3004"}
SALES_FOREIGN = {
	(TAX_CATEGORY_EU, GOODS): "3108",
	(TAX_CATEGORY_EU, SERVICE): "3308",
	(TAX_CATEGORY_NON_EU, GOODS): "3105",
	(TAX_CATEGORY_NON_EU, SERVICE): "3305",
}
PURCHASE_EU_GOODS_BY_RATE = {25: "4515", 12: "4516", 6: "4517"}
PURCHASE_FOREIGN = {
	(TAX_CATEGORY_EU, SERVICE): "4535",
	(TAX_CATEGORY_NON_EU, GOODS): "4545",
	(TAX_CATEGORY_NON_EU, SERVICE): "4531",
}

MANAGED_SALES = {"3000", *SALES_SE_BY_RATE.values(), *SALES_FOREIGN.values()}
MANAGED_PURCHASE = {"4000", *PURCHASE_EU_GOODS_BY_RATE.values(), *PURCHASE_FOREIGN.values()}

# Artikelmomsmallarnas utgående momskonton -> momssats
VAT_RATE_BY_ACCOUNT = {"2611": 25, "2621": 12, "2631": 6}
DEFAULT_VAT_RATE = 25


def resolve_account(side: str, tax_category: str | None, vat_rate: int, kind: str) -> str | None:
	"""BAS-kontonummer för en fakturarad, eller None om kontot inte ska ändras."""
	if side == SALES:
		if tax_category == TAX_CATEGORY_SE:
			return SALES_SE_BY_RATE.get(vat_rate)
		return SALES_FOREIGN.get((tax_category, kind))

	if side == PURCHASE:
		# Svenska inköp bokförs på olika kostnadskonton (4xxx-6xxx) och lämnas orörda
		if tax_category == TAX_CATEGORY_EU and kind == GOODS:
			return PURCHASE_EU_GOODS_BY_RATE.get(vat_rate)
		return PURCHASE_FOREIGN.get((tax_category, kind))

	return None


def set_accounts_by_tax_category(doc, method=None):
	"""doc_events-hook för Sales Invoice och Purchase Invoice (validate)."""
	if not doc.tax_category or not doc.company:
		return

	side = SALES if doc.doctype == "Sales Invoice" else PURCHASE
	fieldname = "income_account" if side == SALES else "expense_account"
	managed = MANAGED_SALES if side == SALES else MANAGED_PURCHASE
	company_default = frappe.get_cached_value(
		"Company", doc.company, "default_income_account" if side == SALES else "default_expense_account"
	)
	perpetual_inventory = side == PURCHASE and frappe.get_cached_value(
		"Company", doc.company, "enable_perpetual_inventory"
	)

	for row in doc.get("items"):
		if not row.item_code:
			continue

		current = row.get(fieldname)
		if current and current != company_default and _account_number(current) not in managed:
			continue

		is_stock_item = frappe.get_cached_value("Item", row.item_code, "is_stock_item")
		# ERPNext bokför lagerartiklar mot lager/2448 vid inköp; det ska inte ändras
		if perpetual_inventory and is_stock_item:
			continue

		number = resolve_account(
			side,
			doc.tax_category,
			get_item_vat_rate(row.item_code, doc.company),
			get_item_kind(row.item_code),
		)
		account = number and _account_by_number(doc.company, number)
		if account:
			row.set(fieldname, account)


def get_item_kind(item_code: str) -> str:
	kind, is_stock_item = frappe.get_cached_value("Item", item_code, ["se_goods_or_service", "is_stock_item"])
	if kind in (GOODS, SERVICE):
		return kind
	return GOODS if is_stock_item else SERVICE


def get_item_vat_rate(item_code: str, company: str) -> int:
	"""Momssats enligt artikelns (eller artikelgruppens) artikelmomsmall för bolaget."""
	template = _item_tax_template(item_code, company)
	if not template:
		return DEFAULT_VAT_RATE

	rates = {}
	for row in frappe.get_all(
		"Item Tax Template Detail", filters={"parent": template}, fields=["tax_type", "tax_rate"]
	):
		number = _account_number(row.tax_type)
		if number in VAT_RATE_BY_ACCOUNT:
			rates[number] = row.tax_rate

	for number, rate in VAT_RATE_BY_ACCOUNT.items():
		if rates.get(number):
			return rate
	return 0 if rates else DEFAULT_VAT_RATE


def _item_tax_template(item_code: str, company: str) -> str | None:
	parents = [("Item", item_code)]
	item_group = frappe.get_cached_value("Item", item_code, "item_group")
	while item_group:
		parents.append(("Item Group", item_group))
		item_group = frappe.get_cached_value("Item Group", item_group, "parent_item_group")

	for parenttype, parent in parents:
		for template in frappe.get_all(
			"Item Tax",
			filters={"parenttype": parenttype, "parent": parent},
			pluck="item_tax_template",
			order_by="idx",
		):
			if frappe.get_cached_value("Item Tax Template", template, "company") == company:
				return template
	return None


def _account_number(account: str | None) -> str | None:
	return frappe.get_cached_value("Account", account, "account_number") if account else None


def _account_by_number(company: str, number: str) -> str | None:
	return frappe.db.get_value("Account", {"company": company, "account_number": number, "is_group": 0})
