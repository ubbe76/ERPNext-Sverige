"""Brevhuvud Sverige skapades med källan Bild (Frappes before_insert) fast innehållet är HTML-mallen.

Formuläret visade då ett tomt bildfält och dolde Header HTML. Har ingen bild laddats upp sätts källan till HTML.
"""

import frappe

from erpnext_sverige.setup.company import LETTER_HEAD


def execute():
	brevhuvud = frappe.db.get_value("Letter Head", LETTER_HEAD, ["source", "image"], as_dict=True)
	if brevhuvud and brevhuvud.source == "Image" and not brevhuvud.image:
		frappe.db.set_value("Letter Head", LETTER_HEAD, "source", "HTML", update_modified=False)
