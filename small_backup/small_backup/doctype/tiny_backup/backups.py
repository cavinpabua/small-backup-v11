from __future__ import unicode_literals, print_function
from frappe import _
import os, frappe
from datetime import datetime
from frappe.utils import cstr, now_datetime
import shlex

verbose = 0
from frappe import conf
class BackupGenerator:
	def __init__(self, db_name, user, password, backup_path_db=None, backup_path_files=None,
		backup_path_private_files=None, db_host="localhost", excluded_tables=None):
		self.db_host = db_host
		self.db_name = db_name
		self.user = user
		self.password = password
		self.backup_path_files = backup_path_files
		self.backup_path_db = backup_path_db
		self.backup_path_private_files = backup_path_private_files
		self.excluded_tables = excluded_tables

	def get_backup(self, older_than=24, ignore_files=False, force=False):
		if not force:
			last_db, last_file, last_private_file = self.get_recent_backup(older_than)
		else:
			last_db, last_file, last_private_file = False, False, False

		if not (self.backup_path_files and self.backup_path_db and self.backup_path_private_files):
			self.set_backup_file_name()

		if not (last_db and last_file and last_private_file):
			self.take_dump()
			if not ignore_files:
				self.zip_files()

		else:
			self.backup_path_files = last_file
			self.backup_path_db = last_db
			self.backup_path_private_files = last_private_file

	def set_backup_file_name(self):
		todays_date = now_datetime().strftime('%Y%m%d_%H%M%S')
		site = frappe.local.site or frappe.generate_hash(length=8)
		site = site.replace('.', '_')

		#Generate a random name using today's date and a 8 digit random number
		for_db = todays_date + "-" + site + "-database.sql.gz"
		for_public_files = todays_date + "-" + site + "-files.tar"
		for_private_files = todays_date + "-" + site + "-private-files.tar"
		backup_path = get_backup_path()

		if not self.backup_path_db:
			self.backup_path_db = os.path.join(backup_path, for_db)
		if not self.backup_path_files:
			self.backup_path_files = os.path.join(backup_path, for_public_files)
		if not self.backup_path_private_files:
			self.backup_path_private_files = os.path.join(backup_path, for_private_files)

	def get_recent_backup(self, older_than):
		file_list = os.listdir(get_backup_path())
		backup_path_files = None
		backup_path_db = None
		backup_path_private_files = None

		for this_file in file_list:
			this_file = cstr(this_file)
			this_file_path = os.path.join(get_backup_path(), this_file)
			if not is_file_old(this_file_path, older_than):
				if "_private_files" in this_file_path:
					backup_path_private_files = this_file_path
				elif "_files" in this_file_path:
					backup_path_files = this_file_path
				elif "_database" in this_file_path:
					backup_path_db = this_file_path

		return (backup_path_db, backup_path_files, backup_path_private_files)

	def zip_files(self):
		for folder in ("public", "private"):
			files_path = frappe.get_site_path(folder, "files")
			backup_path = self.backup_path_files if folder=="public" else self.backup_path_private_files

			cmd_string = """tar -cf %s %s""" % (backup_path, files_path)
			err, out = frappe.utils.execute_in_shell(cmd_string)

			print('Backed up files', os.path.abspath(backup_path))

	def take_dump(self):
		import frappe.utils
		args = dict(
			[
				(item[0], frappe.utils.esc(item[1], '$ ') if not isinstance(item[1], list) else ','.join(item[1]))
				for item in self.__dict__.copy().items()
			]
		)


		ignore_query = ""
		if self.excluded_tables:
			ignore_query = " ".join(
				"--ignore-table=" + self.db_name + "." + (f"{shlex.quote(table)}" if " " in table else shlex.quote(table)) + " "
				for table in self.excluded_tables
			)

		excluded_query = ""
		if self.excluded_tables:
			excluded_query = " ".join(
				"--no-data " + (f"{shlex.quote(table)}" if " " in table else shlex.quote(table)) + " "
				for table in self.excluded_tables
			)

		cmd_ignore = f"""mysqldump --single-transaction --quick --lock-tables=false --max_allowed_packet=512M \
    -u {args['user']} -p{args['password']} {args['db_name']} -h {args['db_host']} {ignore_query} | gzip > {args['backup_path_db']}"""
		
		frappe.utils.execute_in_shell(cmd_ignore)

		cmd_exclude = f"""mysqldump --single-transaction --quick --lock-tables=false --max_allowed_packet=512M \
	-u {args['user']} -p{args['password']} {args['db_name']} -h {args['db_host']} {excluded_query} | gzip >> {args['backup_path_db']}"""
		
		frappe.utils.execute_in_shell(cmd_exclude)

		print("Backup completed.")
		
		

@frappe.whitelist()
def get_backup():
	delete_temp_backups()
	odb = BackupGenerator(frappe.conf.db_name, frappe.conf.db_name,\
						  frappe.conf.db_password, db_host = frappe.db.host)
	odb.get_backup()

def scheduled_backup(older_than=6, ignore_files=False, backup_path_db=None, backup_path_files=None, backup_path_private_files=None, force=False, excluded_tables=None):
	odb = new_backup(older_than, ignore_files, backup_path_db=backup_path_db, backup_path_files=backup_path_files, force=force, excluded_tables=excluded_tables)
	return odb

def new_backup(older_than=6, ignore_files=False, backup_path_db=None, backup_path_files=None, backup_path_private_files=None, force=False, excluded_tables=None):
	delete_temp_backups(older_than = frappe.conf.keep_backups_for_hours or 24)
	odb = BackupGenerator(frappe.conf.db_name, frappe.conf.db_name,\
						  frappe.conf.db_password,
						  backup_path_db=backup_path_db, backup_path_files=backup_path_files,
						  backup_path_private_files=backup_path_private_files,
						  db_host = frappe.db.host, excluded_tables=excluded_tables)
	odb.get_backup(older_than, ignore_files, force=force)
	return odb

def delete_temp_backups(older_than=24):
	backup_path = get_backup_path()
	if os.path.exists(backup_path):
		file_list = os.listdir(get_backup_path())
		for this_file in file_list:
			this_file_path = os.path.join(get_backup_path(), this_file)
			if is_file_old(this_file_path, older_than):
				os.remove(this_file_path)

def is_file_old(db_file_name, older_than=24):
		if os.path.isfile(db_file_name):
			from datetime import timedelta
			#Get timestamp of the file
			file_datetime = datetime.fromtimestamp\
						(os.stat(db_file_name).st_ctime)
			if datetime.today() - file_datetime >= timedelta(hours = older_than):
				if verbose: print("File is old")
				return True
			else:
				if verbose: print("File is recent")
				return False
		else:
			if verbose: print("File does not exist")
			return True

def get_backup_path():
	backup_path = frappe.utils.get_site_path(conf.get("backup_path", "private/backups"))
	return backup_path


def backup(with_files=False, backup_path_db=None, backup_path_files=None, quiet=False, excluded_tables=None):
	"Backup"
	odb = scheduled_backup(ignore_files=not with_files, backup_path_db=backup_path_db, backup_path_files=backup_path_files, force=True, excluded_tables=excluded_tables)
	return {
		"backup_path_db": odb.backup_path_db,
		"backup_path_files": odb.backup_path_files,
		"backup_path_private_files": odb.backup_path_private_files
	}

