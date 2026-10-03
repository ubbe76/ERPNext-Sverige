"""Brevhuvud Sverige: bara logotypen när bolaget har en, annars bolagsnamnet.

Byter bara ut innehållet om det är den förra versionen av mallen oförändrad, så att egna ändringar behålls.
"""

import os
import re

import frappe

from erpnext_sverige.setup.company import LETTER_HEAD

# Mallen före ändringen (logotyp och namn bredvid varandra med flex, som wkhtmltopdf inte klarar)
FORRA_MALLEN = '{#- Logotyp och bolagsnamn. Adress, org.nr och betaluppgifter står i de svenska mallarnas sidfot, och\n    mallarna visar själva dokumentets titel och nummer. -#}\n{%- set company = doc.get("company") if doc else None -%}\n{%- if company -%}\n{%- set logo = frappe.db.get_value("Company", company, "company_logo") -%}\n<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px">\n\t{%- if logo %}\n\t{#- Relativ adress: webbläsaren hämtar bilden från samma värd, och PDF:en gör den absolut (scrub_urls) #}\n\t<img src="{{ logo }}" alt="" style="max-height: 60px; max-width: 200px" />\n\t{%- endif %}\n\t<div style="font-size: 16px; font-weight: bold">{{ company }}</div>\n</div>\n{%- endif -%}\n'


def normalisera(mall: str) -> str:
	"""Utan Jinja-kommentarer och skillnader i blanksteg: brevhuvuden som skapats från den första mallen och
	rättats av brevhuvud_relativ_logga saknar kommentarsraden som filen fick samtidigt."""
	return " ".join(re.sub(r"\{#.*?#\}", "", mall or "", flags=re.S).split())


def execute():
	if normalisera(frappe.db.get_value("Letter Head", LETTER_HEAD, "content")) != normalisera(FORRA_MALLEN):
		return
	ny = frappe.read_file(
		os.path.join(
			frappe.get_app_path("erpnext_sverige"),
			"sweden_compliance",
			"letter_head",
			"brevhuvud_sverige.html",
		)
	)
	frappe.db.set_value("Letter Head", LETTER_HEAD, "content", ny, update_modified=False)
