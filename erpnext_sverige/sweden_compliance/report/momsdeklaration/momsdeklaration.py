import frappe
from frappe import _

from erpnext_sverige.sweden_compliance.vat_return import BOXES, box_accounts, get_vat_return


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not (filters.company and filters.from_date and filters.to_date):
		return get_columns(), []

	boxes = get_vat_return(filters.company, filters.from_date, filters.to_date)
	data = [
		{
			"box": box.number,
			"label": box.label,
			"amount": boxes[box.number],
			"accounts": box_accounts(box) if box.ranges or box.number == "49" else _("Stöds inte"),
			"bold": 1 if box.number == "49" else 0,
		}
		for box in sorted(BOXES, key=lambda b: b.number)
	]
	return get_columns(), data


def get_columns():
	return [
		{"fieldname": "box", "label": _("Ruta"), "fieldtype": "Data", "width": 70},
		{"fieldname": "label", "label": _("Beskrivning"), "fieldtype": "Data", "width": 420},
		{"fieldname": "amount", "label": _("Belopp (kr)"), "fieldtype": "Int", "width": 130},
		{"fieldname": "accounts", "label": _("Konton"), "fieldtype": "Data", "width": 300},
	]
