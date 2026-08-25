import base64
import os
import re

import frappe
from frappe import _
from frappe.utils import cint, now_datetime


ROLE_NAME = "Sales Order Installer"
MAX_FILE_SIZE = 25 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "pdf", "jpg", "jpeg", "png", "webp",
    "doc", "docx", "xls", "xlsx", "csv", "txt",
}


def _require_installer_role():
    if frappe.session.user == "Administrator":
        return

    if ROLE_NAME not in frappe.get_roles(frappe.session.user):
        frappe.throw(
            _("You are not allowed to use Sales Order Installer."),
            frappe.PermissionError,
        )


def _validate_sales_order_name(sales_order_name):
    if not sales_order_name:
        frappe.throw(_("Sales Order is required."))

    sales_order_name = str(sales_order_name).strip()

    if not re.fullmatch(r'[^\\/:*?"<>|\r\n]+', sales_order_name):
        frappe.throw(_("Invalid Sales Order name."))

    if not frappe.db.exists("Sales Order", sales_order_name):
        frappe.throw(
            _("Sales Order {0} does not exist.").format(
                frappe.bold(sales_order_name)
            )
        )

    return sales_order_name


def _decode_file(file_name, filedata):
    if not file_name:
        frappe.throw(_("File name is required."))

    file_name = os.path.basename(str(file_name)).strip()
    if not file_name:
        frappe.throw(_("Invalid file name."))

    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if extension not in ALLOWED_EXTENSIONS:
        frappe.throw(
            _("File type .{0} is not allowed.").format(extension or "unknown")
        )

    if not filedata:
        frappe.throw(_("File data is empty."))

    try:
        content = base64.b64decode(filedata, validate=True)
    except Exception:
        frappe.throw(_("Invalid file data."))

    if len(content) > MAX_FILE_SIZE:
        frappe.throw(
            _("File {0} exceeds the maximum size of {1} MB.").format(
                file_name, MAX_FILE_SIZE // 1024 // 1024
            )
        )

    return file_name, content


@frappe.whitelist()
def get_sales_order_info(sales_order_name):
    _require_installer_role()
    sales_order_name = _validate_sales_order_name(sales_order_name)

    return {
        "name": sales_order_name,
        "customer": frappe.db.get_value(
            "Sales Order", sales_order_name, "customer"
        ),
        "status": frappe.db.get_value(
            "Sales Order", sales_order_name, "status"
        ),
        "installed_done": cint(
            frappe.db.get_value(
                "Sales Order", sales_order_name, "custom_installeddone_"
            )
        ),
    }


@frappe.whitelist()
def search_sales_orders(query=None, limit=8):
    _require_installer_role()

    query = (str(query or "").strip())
    if len(query) < 1:
        return []

    limit = max(1, min(cint(limit) or 8, 12))
    like_query = f"%{query}%"

    return frappe.db.sql(
        """
        select
            name,
            customer,
            status,
            coalesce(custom_installeddone_, 0) as installed_done,
            transaction_date
        from `tabSales Order`
        where name like %(query)s
            or customer like %(query)s
        order by
            case when name like %(starts_with)s then 0 else 1 end,
            modified desc
        limit %(limit)s
        """,
        {
            "query": like_query,
            "starts_with": f"{query}%",
            "limit": limit,
        },
        as_dict=True,
    )


@frappe.whitelist()
def upload_and_mark_installed(sales_order_name, files, upload_type="before"):
    _require_installer_role()
    sales_order_name = _validate_sales_order_name(sales_order_name)

    if isinstance(files, str):
        files = frappe.parse_json(files)

    if not isinstance(files, list) or not files:
        frappe.throw(_("Please select at least one file."))

    if len(files) > 10:
        frappe.throw(_("You can upload a maximum of 10 files at a time."))

    upload_type_map = {"before": "Before Installation", "after": "After Installation"}
    upload_type = upload_type_map.get(upload_type, upload_type)
    is_after = upload_type == "After Installation"
    if is_after:
        frappe.db.set_value(
            "Sales Order",
            sales_order_name,
            "custom_installeddone_",
            1,
            update_modified=True,
        )

    log = frappe.get_doc({
        "doctype": "Sales Order Installer Log",
        "sales_order": sales_order_name,
        "installer": frappe.session.user,
        "installed_at": now_datetime(),
        "files_count": len(files),
        "file_names": "\n".join(item.get("file_name", "") for item in files if item.get("file_name")),
        "upload_type": upload_type,
    })
    log.insert(ignore_permissions=True)

    created_files = []

    for item in files:
        if not isinstance(item, dict):
            frappe.throw(_("Invalid file payload."))

        file_name, content = _decode_file(
            item.get("file_name"),
            item.get("filedata"),
        )

        duplicate = frappe.db.exists("File", {
            "file_name": file_name,
            "attached_to_doctype": "Sales Order Installer Log",
            "attached_to_name": log.name,
        })

        if duplicate:
            frappe.throw(
                _("A file named {0} is already attached to Log {1}.")
                .format(file_name, log.name)
            )

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": file_name,
            "attached_to_doctype": "Sales Order Installer Log",
            "attached_to_name": log.name,
            "is_private": 1,
            "content": content,
        })

        file_doc.insert(ignore_permissions=True)

        created_files.append({
            "name": file_doc.name,
            "file_name": file_doc.file_name,
            "file_url": file_doc.file_url,
        })

    frappe.db.commit()

    return {
        "success": True,
        "sales_order": sales_order_name,
        "installed_done": 1 if is_after else 0,
        "files": created_files,
        "message": _("Sales Order updated successfully."),
    }


@frappe.whitelist()
def get_installation_preview(sales_order_name):
    _require_installer_role()
    sales_order_name = _validate_sales_order_name(sales_order_name)

    before_logs = frappe.get_all(
        "Sales Order Installer Log",
        filters={"sales_order": sales_order_name, "upload_type": "Before Installation"},
        fields=["name", "installer", "installed_at", "files_count"],
        order_by="installed_at asc"
    )

    after_logs = frappe.get_all(
        "Sales Order Installer Log",
        filters={"sales_order": sales_order_name, "upload_type": "After Installation"},
        fields=["name", "installer", "installed_at", "files_count"],
        order_by="installed_at asc"
    )

    def get_files_for_logs(logs):
        files = []
        for log in logs:
            log_files = frappe.get_all(
                "File",
                filters={"attached_to_doctype": "Sales Order Installer Log", "attached_to_name": log.name},
                fields=["file_url", "file_name", "creation"],
                order_by="creation asc"
            )
            for f in log_files:
                files.append({
                    "file_url": f.file_url,
                    "file_name": f.file_name,
                    "creation": f.creation,
                    "installer": log.installer
                })
        return files

    return {
        "before_files": get_files_for_logs(before_logs),
        "after_files": get_files_for_logs(after_logs),
        "before_logs": before_logs,
        "after_logs": after_logs
    }
