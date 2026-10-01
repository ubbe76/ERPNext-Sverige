"""Avsändare och mottagare i fraktmodulens part-format, från ERPNext:s Address och Contact."""

from datetime import date, datetime, timedelta

import frappe
from frappe.utils import get_datetime, get_time, getdate, today


def part(namn, adress, kontakt, privatperson=False) -> dict:
	a = (
		frappe.db.get_value(
			"Address", adress, ["address_line1", "address_line2", "pincode", "city", "country"], as_dict=True
		)
		if adress
		else frappe._dict()
	)
	k = (
		frappe.db.get_value(
			"Contact", kontakt, ["first_name", "last_name", "mobile_no", "phone", "email_id"], as_dict=True
		)
		if kontakt
		else frappe._dict()
	)
	landskod = frappe.db.get_value("Country", a.country, "code") if a.country else None
	return {
		"namn": namn,
		"adressrad_1": a.address_line1,
		"adressrad_2": a.address_line2,
		"postnummer": a.pincode,
		"ort": a.city,
		"landskod": landskod.upper() if landskod else None,
		"kontakt_namn": " ".join(filter(None, [k.first_name, k.last_name])) or None,
		"telefon": k.mobile_no or k.phone,
		"epost": k.email_id,
		"privatperson": bool(privatperson),
	}


def avsandare(inst) -> dict:
	namn = frappe.db.get_value("Company", inst.bolag, "company_name")
	return part(namn, inst.avsandaradress, inst.avsandarkontakt)


def nasta_arbetsdag(fran: date | None = None) -> date:
	dag = getdate(fran or today()) + timedelta(days=1)
	while dag.weekday() >= 5:
		dag += timedelta(days=1)
	return dag


def upphamtningstid(datum, tid) -> datetime:
	return get_datetime(f"{getdate(datum)} {get_time(tid)}")
