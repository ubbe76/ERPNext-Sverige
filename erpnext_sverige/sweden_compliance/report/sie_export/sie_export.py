from collections import defaultdict

import frappe
from frappe import _

from erpnext_sverige.sweden_compliance.sie_export import OTHER_SERIES, SERIES, get_vouchers


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not (filters.company and filters.fiscal_year):
		return get_columns(), []

	start, end = frappe.db.get_value("Fiscal Year", filters.fiscal_year, ["year_start_date", "year_end_date"])
	summary = defaultdict(lambda: {"count": 0, "debit": 0.0, "first": None, "last": None})
	for voucher in get_vouchers(filters.company, start, end):
		row = summary[voucher.series]
		row["count"] += 1
		row["debit"] += sum(amount for _number, _objects, amount in voucher.rows if amount > 0)
		row["first"] = row["first"] or voucher.date
		row["last"] = voucher.date

	labels = {series: label for series, label in [*SERIES.values(), OTHER_SERIES]}
	data = [
		{
			"series": series,
			"label": labels.get(series, ""),
			"count": row["count"],
			"debit": row["debit"],
			"first": row["first"],
			"last": row["last"],
		}
		for series, row in sorted(summary.items())
	]
	return get_columns(), data


def get_columns():
	return [
		{"fieldname": "series", "label": _("Serie"), "fieldtype": "Data", "width": 70},
		{"fieldname": "label", "label": _("Dokumenttyp"), "fieldtype": "Data", "width": 200},
		{"fieldname": "count", "label": _("Verifikationer"), "fieldtype": "Int", "width": 130},
		{"fieldname": "debit", "label": _("Summa debet"), "fieldtype": "Currency", "width": 150},
		{"fieldname": "first", "label": _("Första datum"), "fieldtype": "Date", "width": 120},
		{"fieldname": "last", "label": _("Sista datum"), "fieldtype": "Date", "width": 120},
	]
