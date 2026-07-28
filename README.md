# Sales Order Installer

ERPNext/Frappe v15 custom app for a controlled workflow where users with the
`Sales Order Installer` role can attach files to a Sales Order and set
`custom_installeddone_` to checked, without receiving normal Sales Order
read/write permission.

## Install

```bash
cd ~/frappe-bench
bench get-app /path/to/sales_order_installer
bench --site your-site install-app sales_order_installer
bench --site your-site migrate
bench build
bench restart
```

Assign the `Sales Order Installer` role to the required users.

Open:

`/app/sales-order-installer`

The app automatically creates the `Sales Order` custom field
`custom_installeddone_` if it does not already exist.

## Security

The backend checks the role on every API request. It intentionally uses
controlled `ignore_permissions=True` only for the File and audit-log records,
and changes only the requested Sales Order custom field.

Allowed attachments: PDF, images, Office documents, CSV and TXT.
Maximum: 25 MB per file, 10 files per request.
