# CRS reports scraper.

import re
import os
import os.path
import datetime
import json
import hashlib
import base64
import sqlite3

import scrapelib

# Create a scraper that automatically throttles our requests
# so that we don't overload the CRS server.
scraper = scrapelib.Scraper(
	requests_per_minute=20,
	retry_attempts=2,
	retry_wait_seconds=10)

# Open our local database that remembers what we've already
# fetched & uploaded so that we don't repeatedly fetch the
# same thing.
db = sqlite3.connect('crs_scraper_database.db')

#####################################################################

def main():
	# Initialize the database on first use.
	create_db_tables()

	# Loop through the pages of the listing of CRS reports.
	pageNumber = 1
	while True:
		print("Fetching page", pageNumber, "...")
		had_stuff = fetch_from_json_listing("http://www.crs.gov/search/results?term=orderBy=Date&navids=4294952831&pageNumber=%d" % pageNumber)
		if had_stuff:
			pageNumber += 1
			continue
		else:
			break

#####################################################################

def create_db_tables():
	# Create database tables on first run. Ignore errors about
	# tables already existing if this isn't first run.
	c = db.cursor()
	for table_name, table_def in [
		("fetched", "filename text, fetch_date datetime, content_hash text")
	]:
		try:
			c.execute("CREATE TABLE %s (%s)" % (table_name, table_def))
			print("Initialized database table '%s'." % table_name)
		except sqlite3.OperationalError as e:
			if ("table %s already exists" % table_name) not in str(e):
				raise e
	db.commit()

def fetch_from_json_listing(url):
	# Requests one of the CRS JSON URLs that lists documents.
	body = scraper.get(url).content
	documents = json.loads(body.decode("utf8"))

	# process each document
	for doc in documents["SearchResults"]:
		fetch_document(doc)

	# If this JSON file had any reports, return True. If we got back an
	# empty list, then this was the last page of results, so return False.
	return len(documents["SearchResults"]) > 0

def fetch_document(document):
	# Fetch a "document". Each document is composed of one or more files.
	# We'll treat the metadata record itself as a file, and then each
	# file mentioned in its FormatList is another file.

	# Create a filename for the metadata. We'll use the CoverDate and SHA1
	# of the JSON to form a unique filename that changes whenever the
	# metadata changes. Ensure that weird data in CRS fields doesn't
	# create invalid filenames for us by sanitizing the fields.
	crs_product_id = re.sub(r"[^A-Za-z0-9]", "", document['ProductNumber'])
	crs_report_date = re.sub(r"\D", "", document['CoverDate'])[0:8]
	metadata_filename = \
		"documents/" \
		+ "_".join([
			crs_report_date,
			crs_product_id,
			sha1(json.dumps(document, sort_keys=True).encode("utf8"))
		]) \
		+ ".json"

	# Don't bother fetching files that are very old. We already have
	# these.
	if crs_report_date < "201604":
		return False

	# If we've already seen this, then we're done.
	if has_gotten_file(metadata_filename):
		print("Already got", metadata_filename)
		return False

	# Add some stuff to the metadata.
	document["_fetched"] = datetime.datetime.utcnow().isoformat() # UTC

	# Fetch the files mentioned in the metadata and augment the metadata
	# with the SHA1 of each file.
	for file in document["FormatList"]:
		# Construct full URL.
		file_url = "http://crs.gov/" + file["Url"]

		# Fetch content.
		print(file_url, '...')
		response = scraper.get(file_url)
		file_content = response.content

		# Assign it a filename using the document's cover date, the document's
		# product identifier, the SHA1 hash of the file's content, and the
		# file's type as a file extension (for convenience).
		file_filename = \
			"files/" \
			+ "_".join([
				crs_report_date,
				document['ProductNumber'],
				sha1(file_content)
			]) \
			+ { "PDF": ".pdf", "HTML": ".html" }.get(file["FormatType"], "")

		# Add file metadata to the document.
		file["_"] = {
			"encoding": response.encoding,
			"url": response.url,
			"headers": dict(response.headers),
			"sha1": sha1(file_content),
			"filename": file_filename,
		}

		# Save the file to disk and add it to our database so we know we don't
		# need to fetch it again.
		save_file(file_filename, file_content)


	# Save the metadata record as a file as well, and that's how we'll know what
	# PDF/HTML file corresponds with what report.
	save_file(
		metadata_filename,
		json.dumps(document, indent=2).encode("utf8"))

	return True

def sha1(stuff):
	h = hashlib.sha1()
	h.update(stuff)
	return h.hexdigest()

def has_gotten_file(filename):
	# Returns the content_hash stored in our database of the named file.
	# If the file isn't in our database, returns None.
	cur = db.cursor()
	cur.execute("SELECT content_hash FROM fetched WHERE filename = ?", (filename,))
	r = cur.fetchone()
	if r:
		r = r[0]
	return r

def save_file(filename, payload):
	# Save the file. Make a directory for it if the directory doesn't exist.
	os.makedirs(os.path.dirname(filename), exist_ok=True)
	with open(filename, "wb") as f:
		f.write(payload)

	# Record the file in our database. Cleear an existing record in case
	# we're saving a file with a changed hash (although that'd be strange
	# since the hash is in the filename).
	content_hash = sha1(payload)
	cur = db.cursor()
	cur.execute("DELETE FROM fetched WHERE content_hash = ?", (content_hash,))
	cur.execute("INSERT INTO fetched values (?, ?, ?)", (
		filename,
		datetime.datetime.utcnow(),
		content_hash,
	))
	db.commit()

#####################################################################

main()
