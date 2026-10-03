"""Brevhuvud Sverige: mindre logotyp (max 120 x 30 px i stället för 240 x 60 px).

Byter bara ut storleksangivelsen, så att andra ändringar i brevhuvudet behålls.
"""

import frappe

from erpnext_sverige.setup.company import LETTER_HEAD

GAMMAL = "max-height: 60px; max-width: 240px"
NY = "max-height: 30px; max-width: 120px"


def execute():
	innehall = frappe.db.get_value("Letter Head", LETTER_HEAD, "content")
	if innehall and GAMMAL in innehall:
		frappe.db.set_value(
			"Letter Head", LETTER_HEAD, "content", innehall.replace(GAMMAL, NY), update_modified=False
		)
