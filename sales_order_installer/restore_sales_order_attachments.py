import frappe

STALE_THRESHOLD_SECONDS = 60


def execute(dry_run=False):
    """Restore Sales Order attachments moved to Installer Log by the buggy
    migrate_old_files() migration, then delete the synthetic logs it created.

    The detection is based on relative timestamps in the live database (a file
    that predates its log by more than STALE_THRESHOLD_SECONDS was an existing
    Sales Order attachment moved by the migration), so it works regardless of
    how much newer the current data is than any backup.

    Pass dry_run=True to only show what would be restored without changing data.
    """

    moved_files = frappe.db.sql(
        """
        SELECT f.name AS file_doc, f.file_name AS file_name,
               log.sales_order, log.name AS log_name,
               f.creation AS file_creation, log.creation AS log_creation
        FROM `tabFile` f
        JOIN `tabSales Order Installer Log` log
          ON f.attached_to_name = log.name
         AND f.attached_to_doctype = 'Sales Order Installer Log'
        WHERE TIMESTAMPDIFF(SECOND, f.creation, log.creation) > %s
        """,
        (STALE_THRESHOLD_SECONDS,),
        as_dict=True,
    )

    restored = 0
    skipped = 0

    for f in moved_files:
        if not frappe.db.exists("Sales Order", f.sales_order):
            skipped += 1
            if not dry_run:
                continue
            print(f"  SKIP {f.file_doc} ({f.file_name}) -> missing SO {f.sales_order}")
            continue

        if dry_run:
            print(
                f"  would restore {f.file_doc} ({f.file_name}) "
                f"-> {f.sales_order} from log {f.log_name} "
                f"(file {f.file_creation} vs log {f.log_creation})"
            )
        else:
            frappe.db.set_value(
                "File",
                f.file_doc,
                {
                    "attached_to_doctype": "Sales Order",
                    "attached_to_name": f.sales_order,
                },
            )
        restored += 1

    deleted_logs = 0
    for log in frappe.get_all(
        "Sales Order Installer Log",
        filters={"installer": "Administrator"},
        pluck="name",
    ):
        count = frappe.db.count(
            "File",
            {
                "attached_to_doctype": "Sales Order Installer Log",
                "attached_to_name": log,
            },
        )
        if count:
            continue

        if dry_run:
            print(f"  would delete synthetic log {log}")
        else:
            frappe.db.delete("Sales Order Installer Log", log)
        deleted_logs += 1

    if not dry_run:
        frappe.db.commit()

    print(f"{'DRY RUN: ' if dry_run else ''}would restore/restored {restored} files to Sales Orders.")
    print(f"{'DRY RUN: ' if dry_run else ''}would skip/skipped {skipped} files with missing Sales Order.")
    print(f"{'DRY RUN: ' if dry_run else ''}would delete/deleted {deleted_logs} synthetic migration logs.")