import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from erpnext_sverige.setup.company import TAX_CATEGORY_EU, TAX_CATEGORY_NON_EU, TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import GOODS, INVOICE_PRINT_FORMAT, SERVICE
from erpnext_sverige.sweden_compliance.invoice import (
	NOTE_EU_GOODS,
	NOTE_EXPORT,
	NOTE_REVERSE_CHARGE,
	format_org_nr,
	get_invoice_context,
	luhn_check_digit,
	make_ocr,
	vat_number,
)
from erpnext_sverige.tests.utils import (
	COMPANY,
	COMPANY_ABBR,
	ensure_test_company,
	make_invoice,
	make_item,
	make_party,
)


def luhn_valid(number: str) -> bool:
	return luhn_check_digit(number[:-1]) == number[-1]


class TestOcr(UnitTestCase):
	def test_luhn(self):
		self.assertEqual(luhn_check_digit("7992739871"), "3")  # klassiskt exempel

	def test_ocr_has_length_and_check_digit(self):
		ocr = make_ocr("ACC-SINV-2026-00042")
		self.assertEqual(ocr[:-2], "202600042")  # inledande nollor och bokstäver bort
		self.assertEqual(ocr[-2], str(len(ocr) % 10))  # längdsiffra
		self.assertTrue(luhn_valid(ocr))

	def test_ocr_without_digits(self):
		self.assertIsNone(make_ocr("ABC"))

	def test_ocr_max_25_digits(self):
		self.assertEqual(len(make_ocr("9" * 40)), 25)


class TestCompanyNumbers(UnitTestCase):
	def test_org_nr_and_vat_number(self):
		self.assertEqual(format_org_nr("5560000000"), "556000-0000")
		self.assertEqual(vat_number("556000-0000"), "SE556000000001")
		self.assertEqual(vat_number("SE556000000001"), "SE556000000001")
		self.assertIsNone(vat_number(""))


class TestSwedishInvoice(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		frappe.db.set_value("Company", COMPANY, {"tax_id": "5560000000", "se_f_skatt": 1, "se_use_ocr": 1})
		frappe.db.commit()

	def setUp(self):
		self.service = make_item("TEST-SE-TJANST", kind=SERVICE)
		self.goods = make_item("TEST-SE-VARA", kind=GOODS)
		self.goods_12 = make_item("TEST-SE-VARA-12", kind=GOODS, template=f"Moms 12 % - {COMPANY_ABBR}")
		self.customer_se = make_party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)
		self.customer_eu = make_party("Customer", "Test EU Kunde GmbH", TAX_CATEGORY_EU)
		self.customer_export = make_party("Customer", "Test Export Inc", TAX_CATEGORY_NON_EU)
		frappe.db.set_value("Customer", self.customer_eu, "tax_id", "DE123456789")

	def tearDown(self):
		frappe.db.rollback()

	def test_ocr_is_set_on_invoice(self):
		si = make_invoice("Sales Invoice", self.customer_se, [(self.service, 100)], submit=False)
		self.assertTrue(si.se_ocr)
		self.assertTrue(luhn_valid(si.se_ocr))

	def test_vat_summary_per_rate(self):
		si = make_invoice("Sales Invoice", self.customer_se, [(self.service, 1000), (self.goods_12, 500)])
		summary = {row["rate"]: row for row in get_invoice_context(si)["vat_summary"]}
		self.assertEqual(summary[25]["base"], 1000)
		self.assertEqual(summary[25]["vat"], 250)
		self.assertEqual(summary[12]["base"], 500)
		self.assertEqual(summary[12]["vat"], 60)

	def test_company_details(self):
		ctx = get_invoice_context(make_invoice("Sales Invoice", self.customer_se, [(self.service, 100)]))
		self.assertEqual(ctx["org_nr"], "556000-0000")
		self.assertEqual(ctx["vat_no"], "SE556000000001")
		self.assertTrue(ctx["f_skatt"])
		self.assertEqual(ctx["notes"], [])

	def test_eu_notes_and_customer_vat_number(self):
		si = make_invoice("Sales Invoice", self.customer_eu, [(self.service, 100), (self.goods, 100)])
		ctx = get_invoice_context(si)
		self.assertEqual(ctx["notes"], [NOTE_EU_GOODS, NOTE_REVERSE_CHARGE])
		self.assertEqual(ctx["customer_vat_no"], "DE123456789")
		self.assertEqual({row["rate"] for row in ctx["vat_summary"]}, {0})

	def test_export_note(self):
		si = make_invoice("Sales Invoice", self.customer_export, [(self.goods, 100)])
		self.assertEqual(get_invoice_context(si)["notes"], [NOTE_EXPORT])

	def test_print_format_renders_in_swedish(self):
		si = make_invoice("Sales Invoice", self.customer_se, [(self.service, 1000), (self.goods_12, 500)])
		frappe.local.lang = "sv"
		html = frappe.get_print("Sales Invoice", si.name, print_format=INVOICE_PRINT_FORMAT, doc=si)
		for text in ("Faktura", "Förfallodatum", "Moms 25 % på", "Moms 12 % på", "Att betala"):
			self.assertIn(text, html)
		for text in ("556000-0000", "SE556000000001", "Godkänd för F-skatt", si.se_ocr):
			self.assertIn(text, html)
