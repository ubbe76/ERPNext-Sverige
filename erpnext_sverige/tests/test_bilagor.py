import frappe
from frappe.tests import IntegrationTestCase

from erpnext_sverige.setup.company import TAX_CATEGORY_SE
from erpnext_sverige.setup.custom_fields import GOODS
from erpnext_sverige.tests.utils import ensure_test_company, make_invoice, make_item, make_party


def attach(doc):
	return frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"underlag-{frappe.generate_hash(length=6)}.txt",
			"content": "kvitto",
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"is_private": 1,
		}
	).insert()


class TestBilagor(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_test_company()

	def setUp(self):
		self.item = make_item("TEST-SE-BILAGA", kind=GOODS)
		self.customer = make_party("Customer", "Test SE Kund AB", TAX_CATEGORY_SE)

	def tearDown(self):
		frappe.db.rollback()

	def invoice(self, submit):
		return make_invoice("Sales Invoice", self.customer, [(self.item, 100)], submit=submit)

	def test_draft_attachment_can_be_deleted(self):
		f = attach(self.invoice(submit=False))
		frappe.delete_doc("File", f.name)
		self.assertFalse(frappe.db.exists("File", f.name))

	def test_submitted_attachment_is_protected(self):
		f = attach(self.invoice(submit=True))
		self.assertRaises(frappe.ValidationError, frappe.delete_doc, "File", f.name)
		self.assertTrue(frappe.db.exists("File", f.name))

	def test_cancelled_attachment_is_protected(self):
		si = self.invoice(submit=True)
		f = attach(si)
		si.cancel()
		self.assertRaises(frappe.ValidationError, frappe.delete_doc, "File", f.name)

	def test_attachment_can_be_added_after_submit(self):
		f = attach(self.invoice(submit=True))
		self.assertTrue(frappe.db.exists("File", f.name))

	def test_cannot_move_attachment_off_submitted_document(self):
		f = attach(self.invoice(submit=True))
		other = self.invoice(submit=False)
		f.attached_to_name = other.name
		self.assertRaises(frappe.ValidationError, f.save)

	def test_deleting_draft_removes_its_attachments(self):
		si = self.invoice(submit=False)
		f = attach(si)
		frappe.delete_doc("Sales Invoice", si.name)
		self.assertFalse(frappe.db.exists("File", f.name))
