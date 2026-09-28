frappe.ui.form.on("Bankgiro Inbetalning", {
	refresh(frm) {
		if (frm.is_new()) return;
		const call = (method, message) =>
			frm
				.call({ doc: frm.doc, method, freeze: true, freeze_message: message })
				.then(() => frm.reload_doc());

		const has_payments = (frm.doc.payments || []).some((row) => row.payment_entry);
		if (frm.doc.bgmax_file && !has_payments) {
			frm.add_custom_button(__("Läs in fil"), () =>
				call("read_file", __("Läser in och matchar …"))
			).addClass("btn-primary");
		}
		if ((frm.doc.payments || []).some((row) => row.sales_invoice && !row.payment_entry)) {
			frm.add_custom_button(__("Skapa betalningar för valda fakturor"), () =>
				call("create_payments", __("Skapar betalningar …"))
			);
		}
		if (has_payments && frm.doc.status !== "Bokförd") {
			frm.add_custom_button(__("Bokför betalningar"), () =>
				frappe.confirm(
					__("Bokför alla betalningar i utkastläge från den här filen?"),
					() => call("submit_payments", __("Bokför …"))
				)
			);
		}
	},
});
