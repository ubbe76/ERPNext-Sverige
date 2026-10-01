import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import today

from erpnext_sverige.setup.company import TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import SERVICE
from erpnext_sverige.sweden_compliance.sie_export import (
	SIE_ENCODING,
	_amount,
	_quote,
	build_sie,
	format_sie_org_nr,
)
from erpnext_sverige.tests.utils import COMPANY, ensure_test_company, make_invoice, make_item, make_party


class TestSieFormatting(UnitTestCase):
	def test_quote(self):
		self.assertEqual(_quote('Kund "AB"'), '"Kund \\"AB\\""')
		self.assertEqual(_quote("rad1\nrad2"), '"rad1 rad2"')

	def test_amount(self):
		self.assertEqual(_amount(1234.5), "1234.50")
		self.assertEqual(_amount(-0.004), "0.00")

	def test_org_nr(self):
		self.assertEqual(format_sie_org_nr("5560000000"), "556000-0000")
		self.assertEqual(format_sie_org_nr("165560000000"), "556000-0000")
		self.assertEqual(format_sie_org_nr("SE556000000001"), "556000-0000")
		self.assertIsNone(format_sie_org_nr(""))


class TestSieExport(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()
		if not frappe.db.get_value("Company", COMPANY, "tax_id"):
			frappe.db.set_value("Company", COMPANY, "tax_id", "5560000000")
			frappe.db.commit()
		cls.fiscal_year = frappe.db.get_value(
			"Fiscal Year", {"year_start_date": ["<=", today()], "year_end_date": [">=", today()]}
		)

	def setUp(self):
		service = make_item("TEST-SE-TJANST", kind=SERVICE)
		customer = make_party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)
		supplier = make_party("Supplier", "Test SE Leverantör AB", TAX_CATEGORY_SE)
		self.sales_invoice = make_invoice("Sales Invoice", customer, [(service, 1000)]).name
		self.purchase_invoice = make_invoice("Purchase Invoice", supplier, [(service, 400)]).name
		cancelled = make_invoice("Sales Invoice", customer, [(service, 100)])
		cancelled.cancel()

	def tearDown(self):
		frappe.db.rollback()

	def sie_lines(self):
		content = build_sie(COMPANY, self.fiscal_year).decode(SIE_ENCODING)
		self.assertIn("\r\n", content)
		return content.splitlines()

	def test_header(self):
		lines = self.sie_lines()
		self.assertEqual(lines[0], "#FLAGGA 0")
		self.assertIn("#FORMAT PC8", lines)
		self.assertIn("#SIETYP 4", lines)
		self.assertIn(f'#FNAMN "{COMPANY}"', lines)
		self.assertIn("#ORGNR 556000-0000", lines)
		self.assertIn('#KONTO 3001 "Försäljning inom Sverige, 25 % moms"', lines)
		self.assertIn("#KTYP 3001 I", lines)
		self.assertIn("#KTYP 1510 T", lines)
		self.assertIn('#DIM 1 "Kostnadsställe"', lines)

	def test_vouchers_balance_and_series(self):
		lines = self.sie_lines()
		vouchers = self.parse_vouchers(lines)
		series = [head.split()[1] for head in vouchers]
		self.assertIn("B", series)  # kundfakturor
		self.assertIn("C", series)  # leverantörsfakturor
		for head, rows in vouchers.items():
			self.assertAlmostEqual(sum(amount for _account, amount in rows), 0, places=2, msg=head)

		texts = " ".join(vouchers)
		self.assertIn("Makulering av", texts)
		self.assertIn(self.sales_invoice, texts)
		self.assertIn(self.purchase_invoice, texts)

		# Numren löper 1, 2, 3 … inom varje serie
		numbers = [int(head.split()[2]) for head in vouchers if head.split()[1] == "B"]
		self.assertEqual(numbers, list(range(1, len(numbers) + 1)))

	def test_sales_invoice_rows(self):
		vouchers = self.parse_vouchers(self.sie_lines())
		# Andra tester (t.ex. frakt) lämnar fakturor kvar i samma bolag och period, så leta upp den egna fakturan
		sale = next(
			rows
			for head, rows in vouchers.items()
			if " B " in head and self.sales_invoice in head and "Makulering" not in head
		)
		accounts = dict(sale)
		self.assertEqual(accounts["1510"], 1250)
		self.assertEqual(accounts["3001"], -1000)
		self.assertEqual(accounts["2611"], -250)

	def test_result_includes_period_activity(self):
		lines = self.sie_lines()
		res = {line.split()[2]: float(line.split()[3]) for line in lines if line.startswith("#RES 0 ")}
		self.assertLessEqual(res["3001"], -1000)

	@staticmethod
	def parse_vouchers(lines):
		vouchers, current = {}, None
		for line in lines:
			if line.startswith("#VER "):
				current = line
				vouchers[current] = []
			elif line.strip().startswith("#TRANS") and current:
				parts = line.split()
				vouchers[current].append((parts[1], float(parts[-1])))
			elif line == "}":
				current = None
		return vouchers
