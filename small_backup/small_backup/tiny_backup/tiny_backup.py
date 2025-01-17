from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from tiny_backup.tiny_backup.doctype.tiny_backup.backups import backup

class TinyBackup(Document):
	@frappe.whitelist()
	def get_table_sizes(self):
		tables = frappe.db.sql("""
			SELECT  
				table_name,
				ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS size_in_mb
			FROM 
				information_schema.tables
			GROUP BY 
				table_schema, table_name
			ORDER BY 
				size_in_mb DESC
			LIMIT 20

		""", as_dict=1)

		return tables
	
	@frappe.whitelist()
	def generate_backup(self, selected):
		print(selected)
		enqueue(self.enqueue_backup,queue='long', selected=selected)
		# self.enqueue_backup(selected)
		return "Backup generated successfully"
	
	def enqueue_backup(self, selected):
		backup(with_files=True, excluded_tables=selected)
