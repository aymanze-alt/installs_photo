// Monthly sales per sales person (quotation owner)

(function () {
	const current_year = new Date().getFullYear();
	const years = [];
	for (let y = current_year + 1; y >= 2024; y--) years.push(String(y));

	frappe.query_reports["Sales Person Monthly Sales"] = {
		filters: [
			{
				fieldname: "document_type",
				label: "نوع المستند",
				fieldtype: "Select",
				options: [
					{ value: "Sales Invoice", label: "فواتير المبيعات" },
					{ value: "Sales Order", label: "أوامر العمل (أوامر البيع)" },
				],
				default: "Sales Invoice",
				reqd: 1,
			},
			{
				fieldname: "sales_person_source",
				label: "تحديد المندوب حسب",
				fieldtype: "Select",
				options: [
					{ value: "Quote Owner", label: "حقل qout ownar" },
					{ value: "Sales Team", label: "فريق المبيعات (Sales Team)" },
					{ value: "Created By", label: "المستخدم الذي أنشأ المستند" },
				],
				default: "Quote Owner",
				reqd: 1,
			},
			{
				fieldname: "year",
				label: "السنة",
				fieldtype: "Select",
				options: years,
				default: String(current_year),
				reqd: 1,
			},
			{
				fieldname: "company",
				label: "الشركة",
				fieldtype: "Link",
				options: "Company",
				default: frappe.defaults.get_user_default("Company"),
			},
			{
				fieldname: "amount_type",
				label: "المبلغ",
				fieldtype: "Select",
				options: [
					{ value: "Grand Total", label: "الإجمالي شامل الضريبة" },
					{ value: "Net Total", label: "الصافي قبل الضريبة" },
				],
				default: "Grand Total",
				reqd: 1,
			},
			{
				fieldname: "include_returns",
				label: "خصم المرتجعات (للفواتير)",
				fieldtype: "Check",
				default: 1,
			},
		],

		formatter(value, row, column, data, default_formatter) {
			if (data && data.is_percent_row && !["code", "sales_person", "percent"].includes(column.fieldname)) {
				return value === undefined || value === null || value === ""
					? ""
					: `<b>${flt(value, 2).toFixed(2)}%</b>`;
			}
			value = default_formatter(value, row, column, data);
			if (data && (data.is_total_row || data.is_percent_row)) {
				value = `<b>${value}</b>`;
			}
			return value;
		},

		onload(report) {
			report.page.add_inner_button("تصدير Excel", () => {
				const filters = report.get_values();
				if (!filters) return;
				open_url_post(
					"/api/method/sales_order_installer.sales_order_installer.report.sales_person_monthly_sales.sales_person_monthly_sales.export_excel",
					{ filters: JSON.stringify(filters) }
				);
			});
		},
	};
})();
