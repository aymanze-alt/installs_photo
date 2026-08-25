frappe.ui.form.on('Sales Order', {
    refresh: function(frm) {
        if (!frm.doc) return;

        frm.add_custom_button(__('Installation Preview'), function() {
            open_installation_preview(frm.doc.name);
        }, __('View'));

        if (frm.doc.custom_installeddone_ === 1) {
            frm.dashboard.add_comment(__('Installation Completed ✓'), 'green', true);
        }
    }
});

function open_installation_preview(sales_order_name) {
    frappe.call({
        method: 'sales_order_installer.api.get_installation_preview',
        args: { sales_order_name: sales_order_name },
        callback: function(r) {
            if (r.message) {
                show_preview_dialog(sales_order_name, r.message);
            }
        }
    });
}

function show_preview_dialog(sales_order_name, data) {
    const { before_files, after_files, before_logs, after_logs } = data;

    let before_html = '';
    if (before_files.length) {
        before_html = before_files.map(f => `
            <div class="install-preview-card">
                <div class="install-preview-img-wrapper">
                    <img src="${f.file_url}" alt="${frappe.utils.escape_html(f.file_name)}" loading="lazy">
                    <span class="install-preview-badge before">${__('Before')}</span>
                </div>
                <div class="install-preview-details">
                    <div class="install-preview-title">${frappe.utils.escape_html(f.file_name)}</div>
                    <div class="install-preview-meta">
                        <span>${__('Uploaded by:')} ${frappe.utils.escape_html(f.installer || '')}</span>
                        <span>${frappe.datetime.str_to_user(f.creation)}</span>
                    </div>
                </div>
            </div>
        `).join('');
    } else {
        before_html = `
            <div class="install-preview-empty before">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
                    <circle cx="12" cy="13" r="4"></circle>
                </svg>
                <p>${__('No pre-installation photos uploaded')}</p>
            </div>
        `;
    }

    let after_html = '';
    if (after_files.length) {
        after_html = after_files.map(f => `
            <div class="install-preview-card">
                <div class="install-preview-img-wrapper">
                    <img src="${f.file_url}" alt="${frappe.utils.escape_html(f.file_name)}" loading="lazy">
                    <span class="install-preview-badge after">${__('After')}</span>
                </div>
                <div class="install-preview-details">
                    <div class="install-preview-title">${frappe.utils.escape_html(f.file_name)}</div>
                    <div class="install-preview-meta">
                        <span>${__('Uploaded by:')} ${frappe.utils.escape_html(f.installer || '')}</span>
                        <span>${frappe.datetime.str_to_user(f.creation)}</span>
                    </div>
                </div>
            </div>
        `).join('');
    } else {
        after_html = `
            <div class="install-preview-empty after">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                    <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
                <p>${__('No post-installation photos uploaded')}</p>
            </div>
        `;
    }

    const dialog = new frappe.ui.Dialog({
        title: `${__('Installation Preview')} - ${sales_order_name}`,
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'preview_html',
                options: `
                    <div class="install-preview-container">
                        <div class="install-preview-header">
                            <div class="install-preview-stats">
                                <div class="install-stat before">
                                    <span class="install-stat-count">${before_files.length}</span>
                                    <span class="install-stat-label">${__('Before Images')}</span>
                                </div>
                                <div class="install-stat after">
                                    <span class="install-stat-count">${after_files.length}</span>
                                    <span class="install-stat-label">${__('After Images')}</span>
                                </div>
                            </div>
                        </div>
                        <div class="install-preview-tabs">
                            <button class="install-tab-btn active" data-tab="before">${__('Before Installation')}</button>
                            <button class="install-tab-btn" data-tab="after">${__('After Installation')}</button>
                            <button class="install-tab-btn" data-tab="timeline">${__('Timeline')}</button>
                        </div>
                        <div class="install-preview-content">
                            <div class="install-tab-panel active" data-tab="before">
                                <div class="install-preview-grid">${before_html}</div>
                            </div>
                            <div class="install-tab-panel" data-tab="after">
                                <div class="install-preview-grid">${after_html}</div>
                            </div>
                            <div class="install-tab-panel" data-tab="timeline">
                                <div class="install-timeline">${render_timeline(before_logs, after_logs)}</div>
                            </div>
                        </div>
                    </div>
                `
            }
        ],
        primary_action_label: __('Close'),
        primary_action: function() {
            dialog.hide();
        }
    });

    dialog.show();

    // Tab switching
    dialog.$wrapper.find('.install-tab-btn').on('click', function() {
        const tab = $(this).data('tab');
        dialog.$wrapper.find('.install-tab-btn').removeClass('active');
        $(this).addClass('active');
        dialog.$wrapper.find('.install-tab-panel').removeClass('active');
        dialog.$wrapper.find(`.install-tab-panel[data-tab="${tab}"]`).addClass('active');
    });

    // Image click to enlarge
    dialog.$wrapper.find('.install-preview-card img').on('click', function() {
        const src = $(this).attr('src');
        const alt = $(this).attr('alt');
        show_image_modal(src, alt);
    });
}

function render_timeline(before_logs, after_logs) {
    const all_logs = [
        ...before_logs.map(l => ({ ...l, type: 'before' })),
        ...after_logs.map(l => ({ ...l, type: 'after' }))
    ].sort((a, b) => new Date(a.installed_at) - new Date(b.installed_at));

    if (!all_logs.length) {
        return `<div class="install-preview-empty"><p>${__('No installation activity yet')}</p></div>`;
    }

    return all_logs.map(log => `
        <div class="install-timeline-item ${log.type}">
            <div class="install-timeline-marker ${log.type}"></div>
            <div class="install-timeline-content">
                <div class="install-timeline-header">
                    <span class="install-timeline-type ${log.type}">
                        ${log.type === 'before' ? __('Before Installation') : __('After Installation')}
                    </span>
                    <span class="install-timeline-time">${frappe.datetime.str_to_user(log.installed_at)}</span>
                </div>
                <div class="install-timeline-installer">${__('By:')} ${frappe.utils.escape_html(log.installer)}</div>
                <div class="install-timeline-files">${log.files_count} ${__('file(s)')}</div>
            </div>
        </div>
    `).join('');
}

function show_image_modal(src, alt) {
    const modal = new frappe.ui.Dialog({
        title: alt,
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                options: `<img src="${src}" style="width:100%; max-height:70vh; object-fit:contain;">`
            }
        ],
        primary_action_label: __('Close'),
        primary_action: function() {
            modal.hide();
        }
    });
    modal.show();
}