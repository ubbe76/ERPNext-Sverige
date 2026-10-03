// Förval: senaste avslutade redovisningsperioden enligt bolagets inställning. Datumen sätts utan
// uppdatering, sedan uppdateras rapporten en gång, även när perioden är densamma som för förra bolaget.
function satt_period(report) {
	const company = report.get_filter_value("company");
	if (!company) return;
	frappe
		.call({
			method: "erpnext_sverige.sweden_compliance.vat_return.standardperiod",
			args: { company },
		})
		.then(
			(r) => {
				if (!r.message) return report.refresh();
				report._no_refresh = true;
				return Promise.all([
					report.get_filter("from_date").set_value(r.message.from_date),
					report.get_filter("to_date").set_value(r.message.to_date),
				]).finally(() => {
					report._no_refresh = false;
					report.refresh();
				});
			},
			// Felet visas redan; rapporten ska ändå visa det valda bolaget
			() => report.refresh()
		);
}

// Filen hämtas i bakgrunden och sparas, i stället för i en ny flik: en ny flik med en nedladdning blir kvar
// tom och ser ut att ladda i vissa webbläsare. Fel (t.ex. fel period) visas som vanliga meddelanden.
function ladda_ner_eskd(args) {
	const url = "/api/method/erpnext_sverige.sweden_compliance.vat_return.download_eskd";
	frappe.dom.freeze();
	fetch(`${url}?${new URLSearchParams(args)}`, {
		headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
	})
		.then(async (r) => {
			if (!r.ok) {
				const svar = await r.json().catch(() => ({}));
				const meddelanden = JSON.parse(svar._server_messages || "[]").map(
					(m) => JSON.parse(m).message
				);
				frappe.msgprint({
					message: meddelanden.join("<br>") || __("Filen kunde inte skapas"),
					indicator: "red",
				});
				return;
			}
			const namn =
				(r.headers.get("Content-Disposition") || "").match(/filename=([^;]+)/)?.[1] ||
				"momsdeklaration.xml";
			const lank = document.createElement("a");
			lank.href = URL.createObjectURL(await r.blob());
			lank.download = namn;
			document.body.appendChild(lank);
			lank.click();
			lank.remove();
			setTimeout(() => URL.revokeObjectURL(lank.href), 10000);
		})
		.catch(() =>
			frappe.msgprint({ message: __("Ingen kontakt med servern"), indicator: "red" })
		)
		.finally(() => frappe.dom.unfreeze());
}

frappe.query_reports["Momsdeklaration"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			// on_change ersätter rapportens egen uppdatering; satt_period uppdaterar när datumen är satta
			on_change: (report) => satt_period(report),
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
		satt_period(report);

		const args = () => ({
			company: report.get_filter_value("company"),
			from_date: report.get_filter_value("from_date"),
			to_date: report.get_filter_value("to_date"),
		});

		report.page.add_inner_button(__("Ladda ner eSKD-fil"), () => ladda_ner_eskd(args()));

		report.page.add_inner_button(__("Skapa momsomföring"), () => {
			frappe.call({
				method: "erpnext_sverige.sweden_compliance.vat_return.create_vat_settlement",
				args: args(),
				freeze: true,
				callback: (r) => r.message && frappe.set_route("Form", "Journal Entry", r.message),
			});
		});

		report.page.add_inner_button(__("Lås perioden"), () => {
			const { company, to_date } = args();
			frappe.confirm(
				__(
					"Bokföringen för {0} låses till och med {1}. Därefter går det inte att bokföra, ändra eller makulera något med datum till och med {1}. Lås när momsdeklarationen är inlämnad och momsomföringen bokförd. Fortsätta?",
					[company, frappe.datetime.str_to_user(to_date)]
				),
				() =>
					frappe.call({
						method: "erpnext_sverige.sweden_compliance.period_lock.las_period",
						args: { company, to_date },
						freeze: true,
						callback: (r) => r.message && frappe.msgprint(r.message),
					})
			);
		});
	},
};
