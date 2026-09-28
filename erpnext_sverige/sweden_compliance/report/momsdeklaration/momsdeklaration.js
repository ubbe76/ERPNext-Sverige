frappe.query_reports["Momsdeklaration"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[1],
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[2],
			reqd: 1,
		},
	],

	onload(report) {
		const args = () => ({
			company: report.get_filter_value("company"),
			from_date: report.get_filter_value("from_date"),
			to_date: report.get_filter_value("to_date"),
		});

		report.page.add_inner_button(__("Ladda ner eSKD-fil"), () => {
			const url = "/api/method/erpnext_sverige.sweden_compliance.vat_return.download_eskd";
			window.open(`${url}?${new URLSearchParams(args())}`);
		});

		report.page.add_inner_button(__("Skapa momsomföring"), () => {
			frappe.call({
				method: "erpnext_sverige.sweden_compliance.vat_return.create_vat_settlement",
				args: args(),
				freeze: true,
				callback: (r) => r.message && frappe.set_route("Form", "Journal Entry", r.message),
			});
		});
	},
};
