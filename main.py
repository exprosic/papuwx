# vim: set noet ts=4 sw=4 fileencoding=utf-8:
from __future__ import unicode_literals

import os
import sys
import re
import random
import hashlib
import datetime
import sqlite3
from lxml import etree

from httplib import BAD_REQUEST
from flask import Flask, request, abort, g
from flask_sqlalchemy import SQLAlchemy
#from flask.ext.script import Manager
from sqlalchemy.exc import IntegrityError

import patterns

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PROPAGATE_EXCEPTIONS'] = True

wxToken = 'bigchord'
db = SQLAlchemy(app)

class Message(db.Model):
	'timestamp 用来实现定期清除'
	msgId = db.Column(db.Integer(), primary_key=True, autoincrement=False)
	timestamp = db.Column(db.DateTime(), default=datetime.datetime.now, nullable=False)
	def __repr__(self):
		return '<Message {} at {}>'.format(self.msgId, self.timestamp).encode('utf8')


class User(db.Model):
	id = db.Column(db.Integer(), primary_key=True)
	openId = db.Column(db.String(), unique=True, nullable=True) #null一般为手动录入但没登记的老师
	name = db.Column(db.String(), nullable=False)
	def __repr__(self):
		return '<User {} {}>'.format(self.openId, self.name).encode('utf8')


class Registration(db.Model):
	id = db.Column(db.Integer(), primary_key=True)
	openId = db.Column(db.String(), unique=True, nullable=False)
	name = db.Column(db.String(), nullable=False)
	def __repr__(self):
		return '<Registration {} {}>'.format(self.openId, self.name).encode('utf8')


class Room(db.Model):
	id = db.Column(db.Integer(), primary_key=True)
	name = db.Column(db.String(collation='NOCASE'), unique=True, nullable=False)
	def __repr__(self):
		return '<Room {}>'.format(self.name).encode('utf8')


class Reservation(db.Model):
	id = db.Column(db.Integer(), primary_key=True)
	userId = db.Column(db.Integer(), db.ForeignKey('user.id'), nullable=False)
	user = db.relationship('User', backref=db.backref('reservations', lazy='dynamic'))
	roomId = db.Column(db.Integer(), db.ForeignKey('room.id'), nullable=False)
	room = db.relation('Room', backref=db.backref('reservations', lazy='dynamic'))
	start = db.Column(db.DateTime(), nullable=False)
	end = db.Column(db.DateTime(), nullable=False)
	def __repr__(self):
		return '{} {}'.format(self.user.name, self.getDateRoom()).encode('utf8')

	def getDateRoom(self):
		return '{}年{}月{}日 {}:{:02}~{}:{:02} {}'.format(
				self.start.year, self.start.month, self.start.day,
				self.start.hour, self.start.minute,
				self.end.hour, self.end.minute,
				self.room.name)


class Course(db.Model):
	id = db.Column(db.Integer(), primary_key=True)
	teacherId = db.Column(db.Integer(), db.ForeignKey('user.id'), nullable=False)
	teacher = db.relation('User', backref=db.backref('courses', lazy='dynamic'))
	roomId = db.Column(db.Integer(), db.ForeignKey('room.id'), nullable=False)
	room = db.relation('Room', backref=db.backref('courses', lazy='dynamic'))
	weekday = db.Column(db.Integer(), nullable=False)
	startDate = db.Column(db.Date(), nullable=False)
	endDate = db.Column(db.Date(), nullable=False)
	startTime = db.Column(db.Time(), nullable=False)
	endTime = db.Column(db.Time(), nullable=False)
	def __repr__(self):
		return '<Course {} {}月{}日~{}月{}日 {} {}:{:02}~{}:{:02}>'.format(
				self.teacher.name,
				self.startDate.month, self.startDate.day,
				self.endDate.month, self.endDate.day,
				'周一 周二 周三 周四 周五 周六 周日'.split()[self.weekday],
				self.startTime.hour, self.startTime.minute,
				self.endTime.hour, self.endTime.minute).encode('utf8')


class Show(db.Model):
	id = db.Column(db.Integer(), primary_key=True)
	performerId = db.Column(db.Integer(), db.ForeignKey('user.id'), nullable=False)
	performer = db.relation('User', backref=db.backref('shows', lazy='dynamic'))
	def __repr__(self):
		return '<Show {}>'.format(self.performer).encode('utf8')


appPath = '/papuwx/' if __name__=='__main__' else '/'
@app.route(appPath, methods=['GET', 'POST'])
def index():
	print request
	for func in processes:
		result = func()
		if result is not None:
			return result
	return ''


processes = []
def process(func):
	processes.append(func)


@process
def authenticateMessage():
	'验证是否是从微信服务器发来的请求'
	try:
		s = ''.join(sorted([wxToken, request.args['timestamp'], request.args['nonce']]))
		if hashlib.sha1(s).hexdigest() == request.args['signature']:
			#succeeded, pass through
			return None
	except KeyError:
		pass
	abort(BAD_REQUEST)


@process
def checkEcho():
	'响应微信公众号配置页面发起的验证服务器请求'
	if 'echostr' in request.args:
		return request.args['echostr']


@process
def processMessage():
	try: e = etree.fromstring(request.data)
	except etree.XMLSyntaxError: abort(BAD_REQUEST)

	try:
		db.session.add(Message(msgId=int(e.findtext('MsgId'))))
		db.session.commit()
	except IntegrityError:
		#消息已处理，或者不存在MsgId
		return ''

	if e.findtext('MsgType') not in ('text','voice'):
		return

	return processText(**{x:e.findtext(x) for x in
					   'ToUserName FromUserName CreateTime Content Recognition'.split()})


def randomEmoji():
	available = [(0x1f31a,0x1f31e), (0x1f646,0x1f64f)]
	pos = random.randrange(sum(x[1]-x[0]+1 for x in available))
	for x in available:
		if pos < x[1]-x[0]+1:
			return '\\U{:08x}'.format(x[0]+pos).decode('unicode-escape')
		pos -= x[1]-x[0]+1


def processText(ToUserName, FromUserName, CreateTime, Content, Recognition):
	if Content is None: Content = Recognition
	Content = re.sub('[,，。!！?？]', '', Content.strip())
	if Content == '': return ''

	g.openId = FromUserName

	try:
		for function in processText.functions:
			replyText = function(Content)
			if replyText is not None: break
		else:
			replyText = randomEmoji()
	except MyException as e:
		if e.message=='': return ''
		replyText = e.message

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
	return x


def message(patternEntry):
	def decorate(func):
		def newFunc(message):
			try:
				result = patternEntry(message)
				if result is None: return
				if result.__class__ in [tuple,list]:
					return func(*result)
				else:
					return func(result)
			except ValueError as e:
				return e.message
		processText.func_dict.setdefault('functions',[]).append(newFunc)
		return newFunc
	return decorate


class MyException(Exception):
	pass


def authenticated(func):
	def newFunc(*args, **kwargs):
		user = User.query.filter_by(openId=g.openId).first()
		if user is None:
			raise MyException('抱歉，您还没有登记。请发送 我是xxx')
		g.user = user
		return func(*args, **kwargs)
	return newFunc


def overlayedReservation(start, end, room=None):
	query = Reservation.query if room is None else room.reservations
	return query.filter(db.or_(
		db.and_(Reservation.start<start, Reservation.end>start), # ( [ )
		db.and_(Reservation.start>=start, Reservation.start<end)) # [ ( ]
	)


def overlayedCourse(start, end):
	end -= datetime.timedelta(microseconds=1)
	assert start.date() == end.date()

	return (Course.query.filter_by(weekday=start.weekday())
			.filter(db.and_(Course.startDate<=start.date(),
				Course.endDate>=start.date()))
			.filter(db.or_(
				db.and_(Course.startTime<start.time(), Course.endTime>start.time()),
				db.and_(Course.startTime>=start.time(), Course.startTime<=end.time()))))


def queryExist(query):
	return len(query[:1]) > 0


@message(patterns.iAm)
def processRegistration(name):
	user = User.query.filter_by(openId=g.openId).first()
	if user is not None:
		if user.name == name:
			return '您已设置姓名为 {}'.format(name)
		return '您已设置姓名为 {}，不可更改'.format(user.name)

	registration = Registration.query.filter_by(openId=g.openId).first()
	if registration is None:
		db.session.add(Registration(openId=g.openId, name=name))
		db.session.commit()
		return '请再输入一次。请注意，一旦设置后不可更改。'
	elif registration.name != name:
		db.session.delete(registration)
		db.session.commit()
		return '两次输入不一致，请重新输入'
	else:
		#如果当前仅有一个重名用户且此人没有openId，则将其视为预先录入的老师，二者为同一人
		users = User.query.filter_by(name=name).all()
		if len(users)==1 and users[0].openId is None:
			users[0].openId = g.openId
			db.session.add(users[0])
		else:
			db.session.add(User(openId=g.openId, name=name))
		db.session.delete(registration)
		db.session.commit()
		return '您已设置姓名为 {}'.format(name)


def getRoom(roomName):
	room = Room.query.filter_by(name=roomName).first()
	if room is None:
		raise MyException('没有找到 {} 琴房'.format(roomName))
	return room


@message(patterns.reservation)
@authenticated
def processReservation(start, end, roomName):
	if 1 and not queryExist(g.user.shows):
		return '抱歉，在5月21日演奏会之前，只有演员可以预约'

	#活跃预约数不超过2
	nActiveReservations = (db.session.query(db.func.count(Reservation.id)).filter_by(user=g.user)
			.filter(Reservation.start>datetime.datetime.now())).scalar()
	if nActiveReservations >= 2:
		return '抱歉，每人最多持有 2 个预约。如需添加新的预约，请取消至少一个预约。'

	#时长不超过2小时
	if (end-start).seconds > 2*3600:
		return '抱歉，单次预约时长不能超过 2 个小时。'

	if roomName is not None:
		getRoom(roomName)
	practiceRoom, classRoom = Room.query.order_by(Room.id)

	for x in [0]:
		if roomName is None or roomName.lower() == practiceRoom.name.lower():
			isIdle = not queryExist(overlayedReservation(start, end, practiceRoom))
			if isIdle:
				reservation = Reservation(user=g.user, room=practiceRoom, start=start, end=end)
				db.session.add(reservation)
				db.session.commit()
				break

		if roomName is None or roomName.lower() == classRoom.name.lower():
			#在本学期有课还没上完的时候，只有老师可以预约两天之后的classRoom
			if not ((queryExist(g.user.courses) #是老师
				or (start.date()-datetime.datetime.now().date()).days <= 2)):
				return '抱歉，只有教课的老师可以预约超过 2 天之后的 {}'.format(roomName)

			#没有课
			isIdle = not queryExist(overlayedCourse(start,end))
			#没有预约
			isIdle = isIdle and not queryExist(overlayedReservation(start,end,classRoom))

			if isIdle:
				reservation = Reservation(user=g.user, room=classRoom, start=start, end=end)
				db.session.add(reservation)
				db.session.commit()
				break
	else:
		return '此时段预约已满' if roomName is None else '此时段的 {} 预约已满'.format(roomName)

	return '您已预约 {}'.format(reservation.getDateRoom())


@message(patterns.cancellation)
@authenticated
def processCancellation(time, roomName):
	query = Reservation.query.filter_by(user=g.user)
	if roomName is not None:
		query = query.filter_by(room=getRoom(roomName))
	reservations = query.filter(db.and_(Reservation.start<=time, time<Reservation.end))
	resultList = [r.getDateRoom() for r in reservations]
	if len(resultList)==0:
		return '您没有预约{}年{}月{}日{}:{:02}的{}'.format(
				time.year, time.month, time.day,
				time.hour, time.minute,
				'琴房' if roomName is None else roomName)
	reservations.delete()
	db.session.commit()
	return '您已取消{}{}'.format('\n'[:len(resultList)==1], '\n'.join(resultList))


@message(patterns.queryMyself)
@authenticated
def processQueryMyself():
	reservations = (g.user.reservations.filter(datetime.datetime.now()<Reservation.start)
			.order_by(Reservation.start))
	resultList = [r.getDateRoom() for r in reservations]
	if len(resultList)==0:
		return '您目前没有预约'
	return '您的预约:{}{}'.format('\n'[:len(resultList)==1], '\n'.join(resultList))


@message(patterns.query)
@authenticated
def processQuery(start, end):
	# 暂时只处理单日查询
	assert end-start <= datetime.timedelta(days=1)

	reservations = [(x.start, x.room.id,
		'{} {}:{:02}~{}:{:02} {}'.format(x.user.name, x.start.hour,
		x.start.minute, x.end.hour, x.end.minute, x.room.name))
		for x in overlayedReservation(start, end)]
	courses = [(datetime.datetime.combine(start.date(), x.startTime), x.room.id,
		'{}* {}:{:02}~{}:{:02} {}'.format(x.teacher.name, x.startTime.hour,
		x.startTime.minute, x.endTime.hour, x.endTime.minute, x.room.name))
		for x in overlayedCourse(start, end)]
	date = '{}年{}月{}日'.format(start.year, start.month, start.day)
	result = reservations + courses
	if len(result)==0:
		return '{}没有预约'.format(date)
	result.sort(key=lambda x:x[:2])
	result =  '{}：\n{}'.format(date, '\n'.join(x[2] for x in result))
	if len(courses)>0:
		result += '\n\n(*) 钢琴课'
	return result


def initDb():
	try: os.remove('db')
	except OSError: pass

	db.create_all()

	#room
	B252 = Room(name='B252')
	B253 = Room(name='B253')
	db.session.add(B252)
	db.session.add(B253)

	#legacy db
	legacyName = 'db.legacy'
	try: os.remove(legacyName)
	except OSError: pass
	print 'fetching legacy db ...'
	statusCode = os.system('scp hsw@115.159.82.217:/var/www/papuwx/db.sqlite3 {}'.format(legacyName))
	if statusCode != 0:
		raise RuntimeError('error while fetching legacy db')
	conn = sqlite3.connect(legacyName)

	#legacy users
	curs = conn.cursor()
	curs.execute('SELECT id,openid,name FROM users_person')
	users = {}
	for theId, openId, name in curs:
		user = User(openId=openId, name=name)
		users[theId] = user
		db.session.add(user)
	
	#legacy reservations
	curs=conn.cursor()
	curs.execute('SELECT start,end,person_id FROM appointment_appointment')
	practiceRoom, classRoom = Room.query.order_by(Room.id)
	for start, end, personId in curs:
		user = users[personId]
		start = datetime.datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
		end = datetime.datetime.strptime(end, '%Y-%m-%d %H:%M:%S')
		reservation = Reservation(user=user, start=start, end=end, room=practiceRoom)
		db.session.add(reservation)

	conn.close()
	try: os.remove(legacyName)
	except OSError: pass

	#course
	for line in open('courses.txt'):
		weekday, startHour, endHour, teacherName = line.decode('utf-8').split()
		weekday = '周一 周二 周三 周四 周五 周六 周日'.split().index(weekday)
		startTime = datetime.time(hour=int(startHour))
		endTime = datetime.time(hour=int(endHour))
		startDate = datetime.date(year=2016, month=3, day=21)
		endDate = datetime.date(year=2016, month=5, day=22)
		teacher = getCreateUser(teacherName)
		room = B253
		course = Course(teacher=teacher, room=room, weekday=weekday,
				startDate=startDate, endDate=endDate, startTime=startTime, endTime=endTime)
		db.session.add(course)

	#show
	for line in open('performers.txt'):
		performerNames = line.decode('utf-8').split()
		for performerName in performerNames:
			user = getCreateUser(performerName)
			show = Show(performer=user)
			db.session.add(show)

	db.session.commit()


def getCreateUser(name):
	user = User.query.filter_by(name=name).first()
	if user is None:
		user = User(name=name)
		db.session.add(user)
		db.session.commit()
	return user


if __name__=='__main__':
	if len(sys.argv)==2 and sys.argv[1]=='init':
		if raw_input("All data will be deleted. Are you sure? ")=='yes':
			initDb()
			print 'done'
		else:
			print 'aborted'
	else:
		#Manager(app).run()
		app.run(debug=True, host='::', port=80)
