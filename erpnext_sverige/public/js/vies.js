// Knapp "Kontrollera i VIES" på kund och leverantör: frågar EU:s register om momsregistreringsnumret är giltigt.
const erpnext_sverige_vies = {
	refresh(frm) {
		if (!frm.doc.tax_id || frm.is_new()) return;
		frm.add_custom_button(__("Kontrollera i VIES"), () => {
			frappe.call({
				method: "erpnext_sverige.sweden_compliance.tax_category.check_vies",
				args: { vat_number: frm.doc.tax_id },
				freeze: true,
				freeze_message: __("Frågar VIES …"),
				callback: ({ message: r }) => {
					if (r.valid === true) {
						frappe.msgprint({
							title: __("Giltigt momsregistreringsnummer"),
							indicator: "green",
							message: [r.vat_number, r.name, r.address]
								.filter(Boolean)
								.map((line) => frappe.utils.escape_html(line))
								.join("<br>"),
						});
					} else if (r.valid === false) {
						frappe.msgprint({
							title: __("Ogiltigt momsregistreringsnummer"),
							indicator: "red",
							message:
								r.error || __("VIES känner inte till numret {0}.", [r.vat_number]),
						});
					} else {
						frappe.msgprint({
							title: __("VIES"),
							indicator: "orange",
							message: r.error,
						});
					}
				},
			});
		});
	},
};

frappe.ui.form.on("Customer", erpnext_sverige_vies);
frappe.ui.form.on("Supplier", erpnext_sverige_vies);
