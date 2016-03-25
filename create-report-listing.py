# Takes any already-downloaded metadata files and generates a static HTML
# page listing all of the available reports.
#
# There might be more than one metadata record for the same product, because
# we save a new metadata record each time it changes. Collect all of the
# metadata records and combine them by product.

import glob
import json
from collections import defaultdict
import cgi
import datetime

# Collect by report.
reports = defaultdict(lambda : [])

# Look through all of the metadata records and combine by report.
for fn in glob.glob("documents/*.json"):
	# Parse JSON.
	with open(fn) as f:
		doc = json.load(f)

	# Parse the CoverDate.
	doc['CoverDate'] = datetime.datetime.strptime(doc['CoverDate'], "%Y-%m-%dT%H:%M:%S")

	# Store by product.
	reports[doc['PrdsProdId']].append(doc)

# For each report, sort the metadata records in reverse-chronological order.
for report in reports.values():
	report.sort(key = lambda record : record['CoverDate'], reverse=True)

# Sort the documents in reverse chronological order by most recent
# publication date (the first metadata record, since the arrays have
# already been sorted).
reports = list(reports.values())
reports.sort(key = lambda records : records[0]['CoverDate'], reverse=True)

def truncate_summary(text):
	words = text.split(" ")
	ret = ""
	while len(words) > 0 and len(ret)+len(words[0]) <= 600:
		ret += " " + words.pop(0)
	ret = ret[1:] # take out initial space
	if len(words) > 0:
		ret += "..."
	return ret

# Output a static HTML listing.
with open("index.html", "w") as f:
	f.write("<html><head><title>Congressional Research Service Reports</title></head><body>\n")
	f.write("<h1>Congressional Research Service Reports</h1>\n")
	for report in reports:
		metadata = report[0]
		f.write("<h2>" + cgi.escape(metadata['Title'].strip()) + "</h2>\n")
		for record in report:
			f.write("<p><span class='date'>" + cgi.escape(metadata['CoverDate'].strftime("%x")) + "</span>: \n")
			for fmt in sorted(record['FormatList'], key=lambda fmt : fmt['FormatType']):
				f.write(" <a class='format' href=%s>%s</a> " % (fmt['_']['filename'], fmt['FormatType']))
			f.write(" &mdash; ")
			f.write(cgi.escape(truncate_summary(metadata['Summary'])) + "\n")
			f.write("</p>\n")


	f.write("</body></html>")
