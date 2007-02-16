# Read AFNI .HEAD files.  The blocks are returned as a dict, using the
# block's name as a key.

import re, os.path, sys

class scanner:
	def __init__(self):
		pass

	def __call__(self, p, l):
		self.match = p.search(l)
		return self.match

	def group(self, x):
		return self.match.group(x)

def afni_header_read(filename):
	name = os.path.splitext(filename)[0]
	try:
		f = open("%s.HEAD" % name)
	except IOError:
		try:
			f = open("%s+orig.HEAD" % name)
		except IOError:
			print >> sys.stderr, "can't open %s" % filename
			sys.exit(1)

	search = scanner()

	p1 = re.compile(r"type  *= (?P<type>.*)")
	p2 = re.compile(r"name  *= (?P<name>.*)")
	p3 = re.compile(r"count  *= (?P<count>.*)")

	d = {}
	l = f.readline()
	while len(l) != 0:
		if search(p1, l):
			thd_type = search.group('type')
		if search(p2, l):
			thd_name = search.group('name')
		if search(p3, l):
			thd_count = int(search.group('count'))
			d[thd_name] = _decode_block(thd_type, thd_count, f)
		l = f.readline()
	return d

def _decode_block(thd_type, thd_count, f):
	if thd_type == 'string-attribute':
		s = f.read(thd_count + 1)
		if s[0] != "'" or len(s) != thd_count + 1:
			raise RuntimeError, "afni header string-attribute"
		s = s[1:].strip()
		return s.replace('\\n', '\n').split('~')[:-1]

	if thd_type == 'float-attribute':
		l = []
		while len(l) != thd_count:
			x = f.readline().strip().split()
			x = map(float, x)
			l.extend(x)
		return l

	if thd_type == 'integer-attribute':
		l = []
		while len(l) != thd_count:
			x = f.readline().strip().split()
			x = map(int, x)
			l.extend(x)
		return l
