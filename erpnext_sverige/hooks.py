app_name = "erpnext_sverige"
app_title = "ERPNext Sverige"
app_publisher = "Urban Källefors"
app_description = "Swedish localization and manufacturing adaptations for ERPNext"
app_email = "erpnext@kallefors.se"
app_license = "gpl-3.0"

# Apps
# ------------------

required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "erpnext_sverige",
# 		"logo": "/assets/erpnext_sverige/logo.png",
# 		"title": "ERPNext Sverige",
# 		"route": "/erpnext_sverige",
# 		"has_permission": "erpnext_sverige.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/erpnext_sverige/css/erpnext_sverige.css"
# app_include_js = "/assets/erpnext_sverige/js/erpnext_sverige.js"

# include js, css files in header of web template
# web_include_css = "/assets/erpnext_sverige/css/erpnext_sverige.css"
# web_include_js = "/assets/erpnext_sverige/js/erpnext_sverige.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "erpnext_sverige/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Customer": "public/js/vies.js",
	"Supplier": "public/js/vies.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "erpnext_sverige/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [
		"erpnext_sverige.sweden_compliance.invoice.get_invoice_context",
		"erpnext_sverige.sweden_compliance.print_context.get_print_context",
	],
}

# Installation
# ------------

# before_install = "erpnext_sverige.install.before_install"
after_install = "erpnext_sverige.setup.custom_fields.create_custom_fields"
after_migrate = "erpnext_sverige.setup.custom_fields.create_custom_fields"

# Uninstallation
# ------------

# before_uninstall = "erpnext_sverige.uninstall.before_uninstall"
# after_uninstall = "erpnext_sverige.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "erpnext_sverige.utils.before_app_install"
# after_app_install = "erpnext_sverige.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "erpnext_sverige.utils.before_app_uninstall"
# after_app_uninstall = "erpnext_sverige.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "erpnext_sverige.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erpnext_sverige.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["erpnext_sverige.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Company": {
		"validate": "erpnext_sverige.sweden_compliance.invoice.satt_momsregnr",
	},
	"Sales Invoice": {
		"validate": [
			"erpnext_sverige.accounting.account_selection.set_accounts_by_tax_category",
			"erpnext_sverige.sweden_compliance.invoice.set_ocr",
			"erpnext_sverige.sweden_compliance.invoice_number.rensa_utkast",
		],
		"before_submit": [
			"erpnext_sverige.sweden_compliance.tax_category.validate_invoice_vat_number",
			"erpnext_sverige.sweden_compliance.invoice_number.set_fakturanummer",
		],
	},
	"Address": {
		"validate": "erpnext_sverige.sweden_compliance.tax_category.set_address_tax_category",
		"on_update": "erpnext_sverige.sweden_compliance.tax_category.propagate_address_tax_category",
	},
	"Customer": {
		"validate": "erpnext_sverige.sweden_compliance.tax_category.set_party_tax_category",
		"on_update": "erpnext_sverige.sweden_compliance.tax_category.update_addresses_on_customer_type_change",
	},
	"Supplier": {
		"validate": "erpnext_sverige.sweden_compliance.tax_category.set_party_tax_category",
	},
	"Purchase Invoice": {
		"validate": "erpnext_sverige.accounting.account_selection.set_accounts_by_tax_category",
	},
	"File": {
		"validate": "erpnext_sverige.sweden_compliance.bilagor.skydda_mot_flytt",
		"on_trash": "erpnext_sverige.sweden_compliance.bilagor.skydda_mot_radering",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"erpnext_sverige.tasks.all"
# 	],
# 	"daily": [
# 		"erpnext_sverige.tasks.daily"
# 	],
# 	"hourly": [
# 		"erpnext_sverige.tasks.hourly"
# 	],
# 	"weekly": [
# 		"erpnext_sverige.tasks.weekly"
# 	],
# 	"monthly": [
# 		"erpnext_sverige.tasks.monthly"
# 	],
# }

# Testing
# -------

before_tests = "erpnext_sverige.tests.utils.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "erpnext_sverige.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "erpnext_sverige.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "erpnext_sverige.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["erpnext_sverige.utils.before_request"]
# after_request = ["erpnext_sverige.utils.after_request"]

# Job Events
# ----------
# before_job = ["erpnext_sverige.utils.before_job"]
# after_job = ["erpnext_sverige.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"erpnext_sverige.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
