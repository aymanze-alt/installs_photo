import frappe

ROLE_NAME = "Sales Order Installer"
FIELDNAME = "custom_installeddone_"


def after_install():
    create_role()
    create_custom_field()


def after_migrate():
    create_role()
    create_custom_field()
    migrate_old_files()


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


def migrate_old_files():
    frappe.db.sql(
        """
        UPDATE `tabSales Order Installer Log`
        SET upload_type = 'After Installation'
        WHERE upload_type = 'Before Installation'
          AND creation < '2026-08-25'
        """
    )

    orders_with_files = frappe.db.sql(
        """
        SELECT attached_to_name as name
        FROM `tabFile`
        WHERE attached_to_doctype = 'Sales Order'
          AND file_name IS NOT NULL
        GROUP BY attached_to_name
        """,
        as_dict=True,
    )

    if not orders_with_files:
        return

    migrated = 0

    for order in orders_with_files:
        files = frappe.db.sql(
            """
            SELECT name, file_name, file_url, creation
            FROM `tabFile`
            WHERE attached_to_doctype = 'Sales Order'
              AND attached_to_name = %s
              AND file_name IS NOT NULL
            ORDER BY creation ASC
            """,
            (order.name,),
            as_dict=True,
        )

        if not files:
            continue

        existing_log = frappe.db.sql(
            """
            SELECT name FROM `tabSales Order Installer Log`
            WHERE sales_order = %s
            ORDER BY creation DESC LIMIT 1
            """,
            (order.name,),
            as_dict=True,
        )

        if existing_log:
            for f in files:
                frappe.db.set_value(
                    "File",
                    f.name,
                    {
                        "attached_to_doctype": "Sales Order Installer Log",
                        "attached_to_name": existing_log[0].name,
                    },
                )
            frappe.db.set_value(
                "Sales Order Installer Log",
                existing_log[0].name,
                "upload_type",
                "After Installation",
            )
            migrated += 1
            continue

        log = frappe.get_doc({
            "doctype": "Sales Order Installer Log",
            "sales_order": order.name,
            "installer": "Administrator",
            "installed_at": files[0].creation or frappe.utils.now_datetime(),
            "files_count": len(files),
            "file_names": "\n".join(f.file_name for f in files),
            "upload_type": "After Installation",
        })
        log.insert(ignore_permissions=True)

        for f in files:
            frappe.db.set_value(
                "File",
                f.name,
                {
                    "attached_to_doctype": "Sales Order Installer Log",
                    "attached_to_name": log.name,
                },
            )

        migrated += 1

    if migrated:
        frappe.db.commit()
