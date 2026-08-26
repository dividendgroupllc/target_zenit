app_name = "target_zenit"
app_title = "target_zenit"
app_publisher = "Munisa"
app_description = "target_zenit"
app_email = "munisabax2002@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "target_zenit",
# 		"logo": "/assets/target_zenit/logo.png",
# 		"title": "target_zenit",
# 		"route": "/target_zenit",
# 		"has_permission": "target_zenit.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/target_zenit/css/target_zenit.css"
# ?v= — brauzer keshini yangilash uchun (fayl o'zgarganda raqamni oshiring)
app_include_js = [
	"/assets/target_zenit/js/instagram.js?v=20260825",
	"/assets/target_zenit/js/report_formatter.js?v=20260825",
	"/assets/target_zenit/js/pl_pdf_button.js?v=20260825",
	"/assets/target_zenit/js/balance_sheet_pdf.js?v=20260825",
]

# include js, css files in header of web template
# web_include_css = "/assets/target_zenit/css/target_zenit.css"
# web_include_js = "/assets/target_zenit/js/target_zenit.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "target_zenit/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "target_zenit/public/icons.svg"

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

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "target_zenit.utils.jinja_methods",
# 	"filters": "target_zenit.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "target_zenit.install.before_install"
# after_install = "target_zenit.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "target_zenit.uninstall.before_uninstall"
# after_uninstall = "target_zenit.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "target_zenit.utils.before_app_install"
# after_app_install = "target_zenit.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "target_zenit.utils.before_app_uninstall"
# after_app_uninstall = "target_zenit.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "target_zenit.notifications.get_notification_config"

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

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# Chart of Accounts o'zgarsa — Kassa'dagi "Тип контрагента" ro'yxatidagi
# xarajat papkalari yangilanadi.
doc_events = {
	"Account": {
		"after_insert": "target_zenit.setup.kassa_party_types.on_account_change",
		"on_update": "target_zenit.setup.kassa_party_types.on_account_change",
		"on_trash": "target_zenit.setup.kassa_party_types.on_account_change",
	}
}

after_migrate = ["target_zenit.setup.kassa_party_types.after_migrate"]

# Scheduled Tasks
# ---------------

scheduler_events = {
	"hourly": [
		"target_zenit.integrations.eduvisit.hourly_attendance"
	],
	"daily": [
		"target_zenit.integrations.eduvisit.daily_sync"
	],
}

# scheduler_events = {
# 	"all": [
# 		"target_zenit.tasks.all"
# 	],
# 	"daily": [
# 		"target_zenit.tasks.daily"
# 	],
# 	"hourly": [
# 		"target_zenit.tasks.hourly"
# 	],
# 	"weekly": [
# 		"target_zenit.tasks.weekly"
# 	],
# 	"monthly": [
# 		"target_zenit.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "target_zenit.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "target_zenit.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "target_zenit.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["target_zenit.utils.before_request"]
# after_request = ["target_zenit.utils.after_request"]

# Job Events
# ----------
# before_job = ["target_zenit.utils.before_job"]
# after_job = ["target_zenit.utils.after_job"]

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
# 	"target_zenit.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["name", "in", ["Contact-is_billing_contact", "Student-custom_hikvision_id", "Student-custom_eduvisit_id", "Guardian-custom_eduvisit_id", "Student-custom_shartnoma_qilindi"]]
        ]
    },
    {
        "dt": "Property Setter",
        "filters": [
            ["name", "in", ["Student-student_email_id-reqd"]]
        ]
    }
]
