# CRS reports scraper.

import sys
import re
import os
import os.path
import datetime
import time
import json
import hashlib
import base64
import sqlite3

import scrapelib
import dropbox

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

def run_in_background():
	def MessageBox(message, buttons=0):
		from ctypes import windll
		return windll.user32.MessageBoxW(0, message, "CRS Reports Scraper", buttons)

	# Ask the user if they want to start the scraper in the background?
	if MessageBox("Would you like to start the background CRS reports scraper?", buttons=4) != 6:
		MessageBox("Okay, program stopping.")
		return

	try:

		# Periodically run the scraper in the background around 6pm.
		while True:
			# Is it close to 6pm?
			if datetime.datetime.now().hour != 18:
				# Pause and check again.
				wait_time = datetime.timedelta(minutes=23)
				time.sleep(wait_time.total_seconds())
				continue

			# Run the scraper once.
			MessageBox("Scraping!")
			run_scraper()

			# Delay 12 hours to make sure we don't scrape more than once
			# on the same day. Then start waiting again until it's the
			# right time for another scrape.
			wait_time = datetime.timedelta(hours=12)
			time.sleep(wait_time.total_seconds())
			continue

	except Exception as e:
		MessageBox("The CRS scraper ran into an error and is terminating: " + str(e))
		raise

def run_scraper():
	# Loop through the pages of the listing of CRS reports.
	pageNumber = 1
	while True:
		print("Fetching page", pageNumber, "...")
		had_stuff = fetch_from_json_listing(pageNumber)
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

def fetch_from_json_listing(pageNumber):
	if "--test" not in sys.argv:
		# Requests one of the CRS JSON URLs that lists documents.
		url = "http://www.crs.gov/search/results?term=orderBy=Date&navIds=4294952831&navIds=4294938681&pageNumber=%d" \
			% pageNumber
		body = scraper.get(url).content
		documents = json.loads(body.decode("utf8"))
	else:
		# Use test data from a file on disk.
		documents = json.load(open(os.path.join("test", "SearchResults_%d.json" % pageNumber)))

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
		if "--test" not in sys.argv:
			# Construct full URL.
			file_url = "http://crs.gov/" + file["Url"]

			# Fetch content.
			print(file_url, '...')
			response = scraper.get(file_url)
			file_url = response.url
			file_content = response.content
			file_encoding = response.encoding
			file_headers = dict(response.headers)

		else:
			# Load test data.
			file_url = "file://local/path"
			file_content = open(os.path.join("test", file["Url"]), "rb").read()
			file_encoding = "unknown"
			file_headers = { }

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
			"encoding": file_encoding,
			"url": file_url,
			"headers": file_headers,
			"sha1": sha1(file_content),
			"filename": file_filename,
			"images": { },
		}

		# Save the file to disk and add it to our database so we know we don't
		# need to fetch it again.
		save_file(file_filename, file_content)

		# Scan HTML documents for images and fetch those too.
		if file["FormatType"] == "HTML":
			for img in re.findall(b'src="(/products/Getimages/\?directory=[^"]+&id=/[^"]+\.png)"', file_content):
				img = img.decode("ascii")
				
				# Fetch and save the image, and add a mapping in the
				# metadata from CRS.gov image paths to the filename
				# we stored it in.
				if "--test" not in sys.argv:
					image_url = "http://crs.gov" + img
					print(image_url, '...')
					response = scraper.get(image_url)
					image_content = response.content
				else:
					# Load test data.
					image_content = b"someinvalidrawdata"

				image_filename = \
					"files/" \
					+ "_".join([
						crs_report_date,
						document['ProductNumber'],
						"images",
						sha1(image_content)
					]) \
					+ ".png"
				file["_"]["images"][img] = image_filename
				save_file(image_filename, image_content)


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
	print(">", filename)

	if not dropbox_client:
		# Save the file. Make a directory for it if the directory doesn't exist.
		os.makedirs(os.path.dirname(filename), exist_ok=True)
		with open(filename, "wb") as f:
			f.write(payload)
	else:
		# Upload to Dropbox.
		dropbox_client.files_upload(payload, dropbox_root_path + '/' + filename)

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

# Initialize the database on first use.
create_db_tables()

# Load Dropbox auth from dropbox_access_token.txt, which should look
# like:
#  TOKEN={generate an access token from the app page}
#  PATH=/name
# If the app has permission to upload to an app directory only, the
# uploads will be put in Apps\CRS-Scraper-Uploads\name.
dropbox_client = None
dropbox_root_path = None
if os.path.exists("dropbox_access_token.txt"):
	dropbox_authz = dict(line.strip().split("=",1) for line in open("dropbox_access_token.txt") if line.strip())
	dropbox_client = dropbox.Dropbox(dropbox_authz["TOKEN"])
	dropbox_user = dropbox_client.users_get_current_account()
	dropbox_root_path = dropbox_authz["PATH"]
	print("Uploading to Dropbox account", dropbox_user.name.display_name, dropbox_user.email, "at", dropbox_root_path)

if not sys.stdin is None:
	# We're running on a console.
	run_scraper()
else:
	# We're running inside pythonw without a console.
	run_in_background()
