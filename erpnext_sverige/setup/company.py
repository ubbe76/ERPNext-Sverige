"""Grunduppsättning av bokföring och moms för ett svenskt bolag med BAS-kontoplan.

Idempotent: kan köras flera gånger. Konton slås upp via kontonummer, så funktionen fungerar för alla
bolag vars kontoplan bygger på BAS.

    bench --site <site> execute erpnext_sverige.setup.company.setup_swedish_company --kwargs "{'company': '<bolag>'}"
"""

import os

import frappe
from frappe import _

TAX_CATEGORY_SE = "Svensk moms"
TAX_CATEGORY_EU = "EU"
TAX_CATEGORY_NON_EU = "Utanför EU"

# Company-fält -> BAS-kontonummer
COMPANY_ACCOUNTS = {
	# ERPNext väljer annars sista kontot av rätt typ, t.ex. 1519 Nedskrivning av kundfordringar
	"default_receivable_account": "1510",
	"default_payable_account": "2440",
	"default_bank_account": "1930",
	"default_cash_account": "1910",
	"round_off_account": "3740",
	"default_expense_account": "4000",
	"exchange_gain_loss_account": "3960",
	"unrealized_exchange_gain_loss_account": "3960",
	"write_off_account": "3740",
	"default_discount_account": "3731",
	"default_deferred_revenue_account": "2970",
	"default_deferred_expense_account": "1790",
}

# Konton som saknas i ERPNext:s BAS-mall: nummer -> (namn, syskonkonto att placera det bredvid)
MISSING_ACCOUNTS = {
	"3308": ("Försäljning tjänster till annat EU-land", "3305"),
}

# (titel, momskategori, standard, [(kontonummer, sats)])
SALES_TEMPLATES = [
	("Svensk moms", TAX_CATEGORY_SE, 1, [("2611", 25), ("2621", 0), ("2631", 0)]),
	("EU-försäljning", TAX_CATEGORY_EU, 0, []),
	("Export", TAX_CATEGORY_NON_EU, 0, []),
]

# (titel, momskategori, standard, [(kontonummer, sats, Add/Deduct)])
PURCHASE_TEMPLATES = [
	("Svensk ingående moms", TAX_CATEGORY_SE, 1, [("2641", 25, "Add")]),
	("EU-inköp", TAX_CATEGORY_EU, 0, [("2645", 25, "Add"), ("2614", 25, "Deduct")]),
	("Import varor", TAX_CATEGORY_NON_EU, 0, [("2645", 25, "Add"), ("2615", 25, "Deduct")]),
	# Bara en aktiv mall per momskategori är tillåten, så tjänsteköp utanför EU väljs manuellt
	("Tjänsteinköp utanför EU", None, 0, [("2645", 25, "Add"), ("2614", 25, "Deduct")]),
]

# Artiklar med 25 % behöver ingen mall
ITEM_TAX_TEMPLATES = [
	("Moms 12 %", {"2611": 0, "2621": 12, "2631": 0, "2641": 12}),
	("Moms 6 %", {"2611": 0, "2621": 0, "2631": 6, "2641": 6}),
	("Momsfri", {"2611": 0, "2621": 0, "2631": 0, "2641": 0}),
]

# Brevhuvud för de svenska utskriftsmallarna. ERPNext:s egna skriver ut doctypens engelska namn
# ("Sales Invoice") och upprepar nummer och adress som mallarna redan visar.
LETTER_HEAD = "Brevhuvud Sverige"
ERPNEXT_LETTER_HEADS = ("Company Letterhead", "Company Letterhead - Grey")

# Mallar från ERPNext:s svenska standarduppsättning, som bokför på summakonton (2610/2620/2630/2640)
LEGACY_TEMPLATES = {
	"Sales Taxes and Charges Template": [
		"Försäljning Moms 25%",
		"Försäljning Moms 12%",
		"Försäljning Moms 6%",
		"Försäljning Moms 0%",
	],
	"Purchase Taxes and Charges Template": [
		"Inköp Moms 25%",
		"Inköp Moms 12%",
		"Inköp Moms 6%",
		"Inköp Moms 0%",
	],
	"Item Tax Template": ["Artikel Moms 25%", "Artikel Moms 12%", "Artikel Moms 6%", "Artikel Moms 0%"],
}


def setup_swedish_company(company: str):
	frappe.only_for("System Manager")
	abbr = frappe.get_cached_value("Company", company, "abbr")
	if not abbr:
		frappe.throw(_("Company {0} not found").format(company))

	set_swedish_regional_settings()
	create_missing_accounts(company)
	set_company_accounts(company)
	enable_immutable_ledger()
	create_tax_categories()
	remove_legacy_templates(company, abbr)
	create_sales_templates(company, abbr)
	create_purchase_templates(company, abbr)
	create_item_tax_templates(company, abbr)
	create_tax_rules(company, abbr)
	set_default_party_tax_category()
	create_letter_head()
	frappe.db.commit()
	print(f"Svensk grunduppsättning klar för {company}")


def create_letter_head():
	"""Skapa "Brevhuvud Sverige" och gör det till standard i stället för ERPNext:s.

	Ett befintligt brevhuvud skrivs inte över, och ett eget standardbrevhuvud behålls.
	"""
	if not frappe.db.exists("Letter Head", LETTER_HEAD):
		path = os.path.join(
			frappe.get_app_path("erpnext_sverige"),
			"sweden_compliance",
			"letter_head",
			"brevhuvud_sverige.html",
		)
		frappe.get_doc(
			{
				"doctype": "Letter Head",
				"letter_head_name": LETTER_HEAD,
				"source": "HTML",
				"content": frappe.read_file(path),
			}
		).insert(ignore_permissions=True)
	current = frappe.db.get_value("Letter Head", {"is_default": 1, "disabled": 0})
	if not current or current in ERPNEXT_LETTER_HEADS:
		letter_head = frappe.get_doc("Letter Head", LETTER_HEAD)
		letter_head.is_default = 1
		letter_head.save(ignore_permissions=True)


SWEDISH_NUMBER_FORMAT = "# ###,##"


def set_swedish_regional_settings():
	"""Svenskt talformat (1 234,56), kronor efter beloppet (1 234,56 kr) och måndag som första veckodag."""
	settings = {"number_format": SWEDISH_NUMBER_FORMAT, "first_day_of_the_week": "Monday"}
	for key, value in settings.items():
		frappe.db.set_single_value("System Settings", key, value)
		# Formateringen läser standardvärdet (som System Settings annars sätter när formuläret sparas)
		frappe.db.set_default(key, value)
	if frappe.db.exists("Currency", "SEK"):
		frappe.db.set_value(
			"Currency", "SEK", {"number_format": SWEDISH_NUMBER_FORMAT, "symbol": "kr", "symbol_on_right": 1}
		)
	frappe.clear_cache()


def account(company: str, number: str) -> str:
	name = frappe.db.get_value("Account", {"company": company, "account_number": number, "is_group": 0})
	if not name:
		frappe.throw(_("Account {0} is missing in the chart of accounts for {1}").format(number, company))
	return name


def create_missing_accounts(company: str):
	for number, (account_name, sibling) in MISSING_ACCOUNTS.items():
		if frappe.db.exists("Account", {"company": company, "account_number": number}):
			continue
		sibling_doc = frappe.get_doc("Account", account(company, sibling))
		frappe.get_doc(
			{
				"doctype": "Account",
				"company": company,
				"account_name": account_name,
				"account_number": number,
				"parent_account": sibling_doc.parent_account,
				"root_type": sibling_doc.root_type,
				"report_type": sibling_doc.report_type,
				"account_type": sibling_doc.account_type,
				"account_currency": sibling_doc.account_currency,
			}
		).insert()


def set_company_accounts(company: str):
	doc = frappe.get_doc("Company", company)
	for fieldname, number in COMPANY_ACCOUNTS.items():
		doc.set(fieldname, account(company, number))
	doc.save()


def enable_immutable_ledger():
	# Bokföringslagen: en verifikation får inte ändras, bara rättas. Makuleringar bokförs därför
	# som motverifikationer på makuleringsdagen.
	frappe.db.set_single_value("Accounts Settings", "enable_immutable_ledger", 1)


def create_tax_categories():
	for title in (TAX_CATEGORY_SE, TAX_CATEGORY_EU, TAX_CATEGORY_NON_EU):
		if not frappe.db.exists("Tax Category", title):
			frappe.get_doc({"doctype": "Tax Category", "title": title}).insert()


def remove_legacy_templates(company: str, abbr: str):
	for doctype, titles in LEGACY_TEMPLATES.items():
		for title in titles:
			name = f"{title} - {abbr}"
			if not frappe.db.exists(doctype, name):
				continue
			try:
				frappe.delete_doc(doctype, name)
			except frappe.LinkExistsError:
				frappe.db.set_value(doctype, name, "disabled", 1)
				if doctype != "Item Tax Template":
					frappe.db.set_value(doctype, name, "is_default", 0)


def create_sales_templates(company: str, abbr: str):
	for title, category, is_default, rows in SALES_TEMPLATES:
		doc = _get_or_new("Sales Taxes and Charges Template", title, company, abbr)
		doc.update({"tax_category": category, "is_default": is_default, "disabled": 0})
		doc.set(
			"taxes",
			[
				{
					"charge_type": "On Net Total",
					"account_head": account(company, number),
					"description": _tax_description(company, number),
					"rate": rate,
				}
				for number, rate in rows
			],
		)
		doc.save()


def create_purchase_templates(company: str, abbr: str):
	for title, category, is_default, rows in PURCHASE_TEMPLATES:
		doc = _get_or_new("Purchase Taxes and Charges Template", title, company, abbr)
		doc.update({"tax_category": category, "is_default": is_default, "disabled": 0})
		doc.set(
			"taxes",
			[
				{
					"category": "Total",
					"add_deduct_tax": add_deduct,
					"charge_type": "On Net Total",
					"account_head": account(company, number),
					"description": _tax_description(company, number),
					"rate": rate,
				}
				for number, rate, add_deduct in rows
			],
		)
		doc.save()


def create_item_tax_templates(company: str, abbr: str):
	for title, rates in ITEM_TAX_TEMPLATES:
		doc = _get_or_new("Item Tax Template", title, company, abbr)
		doc.set(
			"taxes",
			[{"tax_type": account(company, number), "tax_rate": rate} for number, rate in rates.items()],
		)
		doc.save()


def create_tax_rules(company: str, abbr: str):
	rules = [("Sales", category, f"{title} - {abbr}") for title, category, _d, _r in SALES_TEMPLATES]
	rules += [
		("Purchase", category, f"{title} - {abbr}")
		for title, category, _d, _r in PURCHASE_TEMPLATES
		if category
	]
	for tax_type, category, template in rules:
		template_field = "sales_tax_template" if tax_type == "Sales" else "purchase_tax_template"
		filters = {"company": company, "tax_type": tax_type, "tax_category": category}
		name = frappe.db.get_value("Tax Rule", filters)
		doc = frappe.get_doc("Tax Rule", name) if name else frappe.new_doc("Tax Rule")
		doc.update({**filters, template_field: template})
		doc.save()


def set_default_party_tax_category():
	"""Svenska kunder och leverantörer utan momskategori får "Svensk moms", så att Tax Rules matchar."""
	for name in frappe.get_all("Customer", filters={"tax_category": ["is", "not set"]}, pluck="name"):
		frappe.db.set_value("Customer", name, "tax_category", TAX_CATEGORY_SE)
	for supplier in frappe.get_all(
		"Supplier", filters={"tax_category": ["is", "not set"]}, fields=["name", "country"]
	):
		if supplier.country in (None, "", "Sweden"):
			frappe.db.set_value("Supplier", supplier.name, "tax_category", TAX_CATEGORY_SE)


def _get_or_new(doctype: str, title: str, company: str, abbr: str):
	name = f"{title} - {abbr}"
	if frappe.db.exists(doctype, name):
		return frappe.get_doc(doctype, name)
	return frappe.get_doc({"doctype": doctype, "title": title, "company": company})


def _tax_description(company: str, number: str) -> str:
	name = frappe.db.get_value("Account", {"company": company, "account_number": number}, "account_name")
	return name or number
