frappe.pages["sales-order-installer"].on_page_load = function (wrapper) {
    new SalesOrderInstallerPage(wrapper);
};

class SalesOrderInstallerPage {
    constructor(wrapper) {
        this.wrapper = wrapper;
        this.selected_order = null;
        this.search_timer = null;
        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: __("Sales Order Installer"),
            single_column: true
        });

        this.make();
    }

    make() {
        const $main = $(this.page.main);

        $main.html(`
            <div class="sales-order-installer-page">
                <div class="sales-order-installer-shell">
                    <div class="sales-order-installer-header">
                        <div>
                            <div class="sales-order-installer-kicker">${__("Installation Proof")}</div>
                            <h3>${__("Sales Order Installer")}</h3>
                        </div>
                        <span class="sales-order-installer-limit">${__("10 files max")}</span>
                    </div>

                    <div class="sales-order-search-wrap">
                        <label class="control-label">${__("Sales Order")}</label>
                        <input type="text" class="form-control sales-order-name"
                            autocomplete="off"
                            placeholder="${__("Type order number or customer")}">
                        <div class="sales-order-search-state text-muted"></div>
                        <div class="sales-order-search-results hidden"></div>
                    </div>

                    <div class="sales-order-installer-status">
                        <div class="sales-order-empty">
                            ${__("Start typing to find the Sales Order.")}
                        </div>
                    </div>

                    <div class="sales-order-installer-files">
                        <label class="control-label">${__("Installation Photos")}</label>
                        <button class="sales-order-dropzone" type="button">
                            <span class="sales-order-dropzone-icon">
                                <svg viewBox="0 0 24 24" aria-hidden="true">
                                    <path d="M12 16V4m0 0 4 4m-4-4-4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>
                                </svg>
                            </span>
                            <span>
                                <strong>${__("Choose photos or files")}</strong>
                                <small>${__("JPG, PNG, PDF and documents up to 25 MB each")}</small>
                            </span>
                        </button>
                        <input type="file" class="sales-order-files" multiple accept=".jpg,.jpeg,.png,.pdf">
                        <div class="sales-order-file-list"></div>
                    </div>

                    <button class="btn btn-primary btn-upload">
                        ${__("Upload & Mark Installed")}
                    </button>

                    <div class="sales-order-installer-success"></div>
                </div>
            </div>
        `);

        this.$name = $main.find(".sales-order-name");
        this.$files = $main.find(".sales-order-files");
        this.$status = $main.find(".sales-order-installer-status");
        this.$success = $main.find(".sales-order-installer-success");
        this.$search_state = $main.find(".sales-order-search-state");
        this.$results = $main.find(".sales-order-search-results");
        this.$file_list = $main.find(".sales-order-file-list");
        this.$upload = $main.find(".btn-upload");
        this.selected_files = [];
        this.allowed_file_types = [
            "image/jpeg",
            "image/png",
            "application/pdf"
        ];
        this.allowed_file_extensions = [
            ".jpg",
            ".jpeg",
            ".png",
            ".pdf"
        ];

        this.$name.on("input", () => this.on_search_input());
        this.$name.on("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                this.search_sales_orders(true);
            }
        });
        $main.on("click", ".sales-order-search-item", (event) => {
            this.select_order($(event.currentTarget).data("name"));
        });
        $main.find(".sales-order-dropzone").on("click", () => this.$files.trigger("click"));
        this.$files.on("change", () => this.on_files_selected());
        $main.on("click", ".sales-order-file-remove", (event) => {
            const index = Number($(event.currentTarget).data("index"));
            this.remove_file(index);
        });
        $main.find(".btn-upload").on("click", () => this.upload());
        $(document).on("click.sales-order-installer", (event) => {
            if (!$(event.target).closest(".sales-order-search-wrap").length) {
                this.hide_results();
            }
        });
    }

    get_name() {
        return (this.$name.val() || "").trim();
    }

    on_search_input() {
        const name = this.get_name();
        this.selected_order = null;
        this.$success.empty();

        if (this.search_timer) {
            clearTimeout(this.search_timer);
        }

        if (name.length < 1) {
            this.hide_results();
            this.$search_state.empty();
            this.render_empty_state();
            return;
        }

        this.$search_state.text(__("Searching..."));
        this.search_timer = setTimeout(() => this.search_sales_orders(false), 250);
    }

    search_sales_orders(force_select) {
        const query = this.get_name();

        if (query.length < 1) {
            return;
        }

        frappe.call({
            method: "sales_order_installer.api.search_sales_orders",
            args: {query}
        }).then((r) => {
            const orders = r.message || [];
            this.$search_state.empty();

            if (force_select && orders.length === 1) {
                this.select_order(orders[0].name);
                return;
            }

            this.render_results(orders);
        }).catch(() => {
            this.$search_state.empty();
            this.hide_results();
        });
    }

    select_order(name) {
        this.hide_results();
        this.$search_state.text(__("Loading order..."));

        frappe.call({
            method: "sales_order_installer.api.get_sales_order_info",
            args: {sales_order_name: name}
        }).then((r) => {
            this.selected_order = r.message;
            this.$name.val(this.selected_order.name);
            this.$search_state.empty();
            this.render_order(this.selected_order);
        }).catch(() => {
            this.selected_order = null;
            this.$search_state.empty();
            this.render_empty_state();
        });
    }

    render_results(orders) {
        if (!orders.length) {
            this.$results
                .removeClass("hidden")
                .html(`<div class="sales-order-no-results">${__("No Sales Orders found.")}</div>`);
            return;
        }

        const html = orders.map((order) => {
            const installed = Number(order.installed_done || 0)
                ? `<span class="sales-order-pill is-done">${__("Installed")}</span>`
                : `<span class="sales-order-pill">${__("Open")}</span>`;

            return `
                <button class="sales-order-search-item" type="button"
                    data-name="${frappe.utils.escape_html(order.name)}">
                    <span>
                        <strong>${frappe.utils.escape_html(order.name)}</strong>
                        <small>${frappe.utils.escape_html(order.customer || "")}</small>
                    </span>
                    ${installed}
                </button>
            `;
        }).join("");

        this.$results.removeClass("hidden").html(html);
    }

    hide_results() {
        this.$results.addClass("hidden").empty();
    }

    render_empty_state() {
        this.$status.html(`
            <div class="sales-order-empty">
                ${__("Start typing to find the Sales Order.")}
            </div>
        `);
    }

    render_order(order) {
        const installed = Number(order.installed_done || 0)
            ? `<span class="sales-order-pill is-done">${__("Installed")}</span>`
            : `<span class="sales-order-pill">${__("Ready for proof")}</span>`;

        this.$status.html(`
            <div class="sales-order-selected">
                <div>
                    <div class="sales-order-label">${__("Selected Order")}</div>
                    <div class="sales-order-title">${frappe.utils.escape_html(order.name)}</div>
                    <div class="sales-order-meta">
                        ${frappe.utils.escape_html(order.customer || "")}
                        ${order.status ? ` - ${frappe.utils.escape_html(order.status)}` : ""}
                    </div>
                </div>
                ${installed}
            </div>
        `);
    }

    render_file_list() {
        const files = this.selected_files || [];

        if (!files.length) {
            this.$file_list.empty();
            return;
        }

        const html = files.map((file, index) => `
            <div class="sales-order-file-row">
                <span>${frappe.utils.escape_html(file.name)}</span>
                <small>${this.format_size(file.size)}</small>
                <button type="button" class="btn btn-secondary btn-xs sales-order-file-remove" data-index="${index}">
                    ${__("Remove")}
                </button>
            </div>
        `).join("");

        this.$file_list.html(html);
    }

    format_size(bytes) {
        if (bytes < 1024 * 1024) {
            return `${Math.max(1, Math.round(bytes / 1024))} KB`;
        }

        return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }

    is_valid_file(file) {
        const file_name = (file.name || "").toLowerCase();
        return this.allowed_file_types.includes(file.type) ||
            this.allowed_file_extensions.some((ext) => file_name.endsWith(ext));
    }

    on_files_selected() {
        const files = Array.from(this.$files[0].files || []);
        const allowed = [];
        const invalid_files = [];

        files.forEach((file) => {
            if (this.is_valid_file(file)) {
                allowed.push(file);
            } else {
                invalid_files.push(file.name);
            }
        });

        if (invalid_files.length) {
            frappe.msgprint(__(
                "Only JPG, PNG and PDF files are allowed. Removed: {0}",
                [invalid_files.join(", ")]
            ));
        }

        if (allowed.length > 10) {
            frappe.msgprint(__("You can upload a maximum of 10 files. Please choose fewer files."));
            allowed.splice(10);
        }

        this.selected_files = allowed;
        this.$files.val("");
        this.render_file_list();
    }

    remove_file(index) {
        if (index < 0 || index >= this.selected_files.length) {
            return;
        }

        this.selected_files.splice(index, 1);
        this.render_file_list();
    }

    read_file(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();

            reader.onload = () => {
                const result = reader.result || "";
                const comma = result.indexOf(",");
                if (comma === -1) {
                    reject(new Error(__("Could not read file.")));
                    return;
                }

                resolve({
                    file_name: file.name,
                    filedata: result.substring(comma + 1)
                });
            };

            reader.onerror = () => reject(new Error(__("Could not read file.")));
            reader.readAsDataURL(file);
        });
    }

    reset_form() {
        this.selected_order = null;
        this.selected_files = [];
        this.$files.val("");
        this.$name.val("");
        this.$search_state.empty();
        this.hide_results();
        this.render_empty_state();
        this.$file_list.empty();
    }

    async upload() {
        const name = this.selected_order ? this.selected_order.name : this.get_name();
        const files = this.selected_files || [];

        if (!name) {
            frappe.msgprint(__("Please enter a Sales Order."));
            return;
        }

        if (!files.length) {
            frappe.msgprint(__("Please select at least one file."));
            return;
        }

        if (files.length > 10) {
            frappe.msgprint(__("You can upload a maximum of 10 files."));
            return;
        }

        const maxSize = 25 * 1024 * 1024;
        const oversized = files.find(file => file.size > maxSize);

        if (oversized) {
            frappe.msgprint(__("File {0} is larger than 25 MB.", [oversized.name]));
            return;
        }

        this.$upload.prop("disabled", true).text(__("Uploading..."));
        frappe.dom.freeze(__("Uploading..."));

        try {
            const encodedFiles = [];
            for (const file of files) {
                encodedFiles.push(await this.read_file(file));
            }

            const r = await frappe.call({
                method: "sales_order_installer.api.upload_and_mark_installed",
                args: {
                    sales_order_name: name,
                    files: encodedFiles
                }
            });

            const d = r.message;

            this.$success.html(`
                <div class="sales-order-success">
                    <strong>${__("Uploaded successfully")}</strong>
                    <span>
                    ${frappe.utils.escape_html(d.message || "")}
                    </span>
                </div>
            `);

            this.reset_form();
        } finally {
            frappe.dom.unfreeze();
            this.$upload.prop("disabled", false).text(__("Upload & Mark Installed"));
        }
    }
}
