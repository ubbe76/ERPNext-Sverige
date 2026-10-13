"""Tillägg till bootinfo."""

from frappe import _


def oversatt_dockan(bootinfo):
	"""Översätt dockans etiketter i Apps-läget.

	frappe 16.51 visar raderna med `row.title` utan `__()`, så "Leaves" och "Setup" står på engelska även för
	svenska användare. Titlarna är källsträngar som redan finns i katalogerna, så de översätts här.
	"""
	for rail in (bootinfo.get("dock") or {}).values():
		for rad in rail:
			if rad.get("title"):
				rad["title"] = _(rad["title"])
