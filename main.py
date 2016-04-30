# vim: set noet ts=4 sw=4 fileencoding=utf-8:
from __future__ import unicode_literals

import re
import random
import hashlib
import datetime
from lxml import etree

from httplib import BAD_REQUEST
from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy

import patterns

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Message(db.Model):
	id = db.Column(db.Integer, primary_key=True, autoincrement=False, nullable=False)
	timestamp = db.Column(db.DateTime, default=datetime.datetime.now, nullable=False)

	def __init__(self, id):
		self.id = id

	def __repr(self):
		return '<Message %d at %s>' % (self.id, self.timestamp)

appPath = '/papuwx/' if __name__=='__main__' else '/'
@app.route(appPath, methods=['GET', 'POST'])
def index():
	for func in processes:
		result = func()
		if result is not None:
			return result
	return ''


processes = []
def process(func):
	processes.append(func)


@process
def authenticate():
	try:
		token = 'bigchord'
		s = ''.join(sorted([token, request.args['timestamp'], request.args['nonce']]))
		if hashlib.sha1(s).hexdigest() == request.args['signature']:
			return None
	except KeyError:
		pass
	abort(BAD_REQUEST)


@process
def checkEcho():
	if 'echostr' in request.args:
		return request.args['echostr']


@process
def processMessage():
	try: e = etree.fromstring(request.data)
	except etree.XMLSyntaxError: abort(BAD_REQUEST)

	if e.findtext('MsgType') not in ('text','voice'): return
	return processText(**{x:e.findtext(x) for x in
					   'ToUserName FromUserName CreateTime Content Recognition'.split()})


def randomEmoji():
	available = [(0x1f31a,0x1f31e), (0x1f646,0x1f64f)]
	pos = random.randrange(sum(x[1]-x[0]+1 for x in available))
	for x in available:
		if pos < x[1]-x[0]+1:
			return ('\\U%08x' % (x[0]+pos)).decode('unicode-escape')
		pos -= x[1]-x[0]+1

def processText(ToUserName, FromUserName, CreateTime, Content, Recognition):
	if Content is None: Content = Recognition
	Content = re.sub('[,，。!！?？]', '', Content.strip())
	if Content == '': return ''

	for function in processText.functions:
		replyText = function(FromUserName, Content)
		if replyText is not None: break
	else:
		replyText = randomEmoji()

	replyDict = dict(FromUserName=ToUserName,
					 ToUserName=FromUserName,
					 CreateTime=CreateTime,
					 MsgType='text',
					 Content=replyText)

	reply = etree.Element('xml')
	for k,v in replyDict.iteritems():
		element = etree.Element(k)
		element.text = v
		reply.append(element)

	x = etree.tostring(reply, encoding='utf8')
	print 'returning', x
	return x


def message(patternEntry):
	def decorate(func):
		def newFunc(userId, message):
			try:
				result = patternEntry(message)
				if result is None: return
				if result.__class__ in [tuple,list]:
					return func(userId, *result)
				else:
					return func(userId, result)
			except ValueError as e:
				return e.message
		processText.func_dict.setdefault('functions',[]).append(newFunc)
		return newFunc
	return decorate


@message(patterns.reservation)
def processReservation(userId, start, end):
	return 'reserving %s, %s, %s' % (userId, start, end)


@message(patterns.cancellation)
def processCancellation(userId, time):
	return 'cancelling %s, %s' % (userId, time)


@message(patterns.queryMyself)
def processQueryMyself(userId):
	return 'querying myself=%s' % userId

@message(patterns.query)
def processQuery(userId, start, end):
	return 'querying %s, %s, %s' % (userId, start, end)


if __name__=='__main__':
	db.create_all()
	#app.run(debug=True, host='::', port=80)
