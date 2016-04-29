# vim: set noet ts=4 sw=4 fileencoding=utf-8:
from __future__ import unicode_literals

from flask import Flask, request
app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
	return 'asdf'

if __name__=='__main__':
	app.run(host='::', port=8080)
