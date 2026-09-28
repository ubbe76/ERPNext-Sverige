from datetime import date

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from erpnext_sverige.setup.company import TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import SERVICE
from erpnext_sverige.sweden_compliance.bgmax import BgMaxError, parse_bgmax
from erpnext_sverige.tests.utils import COMPANY, ensure_test_company, make_invoice, make_item, make_party


def _record(code: str, fields: dict[int, str]) -> str:
	"""Post om 80 tecken med värden på 1-baserade startpositioner."""
	line = [" "] * 80
	line[0:2] = code
	for start, value in fields.items():
		line[start - 1 : start - 1 + len(value)] = value
	return "".join(line)


def build_bgmax(payments, payment_date="20260928", receiving_bankgiro="9912346", test=False):
	"""payments: [(ocr, belopp_kr, löpnummer, namn, avdrag)]"""
	lines = [_record("01", {3: "BGMAX", 23: "01", 25: "20260928103000123456", 45: "T" if test else "P"})]
	lines.append(_record("05", {3: receiving_bankgiro.zfill(10), 23: "SEK"}))
	count = 0
	for ocr, amount, serial, name, deduction in payments:
		code = "21" if deduction else "20"
		lines.append(
			_record(
				code,
				{
					3: "56781234".zfill(10),
					13: ocr.ljust(25),
					38: str(round(amount * 100)).zfill(18),
					56: "2",
					57: "1",
					58: serial.zfill(12),
				},
			)
		)
		if name:
			lines.append(_record("26", {3: name}))
		count += 0 if deduction else 1
	total = sum(a for _o, a, _s, _n, d in payments if not d)
	lines.append(
		_record(
			"15",
			{
				3: "1234567890".ljust(35),
				38: payment_date,
				46: "00001",
				51: str(round(total * 100)).zfill(18),
				69: "SEK",
				72: str(count).zfill(8),
			},
		)
	)
	lines.append(_record("70", {3: str(count).zfill(8), 11: "00000000", 19: "00000000", 27: "00000001"}))
	return ("\r\n".join(lines) + "\r\n").encode("iso-8859-1")


class TestParseBgMax(UnitTestCase):
	def test_payments(self):
		result = parse_bgmax(
			build_bgmax(
				[("20260000417", 12278.0, "123", "Kund Åberg AB", False), ("555", 50.5, "124", "", False)]
			)
		)
		self.assertEqual(len(result.payments), 2)
		first = result.payments[0]
		self.assertEqual(first.reference, "20260000417")
		self.assertEqual(first.amount, 12278.0)
		self.assertEqual(first.bgc_serial, "000000000123")
		self.assertEqual(first.payer_name, "Kund Åberg AB")
		self.assertEqual(first.payer_bankgiro, "56781234")
		self.assertEqual(first.receiving_bankgiro, "9912346")
		self.assertEqual(first.payment_date, date(2026, 9, 28))
		self.assertEqual(result.payments[1].amount, 50.5)
		self.assertFalse(result.test_mark)

	def test_deduction_is_negative(self):
		result = parse_bgmax(build_bgmax([("1", 100, "1", "", False), ("2", 30, "2", "", True)]))
		self.assertEqual(result.payments[1].amount, -30)
		self.assertTrue(result.payments[1].is_deduction)

	def test_not_bgmax(self):
		self.assertRaises(BgMaxError, parse_bgmax, b"hello")

	def test_count_mismatch(self):
		content = build_bgmax([("1", 100, "1", "", False)]).decode("iso-8859-1")
		content = content.replace(
			_record("70", {3: "00000001", 11: "00000000", 19: "00000000", 27: "00000001"}),
			_record("70", {3: "00000002", 11: "00000000", 19: "00000000", 27: "00000001"}),
		)
		self.assertRaises(BgMaxError, parse_bgmax, content)


class TestBankgiroInbetalning(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		frappe.db.set_value("Company", COMPANY, {"tax_id": "5560000000", "se_use_ocr": 1})
		frappe.db.commit()

	def setUp(self):
		self.service = make_item("TEST-SE-TJANST", kind=SERVICE)
		self.customer = make_party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)
		self.invoice = make_invoice("Sales Invoice", self.customer, [(self.service, 1000)])  # 1 250 kr
		self.other = make_invoice("Sales Invoice", self.customer, [(self.service, 200)])  # 250 kr

	def tearDown(self):
		frappe.db.rollback()

	def import_file(self, payments):
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"bgmax-{frappe.generate_hash(length=6)}.txt",
				"content": build_bgmax(payments),
				"is_private": 1,
			}
		).insert()
		doc = frappe.get_doc(
			{"doctype": "Bankgiro Inbetalning", "company": COMPANY, "bgmax_file": file_doc.file_url}
		).insert()
		doc.read_file()
		doc.reload()
		return doc

	def test_match_by_ocr_creates_draft_payment(self):
		doc = self.import_file(
			[
				(self.invoice.se_ocr, 1250, "901", "Test SE Kund AB", False),
				("99999", 10, "902", "Okänd", False),
			]
		)
		matched, unmatched = doc.payments
		self.assertEqual(matched.status, "Matchad")
		self.assertEqual(matched.sales_invoice, self.invoice.name)
		self.assertEqual(unmatched.status, "Ej matchad")
		self.assertEqual((doc.matched_count, doc.unmatched_count), (1, 1))
		self.assertEqual(doc.total_amount, 1260)

		pe = frappe.get_doc("Payment Entry", matched.payment_entry)
		self.assertEqual(pe.docstatus, 0)
		self.assertEqual(pe.paid_amount, 1250)
		self.assertEqual(pe.references[0].reference_name, self.invoice.name)
		self.assertEqual(pe.reference_no, "BG 000000000901")
		self.assertEqual(pe.paid_to, frappe.get_cached_value("Company", COMPANY, "default_bank_account"))

	def test_submit_payments_settles_invoice(self):
		doc = self.import_file([(self.invoice.se_ocr, 1250, "911", "", False)])
		self.assertEqual(doc.submit_payments(), 1)
		self.assertEqual(frappe.db.get_value("Sales Invoice", self.invoice.name, "outstanding_amount"), 0)
		self.assertEqual(frappe.db.get_value("Bankgiro Inbetalning", doc.name, "status"), "Bokförd")

	def test_partial_payment(self):
		doc = self.import_file([(self.invoice.se_ocr, 500, "921", "", False)])
		doc.submit_payments()
		self.assertEqual(frappe.db.get_value("Sales Invoice", self.invoice.name, "outstanding_amount"), 750)

	def test_same_file_twice_is_not_registered_again(self):
		payments = [(self.invoice.se_ocr, 1250, "931", "", False)]
		self.import_file(payments)
		second = self.import_file(payments)
		self.assertEqual(second.payments[0].status, "Redan registrerad")
		self.assertFalse(second.payments[0].payment_entry)

	def test_manual_match(self):
		doc = self.import_file([("FAKTURA 42", 250, "941", "Test SE Kund AB", False)])
		self.assertEqual(doc.payments[0].status, "Ej matchad")
		doc.payments[0].sales_invoice = self.other.name
		doc.save()
		doc.create_payments()
		doc.reload()
		self.assertTrue(doc.payments[0].payment_entry)
		self.assertEqual(doc.payments[0].status, "Matchad")
