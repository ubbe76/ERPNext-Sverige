"""Brevhuvud Sverige: logotypen med relativ adress i stället för get_url.

get_url ger site_config:s host_name (t.ex. http://<site>:8000), som andra datorer i nätet kanske inte känner
till. Då blev loggan en trasig bild i utskriftsvyn. Ändrar bara just det uttrycket, så att egna ändringar behålls.
"""

import frappe

from erpnext_sverige.setup.company import LETTER_HEAD

GAMMAL = "{{ frappe.utils.get_url(logo) }}"
NY = "{{ logo }}"


def execute():
	innehall = frappe.db.get_value("Letter Head", LETTER_HEAD, "content")
	if innehall and GAMMAL in innehall:
		frappe.db.set_value(
			"Letter Head", LETTER_HEAD, "content", innehall.replace(GAMMAL, NY), update_modified=False
		)
