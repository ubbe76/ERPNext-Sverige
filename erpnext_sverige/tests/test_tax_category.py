from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from erpnext_sverige.setup.company import TAX_CATEGORY_EU, TAX_CATEGORY_NON_EU, TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import SERVICE
from erpnext_sverige.sweden_compliance.tax_category import (
	category_for,
	check_vies,
	is_valid_vat_format,
	normalize_vat_number,
)
from erpnext_sverige.tests.utils import COMPANY, ensure_test_company, make_invoice, make_item


class TestCategoryAndFormat(UnitTestCase):
	def test_category_for_country(self):
		self.assertEqual(category_for("Sweden"), TAX_CATEGORY_SE)
		self.assertEqual(category_for("Germany"), TAX_CATEGORY_EU)
		self.assertEqual(category_for("Germany", is_individual=True), TAX_CATEGORY_SE)
		self.assertEqual(category_for("United States"), TAX_CATEGORY_NON_EU)
		self.assertEqual(category_for("Norway"), TAX_CATEGORY_NON_EU)
		self.assertIsNone(category_for(None))

	def test_vat_formats(self):
		for number in (
			"DE123456789",
			"ATU12345678",
			"EL123456789",
			"NL123456789B01",
			"SE556000000001",
			"FR12345678901",
		):
			self.assertTrue(is_valid_vat_format(number), number)
		for number in ("DE12345", "123456789", "XX123456789", "NL123456789", "SE5560000000"):
			self.assertFalse(is_valid_vat_format(number), number)

	def test_normalize(self):
		self.assertEqual(normalize_vat_number(" de 123.456-789 "), "DE123456789")

	def test_vies_valid(self):
		response = MagicMock()
		response.json.return_value = {
			"isValid": True,
			"name": "Test GmbH",
			"address": "Berlin",
			"userError": "VALID",
		}
		with patch(
			"erpnext_sverige.sweden_compliance.tax_category.requests.get", return_value=response
		) as get:
			result = check_vies("DE 123456789")
		self.assertTrue(result["valid"])
		self.assertEqual(result["name"], "Test GmbH")
		self.assertIn("/ms/DE/vat/123456789", get.call_args.args[0])

	def test_vies_unreachable(self):
		with patch(
			"erpnext_sverige.sweden_compliance.tax_category.requests.get", side_effect=OSError("offline")
		):
			result = check_vies("DE123456789")
		self.assertIsNone(result["valid"])
		self.assertTrue(result["error"])

	def test_vies_bad_format_skips_request(self):
		with patch("erpnext_sverige.sweden_compliance.tax_category.requests.get") as get:
			self.assertFalse(check_vies("DE12")["valid"])
		get.assert_not_called()


class TestTaxCategoryOnParties(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()

	def tearDown(self):
		frappe.db.rollback()

	def customer(self, name, customer_type="Company", tax_id=None):
		return frappe.get_doc(
			{"doctype": "Customer", "customer_name": name, "customer_type": customer_type, "tax_id": tax_id}
		).insert()

	def address(self, country, link_doctype, link_name):
		return frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": link_name,
				"address_line1": "Teststraße 1",
				"city": "Teststadt",
				"country": country,
				"links": [{"link_doctype": link_doctype, "link_name": link_name}],
			}
		).insert()

	def test_address_category_from_country(self):
		company = self.customer("Test Kategori GmbH")
		self.assertEqual(self.address("Germany", "Customer", company.name).tax_category, TAX_CATEGORY_EU)
		self.assertEqual(
			self.address("United States", "Customer", company.name).tax_category, TAX_CATEGORY_NON_EU
		)
		self.assertEqual(self.address("Sweden", "Customer", company.name).tax_category, TAX_CATEGORY_SE)

	def test_eu_individual_gets_swedish_vat(self):
		person = self.customer("Test Privatperson DE", customer_type="Individual")
		self.assertEqual(self.address("Germany", "Customer", person.name).tax_category, TAX_CATEGORY_SE)

	def test_customer_gets_category_from_first_address(self):
		customer = self.customer("Test Ny Kund Inc")
		self.assertFalse(customer.tax_category)
		self.address("United States", "Customer", customer.name)
		self.assertEqual(frappe.db.get_value("Customer", customer.name, "tax_category"), TAX_CATEGORY_NON_EU)

	def test_manual_category_is_kept(self):
		address = self.address("Germany", "Customer", self.customer("Test Manuell GmbH").name)
		address.tax_category = TAX_CATEGORY_SE
		address.save()
		self.assertEqual(address.tax_category, TAX_CATEGORY_SE)

	def test_customer_type_change_updates_addresses(self):
		customer = self.customer("Test Byter Typ GmbH")
		address = self.address("Germany", "Customer", customer.name)
		customer.reload()
		customer.customer_type = "Individual"
		customer.save()
		self.assertEqual(frappe.db.get_value("Address", address.name, "tax_category"), TAX_CATEGORY_SE)

	def test_invalid_eu_vat_number_is_rejected(self):
		customer = self.customer("Test Fel Momsnr GmbH")
		self.address("Germany", "Customer", customer.name)

		def save_with(tax_id):
			doc = frappe.get_doc("Customer", customer.name)
			doc.tax_id = tax_id
			doc.save()
			return doc

		self.assertRaises(frappe.ValidationError, save_with, "DE123")
		self.assertRaises(frappe.ValidationError, save_with, "FR12345678901")  # rätt format men fel land
		self.assertEqual(save_with("de 123 456 789").tax_id, "DE123456789")

	def test_swedish_org_number_in_tax_id_is_allowed(self):
		customer = self.customer("Test Svensk Kund AB", tax_id="556000-0000")
		self.address("Sweden", "Customer", customer.name)
		customer.reload()
		customer.save()

	def test_eu_invoice_requires_vat_number(self):
		service = make_item("TEST-SE-TJANST", kind=SERVICE)
		customer = self.customer("Test Utan Momsnr GmbH")
		self.address("Germany", "Customer", customer.name)
		si = make_invoice("Sales Invoice", customer.name, [(service, 100)], submit=False)
		self.assertEqual(si.tax_category, TAX_CATEGORY_EU)
		self.assertRaises(frappe.ValidationError, si.submit)

		frappe.db.set_value("Customer", customer.name, "tax_id", "DE123456789")
		si.reload()
		si.submit()
		self.assertEqual(si.docstatus, 1)
		self.assertEqual(frappe.db.get_value("Sales Invoice", si.name, "company"), COMPANY)
