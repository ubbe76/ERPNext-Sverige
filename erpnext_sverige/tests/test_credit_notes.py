"""Kreditfakturor (kundreturer) och debetnotor (leverantörsreturer): kontoval, moms, OCR, momsdeklaration och utskrift."""

import frappe
from erpnext.accounts.doctype.purchase_invoice.purchase_invoice import make_debit_note
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from frappe.tests import IntegrationTestCase

from erpnext_sverige.setup.company import TAX_CATEGORY_EU, TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import GOODS, INVOICE_PRINT_FORMAT, SERVICE
from erpnext_sverige.sweden_compliance.invoice import get_invoice_context
from erpnext_sverige.sweden_compliance.vat_return import get_vat_return
from erpnext_sverige.tests.utils import (
	COMPANY,
	COMPANY_ABBR,
	account,
	ensure_test_company,
	make_invoice,
	make_item,
	make_party,
)


def gl(voucher_no):
	rows = frappe.get_all(
		"GL Entry",
		filters={"voucher_no": voucher_no, "is_cancelled": 0},
		fields=["account", "debit", "credit"],
	)
	result = {}
	for row in rows:
		result[row.account] = result.get(row.account, 0) + row.debit - row.credit
	return result


def credit_note(invoice):
	doc = make_sales_return(invoice.name)
	doc.insert()
	doc.submit()
	return doc


class TestCreditNotes(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		frappe.db.set_value("Company", COMPANY, {"tax_id": "5560000000", "se_use_ocr": 1})
		frappe.db.commit()

	def setUp(self):
		self.date = frappe.utils.today()
		self.service = make_item("TEST-SE-TJANST", kind=SERVICE)
		self.goods_12 = make_item("TEST-SE-VARA-12", kind=GOODS, template=f"Moms 12 % - {COMPANY_ABBR}")
		self.customer_se = make_party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)
		self.customer_eu = make_party("Customer", "Test EU Kunde GmbH", TAX_CATEGORY_EU)
		self.supplier_eu = make_party("Supplier", "Test EU Lieferant GmbH", TAX_CATEGORY_EU)

	def tearDown(self):
		frappe.db.rollback()

	def test_swedish_credit_note_reverses_accounts_and_vat(self):
		invoice = make_invoice(
			"Sales Invoice", self.customer_se, [(self.service, 1000), (self.goods_12, 500)]
		)
		credit = credit_note(invoice)

		self.assertEqual(credit.is_return, 1)
		self.assertEqual([row.income_account for row in credit.items], [account("3001"), account("3002")])
		entries = gl(credit.name)
		self.assertEqual(entries[account("3001")], 1000)
		self.assertEqual(entries[account("3002")], 500)
		self.assertEqual(entries[account("2611")], 250)
		self.assertEqual(entries[account("2621")], 60)
		self.assertEqual(entries[account("1510")], -1810)

	def test_credit_note_has_no_ocr_but_invoice_has(self):
		invoice = make_invoice("Sales Invoice", self.customer_se, [(self.service, 100)])
		self.assertTrue(invoice.se_ocr)
		self.assertFalse(credit_note(invoice).se_ocr)

	def test_eu_credit_note(self):
		invoice = make_invoice("Sales Invoice", self.customer_eu, [(self.service, 800)])
		credit = credit_note(invoice)
		self.assertEqual(credit.items[0].income_account, account("3308"))
		self.assertEqual(credit.total_taxes_and_charges, 0)

	def test_vat_return_nets_to_zero_after_full_credit(self):
		invoice = make_invoice(
			"Sales Invoice", self.customer_se, [(self.service, 1000), (self.goods_12, 500)]
		)
		credit_note(invoice)
		boxes = get_vat_return(COMPANY, self.date, self.date)
		for box in ("05", "10", "11", "49"):
			self.assertEqual(boxes[box], 0, box)

	def test_partial_credit_reduces_vat_return(self):
		invoice = make_invoice("Sales Invoice", self.customer_se, [(self.service, 1000)])
		credit = make_sales_return(invoice.name)
		credit.items[0].qty = -1
		credit.items[0].rate = 400
		credit.insert()
		credit.submit()
		boxes = get_vat_return(COMPANY, self.date, self.date)
		self.assertEqual(boxes["05"], 600)
		self.assertEqual(boxes["10"], 150)

	def test_credit_note_print(self):
		invoice = make_invoice("Sales Invoice", self.customer_se, [(self.service, 1000)])
		credit = credit_note(invoice)
		frappe.local.lang = "sv"
		html = frappe.get_print("Sales Invoice", credit.name, print_format=INVOICE_PRINT_FORMAT, doc=credit)
		self.assertIn("Kreditfaktura", html)
		self.assertIn("Kredit avser faktura", html)
		self.assertIn(invoice.name, html)
		self.assertNotIn("Förfallodatum", html)
		self.assertNotIn("OCR-nummer", html)
		summary = get_invoice_context(credit)["vat_summary"]
		self.assertEqual(summary[0]["base"], -1000)
		self.assertEqual(summary[0]["vat"], -250)

	def test_eu_debit_note_reverses_reverse_charge(self):
		invoice = make_invoice("Purchase Invoice", self.supplier_eu, [(self.service, 1500)])
		debit = make_debit_note(invoice.name)
		debit.bill_no = frappe.generate_hash(length=8)
		debit.insert()
		debit.submit()

		self.assertEqual(debit.items[0].expense_account, account("4535"))
		entries = gl(debit.name)
		self.assertEqual(entries[account("4535")], -1500)
		self.assertEqual(entries[account("2645")], -375)
		self.assertEqual(entries[account("2614")], 375)
		boxes = get_vat_return(COMPANY, self.date, self.date)
		self.assertEqual(boxes["21"], 0)
		self.assertEqual(boxes["30"], 0)
		self.assertEqual(boxes["48"], 0)
