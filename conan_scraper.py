# http://www.crs.gov/conan/constitutionannotated scraper.

import sys
import re
import os
import os.path
import datetime
import time
import json
import hashlib
import base64
from urllib.parse import quote

import scrapelib
import dropbox

# Create a scraper that automatically throttles our requests
# so that we don't overload the CRS server.
scraper = scrapelib.Scraper(
	requests_per_minute=20,
	retry_attempts=2,
	retry_wait_seconds=10)


#####################################################################

def run_in_background():
	def MessageBox(message, buttons=0):
		from ctypes import windll
		return windll.user32.MessageBoxW(0, message, "CONAN Scraper", buttons)

	# Ask the user if they want to start the scraper in the background?
	if MessageBox("Would you like to start the background CONAN scraper?", buttons=4) != 6:
		MessageBox("Okay, program stopping.")
		return

	try:

		# Periodically run the scraper in the background around 6pm.
		while True:
			# Is it close to 8pm on a Tuesday?
			if datetime.datetime.now().hour != 20 or datetime.datetime.now().weekday() != 2:
				# Pause and check again.
				wait_time = datetime.timedelta(minutes=23)
				time.sleep(wait_time.total_seconds())
				continue

			# Run the scraper once.
			run_scraper()

			# Delay 12 hours to make sure we don't scrape more than once
			# on the same day. Then start waiting again until it's the
			# right time for another scrape.
			wait_time = datetime.timedelta(hours=12)
			time.sleep(wait_time.total_seconds())
			continue

	except Exception as e:
		MessageBox("The COAN scraper ran into an error and is terminating: " + str(e))
		raise

def run_scraper():
	# Scrape the top-level file.
	scrape_page("constitutionannotated", set())

def scrape_page(path, already_scraped):
	if path in already_scraped: return
	already_scraped.add(path)

	fn = "conan/" + quote(path.replace("/", "_")) + ".html"

	if not os.path.exists(fn) or dropbox_client:
		url = "http://www.crs.gov/conan/" + path
		print(url + "...")
		content = scraper.get(url).content
		save_file(fn, content)
	else:
		with open(fn, "rb") as f:
			content = f.read()
	
	for link in re.findall(b"href=\"/conan/((?:index|details)/.*?)\">", content):
		link = link.decode("utf8").replace("&amp;", "&")
		link = re.sub(r"#.*", "", link)
		scrape_page(link, already_scraped)

#####################################################################


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



#####################################################################

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
	dropbox_root_path = dropbox_authz["PATH"] + "-conan"
	print("Uploading to Dropbox account", dropbox_user.name.display_name, dropbox_user.email, "at", dropbox_root_path)

if not sys.stdin is None:
	# We're running on a console.
	run_scraper()
else:
	# We're running inside pythonw without a console.
	run_in_background()
