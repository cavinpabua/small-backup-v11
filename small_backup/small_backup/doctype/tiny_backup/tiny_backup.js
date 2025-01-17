frappe.ui.form.on('Tiny Backup', {
	get_sizes: function (frm) {
		frappe.call({
			method: "get_table_sizes",
			doc: frm.doc,
			callback: function (r) {
				const data = r.message
				cur_frm.set_value('sizes', []);
				data.forEach((item) => {
					let row = frappe.model.add_child(frm.doc, "Table Sizes", "sizes");
					row.table_name = item['table_name'];
					row.size_in_mb = item['size_in_mb'];
				})
				cur_frm.refresh_fields("sizes");
			}
		});
	},
	generate_backup: function (frm) {
		const selected = cur_frm.doc.sizes.filter(item => item.__checked === 1).map(item => item.table_name);
		frappe.call({
			method: "generate_backup",
			doc: frm.doc,
			args: {
				selected
			},
			callback: function (r) {
				frappe.msgprint(r.message);
			}
		});
	}
});
