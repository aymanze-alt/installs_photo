# Monthly sales per sales person (quotation owner) for Sales Orders / Sales Invoices.
# The sales person is read from the custom field `custom_qout_ownar`; empty values
# are grouped under "غير محدد".

import json
from io import BytesIO

import frappe
from frappe.utils import cint, flt, getdate, nowdate

MONTHS = [
	"يناير", "فبراير", "مارس", "ابريل", "مايو", "يونيو",
	"يوليو", "اغسطس", "سبتمبر", "اكتوبر", "نوفمبر", "ديسمبر",
]
MONTH_KEYS = [f"m{i:02d}" for i in range(1, 13)]
UNSPECIFIED = "غير محدد"
OWNER_FIELD = "custom_qout_ownar"

DOC_TYPES = {
	"Sales Order": {"date": "transaction_date", "title": "إجمالي أوامر العمل الصادرة لعام {year}م"},
	"Sales Invoice": {"date": "posting_date", "title": "إجمالي الفواتير الصادرة لعام {year}م"},
}
AMOUNT_FIELDS = {
	"Grand Total": "base_grand_total",  # شامل الضريبة
	"Net Total": "base_net_total",  # قبل الضريبة
}
# Where the sales person comes from -> header label for the name column
SOURCE_LABELS = {
	"Quote Owner": "اسم المندوب",  # custom_qout_ownar
	"Sales Team": "اسم المندوب",  # Sales Team table (split by allocated %)
	"Created By": "المستخدم",  # document owner
}


def execute(filters=None):
	filters = _clean_filters(filters)
	rows = get_rows(filters)
	columns = get_columns(filters)

	grand_total = sum(r["total"] for r in rows)
	data = []
	for r in rows:
		r["percent"] = (r["total"] / grand_total * 100) if grand_total else 0
		data.append(r)

	if rows:
		total_row = {"code": "", "sales_person": "الإجمالي", "is_total_row": 1, "total": grand_total, "percent": 100 if grand_total else 0}
		percent_row = {"code": "", "sales_person": "النسبة المئوية", "is_percent_row": 1}
		for key in MONTH_KEYS:
			month_total = sum(r[key] for r in rows)
			total_row[key] = month_total
			percent_row[key] = (month_total / grand_total * 100) if grand_total else 0
		percent_row["total"] = 100 if grand_total else 0
		data += [total_row, percent_row]

	return columns, data


def _clean_filters(filters):
	if isinstance(filters, str):
		filters = json.loads(filters)
	filters = frappe._dict(filters or {})
	filters.year = cint(filters.year) or getdate(nowdate()).year
	if filters.document_type not in DOC_TYPES:
		filters.document_type = "Sales Invoice"
	if filters.amount_type not in AMOUNT_FIELDS:
		filters.amount_type = "Grand Total"
	filters.include_returns = cint(filters.get("include_returns", 1))
	if filters.sales_person_source not in SOURCE_LABELS:
		filters.sales_person_source = "Quote Owner"
	return filters


def get_columns(filters):
	columns = [
		{"fieldname": "code", "label": "الكود", "fieldtype": "Data", "width": 90},
		{"fieldname": "sales_person", "label": SOURCE_LABELS[filters.sales_person_source], "fieldtype": "Data", "width": 200},
	]
	for key, label in zip(MONTH_KEYS, MONTHS):
		columns.append({"fieldname": key, "label": label, "fieldtype": "Float", "precision": 0, "width": 110})
	columns += [
		{"fieldname": "total", "label": "إجمالي", "fieldtype": "Float", "precision": 0, "width": 130},
		{"fieldname": "percent", "label": "النسبة المئوية", "fieldtype": "Percent", "width": 110},
	]
	return columns


def get_rows(filters):
	doctype = filters.document_type
	date_field = DOC_TYPES[doctype]["date"]
	amount_field = AMOUNT_FIELDS[filters.amount_type]

	source = filters.sales_person_source
	if source == "Quote Owner" and not frappe.db.has_column(doctype, OWNER_FIELD):
		frappe.throw(f"الحقل {OWNER_FIELD} غير موجود في {doctype}")

	conditions = [f"d.docstatus = 1", f"d.`{date_field}` between %(from_date)s and %(to_date)s"]
	values = {
		"from_date": f"{filters.year}-01-01",
		"to_date": f"{filters.year}-12-31",
		"unspecified": UNSPECIFIED,
	}
	if filters.company:
		conditions.append("d.company = %(company)s")
		values["company"] = filters.company
	if doctype == "Sales Invoice" and not filters.include_returns:
		conditions.append("d.is_return = 0")

	where = " and ".join(conditions)
	month = f"month(d.`{date_field}`)"
	amount = f"d.`{amount_field}`"
	values["doctype"] = doctype

	if source == "Sales Team":
		# Split each document between its Sales Team rows by allocated %; any
		# unallocated remainder (or documents without a team) goes to "غير محدد".
		result = frappe.db.sql(
			f"""
			select st.sales_person as sales_person, {month} as month,
				sum({amount} * ifnull(st.allocated_percentage, 0) / 100) as amount
			from `tab{doctype}` d
			join `tabSales Team` st on st.parent = d.name and st.parenttype = %(doctype)s
			where {where}
			group by 1, 2
			union all
			select %(unspecified)s as sales_person, {month} as month,
				sum({amount} * (100 - ifnull(t.pct, 0)) / 100) as amount
			from `tab{doctype}` d
			left join (
				select parent, sum(allocated_percentage) as pct from `tabSales Team`
				where parenttype = %(doctype)s group by parent
			) t on t.parent = d.name
			where {where} and ifnull(t.pct, 0) < 100
			group by 1, 2
			""",
			values,
			as_dict=True,
		)
	elif source == "Created By":
		result = frappe.db.sql(
			f"""
			select coalesce(nullif(d.owner, ''), %(unspecified)s) as sales_person, {month} as month,
				sum({amount}) as amount
			from `tab{doctype}` d
			where {where}
			group by 1, 2
			""",
			values,
			as_dict=True,
		)
	else:
		result = frappe.db.sql(
			f"""
			select coalesce(nullif(trim(d.`{OWNER_FIELD}`), ''), %(unspecified)s) as sales_person,
				{month} as month, sum({amount}) as amount
			from `tab{doctype}` d
			where {where}
			group by 1, 2
			""",
			values,
			as_dict=True,
		)

	if source == "Created By":
		names = dict(frappe.get_all("User", fields=["name", "full_name"], as_list=True))
		codes = {
			user: emp
			for emp, user in frappe.get_all(
				"Employee", filters={"user_id": ["is", "set"]}, fields=["name", "user_id"], as_list=True
			)
		}
	else:
		names = {}
		codes = dict(frappe.get_all("Sales Person", fields=["name", "employee"], as_list=True))

	people = {}
	for row in result:
		if not row.month:
			continue
		person = people.setdefault(
			row.sales_person,
			{
				"code": codes.get(row.sales_person) or "",
				"sales_person": names.get(row.sales_person) or row.sales_person,
				**{k: 0.0 for k in MONTH_KEYS},
			},
		)
		person[MONTH_KEYS[cint(row.month) - 1]] += flt(row.amount)

	# drop zero rows (e.g. "غير محدد" when everything is fully allocated)
	people = {k: v for k, v in people.items() if any(abs(v[m]) > 0.005 for m in MONTH_KEYS)}

	rows = list(people.values())
	for r in rows:
		r["total"] = sum(r[k] for k in MONTH_KEYS)

	# Highest total first, "غير محدد" always last
	rows.sort(key=lambda r: (r["sales_person"] == UNSPECIFIED, -r["total"]))
	return rows


@frappe.whitelist()
def export_excel(filters=None):
	"""Excel export in the same layout as the manual yearly sheets."""
	filters = _clean_filters(filters)
	frappe.has_permission(filters.document_type, "read", throw=True)
	if not frappe.get_doc("Report", "Sales Person Monthly Sales").is_permitted():
		frappe.throw("ليس لديك صلاحية على هذا التقرير", frappe.PermissionError)
	rows = get_rows(filters)

	from openpyxl import Workbook
	from openpyxl.styles import Alignment, Border, Font, Side
	from openpyxl.utils import get_column_letter

	wb = Workbook()
	ws = wb.active
	ws.title = "شامل"
	ws.sheet_view.rightToLeft = True

	thin = Side(style="thin")
	border = Border(left=thin, right=thin, top=thin, bottom=thin)
	font = Font(name="Calibri", size=12)
	bold = Font(name="Calibri", size=12, bold=True)
	center = Alignment(horizontal="center", vertical="center")

	last_col = 2 + 12 + 2  # A..P
	total_col = get_column_letter(15)  # O
	pct_col = get_column_letter(16)  # P

	# Title (row 2, merged A2:P2)
	ws.row_dimensions[1].height = 6
	ws.row_dimensions[2].height = 21
	ws.row_dimensions[3].height = 6
	ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
	title = ws.cell(row=2, column=1, value=DOC_TYPES[filters.document_type]["title"].format(year=filters.year))
	title.font = Font(name="Calibri", size=14, bold=True)
	title.alignment = center

	# Header (row 4)
	headers = ["الكود", SOURCE_LABELS[filters.sales_person_source], *MONTHS, "إجمالي", "النسبة المئوية"]
	ws.row_dimensions[4].height = 27
	for col, label in enumerate(headers, start=1):
		c = ws.cell(row=4, column=col, value=label)
		c.font, c.alignment, c.border = bold, center, border

	first = 5
	last = first + len(rows) - 1
	total_row = last + 1
	pct_row = last + 2

	for i, r in enumerate(rows):
		row_no = first + i
		ws.row_dimensions[row_no].height = 27
		ws.cell(row=row_no, column=1, value=r["code"]).alignment = center
		ws.cell(row=row_no, column=2, value=r["sales_person"]).alignment = center
		for m, key in enumerate(MONTH_KEYS):
			value = round(r[key], 2)
			ws.cell(row=row_no, column=3 + m, value=value or None).number_format = "#,##0"
		ws.cell(row=row_no, column=15, value=f"=SUM(C{row_no}:N{row_no})").number_format = "#,##0"
		ws.cell(
			row=row_no, column=16, value=f"=IF(${total_col}${total_row}=0,0,{total_col}{row_no}/${total_col}${total_row})"
		).number_format = "0.00%"
		for col in range(1, last_col + 1):
			ws.cell(row=row_no, column=col).font = font
			ws.cell(row=row_no, column=col).border = border

	# Totals row
	ws.row_dimensions[total_row].height = 30
	ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=2)
	ws.cell(row=total_row, column=1, value="الأجمالي")
	for col in range(3, 16):
		letter = get_column_letter(col)
		ws.cell(row=total_row, column=col, value=f"=SUM({letter}{first}:{letter}{last})" if rows else 0).number_format = "#,##0"
	ws.cell(row=total_row, column=16, value=f"=SUM({pct_col}{first}:{pct_col}{last})" if rows else 0).number_format = "0.00%"

	# Percentage row
	ws.row_dimensions[pct_row].height = 30
	ws.merge_cells(start_row=pct_row, start_column=1, end_row=pct_row, end_column=2)
	ws.cell(row=pct_row, column=1, value="النسبة المئوية")
	for col in range(3, 15):
		letter = get_column_letter(col)
		ws.cell(
			row=pct_row, column=col, value=f"=IF(${total_col}${total_row}=0,0,{letter}{total_row}/${total_col}${total_row})"
		).number_format = "0.00%"
	ws.cell(row=pct_row, column=15, value=f"=SUM(C{pct_row}:N{pct_row})").number_format = "0.00%"

	for row_no in (total_row, pct_row):
		for col in range(1, last_col + 1):
			c = ws.cell(row=row_no, column=col)
			c.font, c.border = bold, border
		ws.cell(row=row_no, column=1).alignment = center

	widths = {"A": 12, "B": 30, "O": 15, "P": 14}
	for col in range(1, last_col + 1):
		letter = get_column_letter(col)
		ws.column_dimensions[letter].width = widths.get(letter, 13)

	ws.freeze_panes = "C5"
	ws.print_options.horizontalCentered = True
	ws.page_setup.orientation = "landscape"
	ws.page_setup.fitToWidth = 1
	ws.sheet_properties.pageSetUpPr.fitToPage = True

	out = BytesIO()
	wb.save(out)

	prefix = "اوامر عمل مبيعات" if filters.document_type == "Sales Order" else "فواتير مبيعات"
	frappe.response["filename"] = f"{prefix} عام {filters.year}م.xlsx"
	frappe.response["filecontent"] = out.getvalue()
	frappe.response["type"] = "binary"
