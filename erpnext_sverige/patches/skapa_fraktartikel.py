"""Skapar fraktartikeln "Frakt" och pekar ut den i Fraktinställningar (ersätter fraktkontot)."""

from erpnext_sverige.setup.custom_fields import create_custom_fields


def execute():
	# after_migrate (som skapar custom fields) körs efter patcharna, men artikeln behöver se_goods_or_service.
	# create_custom_fields skapar fälten och anropar sedan sakerstall_fraktartikel, så patchen räcker med det anropet.
	create_custom_fields()
