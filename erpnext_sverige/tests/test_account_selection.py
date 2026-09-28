import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from erpnext_sverige.accounting.account_selection import PURCHASE, SALES, resolve_account
from erpnext_sverige.setup.company import TAX_CATEGORY_EU, TAX_CATEGORY_NON_EU, TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import GOODS, SERVICE

COMPANY = "BOLAG"


class TestResolveAccount(UnitTestCase):
	def test_sales_sweden_by_vat_rate(self):
		for rate, number in ((25, "3001"), (12, "3002"), (6, "3003"), (0, "3004")):
			for kind in (GOODS, SERVICE):
				self.assertEqual(resolve_account(SALES, TAX_CATEGORY_SE, rate, kind), number)

	def test_sales_foreign(self):
		self.assertEqual(resolve_account(SALES, TAX_CATEGORY_EU, 25, GOODS), "3108")
		self.assertEqual(resolve_account(SALES, TAX_CATEGORY_EU, 25, SERVICE), "3308")
		self.assertEqual(resolve_account(SALES, TAX_CATEGORY_NON_EU, 25, GOODS), "3105")
		self.assertEqual(resolve_account(SALES, TAX_CATEGORY_NON_EU, 25, SERVICE), "3305")

	def test_purchase_sweden_untouched(self):
		self.assertIsNone(resolve_account(PURCHASE, TAX_CATEGORY_SE, 25, GOODS))
		self.assertIsNone(resolve_account(PURCHASE, TAX_CATEGORY_SE, 25, SERVICE))

	def test_purchase_foreign(self):
		for rate, number in ((25, "4515"), (12, "4516"), (6, "4517")):
			self.assertEqual(resolve_account(PURCHASE, TAX_CATEGORY_EU, rate, GOODS), number)
		self.assertEqual(resolve_account(PURCHASE, TAX_CATEGORY_EU, 25, SERVICE), "4535")
		self.assertEqual(resolve_account(PURCHASE, TAX_CATEGORY_NON_EU, 25, GOODS), "4545")
		self.assertEqual(resolve_account(PURCHASE, TAX_CATEGORY_NON_EU, 25, SERVICE), "4531")

	def test_unknown_category(self):
		self.assertIsNone(resolve_account(SALES, None, 25, GOODS))
		self.assertIsNone(resolve_account(SALES, "Okänd", 25, GOODS))


class TestAccountSelectionOnInvoices(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Company", COMPANY):
			raise cls.skipTest(cls, f"Bolaget {COMPANY} saknas")
		cls.abbr = frappe.get_cached_value("Company", COMPANY, "abbr")

	def setUp(self):
		self.service = _item("TEST-SE-TJANST", kind=SERVICE)
		self.goods_12 = _item("TEST-SE-VARA-12", kind=GOODS, template=f"Moms 12 % - {self.abbr}")
		self.customer_se = _party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)
		self.customer_eu = _party("Customer", "Test EU Kunde GmbH", TAX_CATEGORY_EU)
		self.supplier_eu = _party("Supplier", "Test EU Lieferant GmbH", TAX_CATEGORY_EU)

	def tearDown(self):
		frappe.db.rollback()

	def account(self, number):
		return frappe.db.get_value("Account", {"company": COMPANY, "account_number": number})

	def test_sales_sweden_uses_account_per_vat_rate(self):
		si = _sales_invoice(self.customer_se, [self.service, self.goods_12])
		self.assertEqual([r.income_account for r in si.items], [self.account("3001"), self.account("3002")])

	def test_sales_eu_service(self):
		si = _sales_invoice(self.customer_eu, [self.service])
		self.assertEqual(si.items[0].income_account, self.account("3308"))

	def test_item_default_from_eu_sale_does_not_leak_to_swedish_sale(self):
		# ERPNext sparar första avvikande intäktskonto som artikelns standard
		item = frappe.get_doc("Item", self.service)
		item.set("item_defaults", [{"company": COMPANY, "income_account": self.account("3308")}])
		item.save()

		si = _sales_invoice(self.customer_se, [self.service])
		self.assertEqual(si.items[0].income_account, self.account("3001"))

	def test_manual_account_is_kept(self):
		si = _sales_invoice(self.customer_se, [self.service], income_account=self.account("3590"))
		self.assertEqual(si.items[0].income_account, self.account("3590"))

	def test_purchase_eu_service(self):
		pi = frappe.get_doc(
			{
				"doctype": "Purchase Invoice",
				"supplier": self.supplier_eu,
				"company": COMPANY,
				"bill_no": frappe.generate_hash(length=8),
				"items": [{"item_code": self.service, "qty": 1, "rate": 100}],
			}
		)
		pi.set_missing_values()
		pi.insert()
		self.assertEqual(pi.items[0].expense_account, self.account("4535"))


def _item(item_code, kind, template=None):
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


def _party(doctype, name, tax_category):
	if not frappe.db.exists(doctype, name):
		doc = frappe.new_doc(doctype)
		doc.update({f"{doctype.lower()}_name": name, "tax_category": tax_category})
		if doctype == "Supplier":
			doc.supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0})
		doc.insert()
	return name


def _sales_invoice(customer, items, income_account=None):
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": customer,
			"company": COMPANY,
			"items": [
				{"item_code": item, "qty": 1, "rate": 100, "income_account": income_account} for item in items
			],
		}
	)
	si.set_missing_values()
	si.insert()
	return si
