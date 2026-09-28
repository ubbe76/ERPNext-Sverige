frappe.query_reports["SIE-export"] = {
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
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today()),
			reqd: 1,
		},
	],

	onload(report) {
		report.page.add_inner_button(__("Ladda ner SIE-fil"), () => {
			const args = {
				company: report.get_filter_value("company"),
				fiscal_year: report.get_filter_value("fiscal_year"),
			};
			const url = "/api/method/erpnext_sverige.sweden_compliance.sie_export.download_sie";
			window.open(`${url}?${new URLSearchParams(args)}`);
		});
	},
};
