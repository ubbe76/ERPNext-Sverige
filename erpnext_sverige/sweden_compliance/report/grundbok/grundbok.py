"""Grundbok: bokföringsposterna i registreringsordning (bokföringslagen 5 kap. 1 §).

Huvudboken i ERPNext sorteras efter bokföringsdatum. Grundboken visar i stället posterna i den ordning de
registrerades, med registreringstidpunkt och vem som registrerade dem. Makuleringar visas som egna rader
där de registrerades, eftersom Immutable Ledger bokför en motpost i stället för att ändra originalet.
"""

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import add_days, getdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Registrerad"), "fieldname": "creation", "fieldtype": "Datetime", "width": 160},
		{"label": _("Bokföringsdatum"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
		{"label": _("Verifikattyp"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 140},
		{
			"label": _("Verifikation"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 200,
		},
		{
			"label": _("Konto"),
			"fieldname": "account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 220,
		},
		{"label": _("Debet"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
		{"label": _("Kredit"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
		{"label": _("Part"), "fieldname": "party", "fieldtype": "Data", "width": 160},
		{"label": _("Text"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
		{
			"label": _("Registrerad av"),
			"fieldname": "owner",
			"fieldtype": "Link",
			"options": "User",
			"width": 160,
		},
	]


def get_data(filters) -> list[dict]:
	gle = DocType("GL Entry")
	query = (
		frappe.qb.from_(gle)
		.select(
			gle.creation,
			gle.posting_date,
			gle.voucher_type,
			gle.voucher_no,
			gle.account,
			gle.debit,
			gle.credit,
			gle.party,
			gle.remarks,
			gle.owner,
		)
		.where(gle.company == filters.company)
		.orderby(gle.creation)
		.orderby(gle.name)
	)
	if filters.from_date:
		query = query.where(gle.creation >= getdate(filters.from_date))
	if filters.to_date:
		query = query.where(gle.creation < add_days(getdate(filters.to_date), 1))
	rows = query.run(as_dict=True)
	for row in rows:
		row.voucher_type = _(row.voucher_type)
	return rows
