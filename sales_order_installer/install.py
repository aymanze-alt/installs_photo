import frappe

ROLE_NAME = "Sales Order Installer"
FIELDNAME = "custom_installeddone_"


def after_install():
    create_role()
    create_custom_field()


def after_migrate():
    create_role()
    create_custom_field()


def create_role():
    if not frappe.db.exists("Role", ROLE_NAME):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": ROLE_NAME,
            "desk_access": 1,
            "is_custom": 1,
        }).insert(ignore_permissions=True)


def create_custom_field():
    if frappe.db.exists("Custom Field", {
        "dt": "Sales Order",
        "fieldname": FIELDNAME,
    }):
        return

    frappe.get_doc({
        "doctype": "Custom Field",
        "dt": "Sales Order",
        "fieldname": FIELDNAME,
        "label": "Installed Done",
        "fieldtype": "Check",
        "default": "0",
        "insert_after": "status",
        "description": "Set automatically by Sales Order Installer.",
    }).insert(ignore_permissions=True)

    frappe.clear_cache(doctype="Sales Order")
