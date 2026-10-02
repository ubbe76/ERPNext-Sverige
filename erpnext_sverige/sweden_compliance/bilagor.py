"""Bilagor (underlag) på bokförda dokument får inte tas bort (bokföringslagen 5 kap. 5 § och 7 kap.).

Ett kvitto eller en inskannad leverantörsfaktura är själva verifikationen och ska bevaras. Nya bilagor går
att lägga till efter bokföring, men en bilaga på ett bokfört eller makulerat dokument kan inte tas bort eller
flyttas till ett annat dokument. När ett dokument som får raderas (t.ex. ett utkast) tas bort, följer dess
bilagor med som vanligt: dokumentet är då redan borta när bilagorna raderas.
"""

import frappe
from frappe import _


def _is_protected(doctype: str | None, name: str | None) -> bool:
	if not (doctype and name) or not frappe.db.exists("DocType", doctype):
		return False
	if not frappe.get_meta(doctype).is_submittable:
		return False
	return frappe.db.get_value(doctype, name, "docstatus") in (1, 2)


def _throw(doctype: str, name: str):
	frappe.throw(
		_(
			"Bilagan hör till {0} {1}, som är bokförd. Underlag till bokförda verifikationer ska bevaras och kan inte tas bort."
		).format(_(doctype), name),
		title=_("Bilagan är skyddad"),
	)


def skydda_mot_radering(doc, method=None):
	"""File.on_trash"""
	if _is_protected(doc.attached_to_doctype, doc.attached_to_name):
		_throw(doc.attached_to_doctype, doc.attached_to_name)


def skydda_mot_flytt(doc, method=None):
	"""File.validate: en bilaga på ett bokfört dokument får inte flyttas därifrån."""
	if doc.is_new():
		return
	before = doc.get_doc_before_save()
	if not before or (
		before.attached_to_doctype == doc.attached_to_doctype
		and before.attached_to_name == doc.attached_to_name
	):
		return
	if _is_protected(before.attached_to_doctype, before.attached_to_name):
		_throw(before.attached_to_doctype, before.attached_to_name)
