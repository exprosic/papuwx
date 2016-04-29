# vim: set noet ts=4 sw=4 fileencoding=utf-8:
from __future__ import unicode_literals

import re
import random
import hashlib
import datetime
from lxml import etree

from httplib import BAD_REQUEST
from flask import Flask, request, abort

app = Flask(__name__)
appPath = '/papuwx/' if __name__=='__main__' else '/'
print appPath

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

def processText(ToUserName, FromUserName, CreateTime, Content, Recognition):
	if Content is None:
		Content = Recognition
	Content = re.sub('[,，。!！?？]', '', Content.strip())

	replyDict = dict(FromUserName=ToUserName,
					 ToUserName=FromUserName,
					 CreateTime=CreateTime,
					 MsgType='text',
					 Content='myreply')

	reply = etree.Element('xml')
	for k,v in replyDict.iteritems():
		element = etree.Element(k)
		element.text = v
		reply.append(element)

	x = etree.tostring(reply, encoding='utf8')
	print 'returning', x
	return x

if __name__=='__main__':
	app.run(debug=True, host='::', port=80)
