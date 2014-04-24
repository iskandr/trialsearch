import xml
import argparse
import glob
from os.path import exists, isdir, join, split
import cgi
import xml.etree.ElementTree as ET
import requests
import subprocess

parser = argparse.ArgumentParser(description='Load clinicaltrials.gov XML files into solr search index')
parser.add_argument('path',  type=str, 
                   help='Filename(s) separated by commas (can include wildcards)')
parser.add_argument('--host', default='localhost', help='Solr host address')
parser.add_argument('--port',  default="8983", help='Solr host port')
parser.add_argument('--solr-command', default='solr/update')

args = parser.parse_args()

wildcard_paths = args.path.split(',')
filenames = []
for wildcard_path in wildcard_paths:
	for filename in glob.glob(wildcard_path):
		if isdir(filename):
			path = join(filename, '*.xml')
			filenames.extend(glob.glob(path))
		else:
			filename.append(filename)

class Doc(object):
	def __init__(self, filename):
		assert exists(filename), "File not found %s" % filename
		self.filename = filename
		xml_tree = ET.parse(filename)
		self.xml_root = xml_tree.getroot()
		self.fields = []

	def add(self, xpath, name = None):
		assert self.xml_root

		if name is None:
			name = split(xpath)[-1]
		field = self.xml_root.find(xpath)	
		assert field is not None, \
			"%s not found in XML document %s" % (xpath, self.filename)
		
		text = field.text
		print text
		self.fields.append( (name, text) )

	def add_multiple(self,  xpath, name):
		combined = ", ".join(field.text for field in self.xml_root.findall(xpath))
		self.fields.append( (name, combined) )

	def close(self):
		self.xml_root = None

	def __str__(self):
		escaped_pairs = [(name, cgi.escape(value.encode('ascii', 'ignore'))) for (name, value) in self.fields]

		field_strings = \
			["""<field name="{0}">{1}</field>""".format(name, value)
			 for name, value in escaped_pairs
			]
		joined = "\n\t".join(field_strings)
		return "<doc>\n\t{0}\n</doc>".format (joined)
		
# accumulate update query from a collection of XML files
docs = []
for filename in filenames:

	try:
		print "Processing", filename 
		doc = Doc(filename)
		doc.add('.//id_info/nct_id')
		doc.add('.//id_info/org_study_id', name="org_id")
		doc.add('.//required_header/url')
		doc.add('official_title', name = 'title')
		doc.add_multiple('.//agency', name = 'agency')
		doc.add('.//brief_summary/textblock', name='summary')
		doc.add('.//overall_status', name = 'status')
		doc.add('.//start_date')
		doc.add('.//completion_date')
		doc.add('.//eligibility/criteria/textblock', name = 'criteria')
		doc.add('.//gender')
		doc.add('.//minimum_age')
		doc.add('.//maximum_age')
		doc.close()
		docs.append(doc)
	except Exception as e:
		print e
		print "Skipping %s due to parsing error" % filename

query = "<add>\n%s\n</add>" % "\n".join(str(doc) for doc in docs)

import cStringIO
request_url = join('http://' + args.host + ":" + args.port, args.solr_command)
print "Request URL:", request_url
#headers = {'Content-Type' : 'text/xml'}
#r = requests.post(request_url, headers = headers, data = cStringIO.StringIO(query))
#r.raise_for_status()

shell_command = [
	"curl",
	request_url, 
	"-H", "\"Content-Type: text/xml\"",
	"--data-binary", "'%s'" % query 
]
shell_command_string = " ".join(shell_command)
import os 
os.system(shell_command_string)