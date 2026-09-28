frappe.ui.form.on("Leverantorsbetalning", {
	setup(frm) {
		frm.set_query("bank_account", () => ({
			filters: { company: frm.doc.company, is_company_account: 1 },
		}));
		frm.set_query("purchase_invoice", "invoices", () => ({
			filters: { company: frm.doc.company, docstatus: 1, outstanding_amount: [">", 0] },
		}));
	},

	refresh(frm) {
		if (frm.is_new()) return;
		const call = (method, message) =>
			frm
				.call({ doc: frm.doc, method, freeze: true, freeze_message: message })
				.then(() => frm.reload_doc());

		if (frm.doc.status === "Utkast") {
			frm.add_custom_button(__("Hämta förfallna fakturor"), () =>
				call("get_due_invoices", __("Hämtar fakturor …"))
			);
			frm.add_custom_button(__("Skapa betalfil"), () =>
				call("create_payment_file", __("Skapar betalfil …"))
			).addClass("btn-primary");
		}
		if (frm.doc.payment_file) {
			frm.add_custom_button(__("Ladda ner betalfil"), () =>
				window.open(frm.doc.payment_file)
			);
		}
		if (frm.doc.status === "Fil skapad") {
			frm.add_custom_button(__("Bokför betalningar"), () =>
				frappe.confirm(
					__(
						"Har banken genomfört betalningarna? De bokförs med betalningsdagen som datum."
					),
					() => call("submit_payments", __("Bokför …"))
				)
			);
		}
	},
});
