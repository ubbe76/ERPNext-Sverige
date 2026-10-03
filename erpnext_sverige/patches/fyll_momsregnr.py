"""Fyller i det nya fältet Momsregistreringsnummer från organisationsnumret, så att fakturorna ser ut som förut."""

import frappe

from erpnext_sverige.setup.custom_fields import create_custom_fields
from erpnext_sverige.sweden_compliance.invoice import vat_number


def execute():
	# after_migrate (som skapar custom fields) körs efter patcharna
	create_custom_fields()
	for bolag in frappe.get_all(
		"Company",
		filters={"country": "Sweden", "tax_id": ("is", "set"), "se_momsregnr": ("is", "not set")},
		fields=["name", "tax_id"],
	):
		if nummer := vat_number(bolag.tax_id):
			frappe.db.set_value("Company", bolag.name, "se_momsregnr", nummer, update_modified=False)
