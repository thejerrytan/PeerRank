from key import KeyManager
from tweepy import OAuthHandler, API, Cursor
from tweepy.error import TweepError
from collections import deque
import mysql.connector, math, sys, time, tweepy, threading, logging, json, os, socket

ENV               = json.loads(open(os.path.join(os.path.dirname(__file__), 'env.json')).read())
MYSQL_HOST        = ENV['MYSQL_HOST'] if socket.gethostname() != ENV['INSTANCE_HOSTNAME'] else "localhost"
MYSQL_USER        = ENV['MYSQL_USER']
MYSQL_PW          = ENV['MYSQL_PW']
MYSQL_PORT        = ENV['MYSQL_PORT']
NUM_USERS         = 500000
NO_THREADS        = 5
USERS_PER_PROCESS = math.ceil(NUM_USERS / NO_THREADS)
SO_FAR            = int(open('twitter_get_lists_for_user.txt', 'r').readline())
cnx               = mysql.connector.connect(pool_name="mypool", pool_size=6, user=MYSQL_USER, password=MYSQL_PW, host=MYSQL_HOST, database='test', charset='utf8mb4', collation='utf8mb4_general_ci', connection_timeout=3600)
cursor            = cnx.cursor()
qlock             = threading.Lock()

class Counter(object):
	def __init__(self, start=0):
		self.lock = threading.Lock()
		self.value = start
	def increment(self):
		logging.debug('Waiting for lock')
		self.lock.acquire()
		try:
			logging.debug('Acquired lock')
			self.value = self.value + 1
		finally:
			self.lock.release()

count = Counter(start=SO_FAR)
def authenticate(key):
	auth = OAuthHandler(key['consumer_key'], key['consumer_secret'])
	auth.set_access_token(key['access_token_key'], key['access_token_secret'])
	api = API(auth_handler=auth, wait_on_rate_limit=False, wait_on_rate_limit_notify=True)
	return api

def reconnect():
	""" Create a new connection"""
	cnx = mysql.connector.connect(pool_name= "mypool", pool_size=6, user=MYSQL_USER, password=MYSQL_PW, host=MYSQL_HOST, database='test',charset='utf8mb4', collation='utf8mb4_general_ci', get_warnings=True, connection_timeout=3600)
	return (cnx.cursor(), cnx)

class Worker(threading.Thread):
	def __init__(self, users, group=None, target=None, name=None, args=(), kwargs=None, verbose=None):
		self.local  = threading.local()
		self.cnx    = mysql.connector.connect(pool_name="mypool", pool_size=6, user=MYSQL_USER, password=MYSQL_PW, host=MYSQL_HOST, database='test', charset='utf8mb4', collation='utf8mb4_general_ci', get_warnings=True, connection_timeout=3600)
		self.cursor = self.cnx.cursor()
		self.cursor.execute("SET SESSION net_read_timeout = 3600")
		self.cursor.execute("SET SESSION net_write_timeout = 3600")
		self.km     = KeyManager('Twitter-Search-v1.1', 'keys.json')
		self.api    = authenticate(self.km.get_key())
		self.users  = users # shared resource
		threading.Thread.__init__(self, group=group, target=target, name=name, verbose=verbose)

	def run(self):
		# Acquire qlock
		hasWork = True
		while hasWork:
			qlock.acquire()
			try:
				size = len(self.users)
				if size > 0:
					(user, screen_name) = self.users.popleft()
				else:
					self.cnx.close()
					hasWork = False
			finally:
				qlock.release()
			if hasWork: self.insert_list(user, screen_name)

	def insert_list(self, user, screen_name):
		# Insert list
		print("Inserting lists for user %d : %s" % (user, screen_name))
		max_page = 2000 / 20
		curr_page = 0
		cursor = -1
		try:
			while cursor is not None and curr_page < max_page:
				try:
					(lists, paginate) = self.api.lists_memberships(id=user, cursor=cursor)
					for l in lists:
						self.cursor.execute("INSERT INTO test.lists (list_id, url, name, description, subscriber_count, member_count, created_at) VALUES(%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE url=%s", (l.id, l.uri, l.name, l.description, l.subscriber_count, l.member_count, l.created_at, l.uri))
						self.cnx.commit()
						self.cursor.execute("INSERT INTO test.member_of (user_id, list_id) VALUES(%s, %s) ON DUPLICATE KEY UPDATE user_id=%s", (user, l.id, user))
						self.cnx.commit()
				except tweepy.RateLimitError as e:
					print e
					time.sleep(5)
					self.km.invalidate_key()
					self.km.change_key()
					self.api = authenticate(self.km.get_key())
					(lists, paginate) = self.api.lists_memberships(id=user, cursor=cursor)
					for l in lists:
						self.cursor.execute("INSERT INTO test.lists (list_id, url, name, description, subscriber_count, member_count, created_at) VALUES(%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE url=%s", (l.id, l.uri, l.name, l.description, l.subscriber_count, l.member_count, l.created_at, l.uri))
						self.cnx.commit()
						self.cursor.execute("INSERT INTO test.member_of (user_id, list_id) VALUES(%s, %s) ON DUPLICATE KEY UPDATE user_id=%s", (user, l.id, user))
						self.cnx.commit()
				except TweepError as e:
					print(e)
					if type(e.message) is list and e.message[0]['code'] == 32: # Could not authenticate
						time.sleep(5)
						self.km.invalidate_key()
						self.km.change_key()
						self.api = authenticate(self.km.get_key())
						(lists, paginate) = self.api.lists_memberships(id=user, cursor=cursor)
						for l in lists:
							self.cursor.execute("INSERT INTO test.lists (list_id, url, name, description, subscriber_count, member_count, created_at) VALUES(%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE url=%s", (l.id, l.uri, l.name, l.description, l.subscriber_count, l.member_count, l.created_at, l.uri))
							self.cnx.commit()
							self.cursor.execute("INSERT INTO test.member_of (user_id, list_id) VALUES(%s, %s) ON DUPLICATE KEY UPDATE user_id=%s", (user, l.id, user))
							self.cnx.commit()
				finally:
					curr_page += 1
					cursor = paginate[1]
					print(curr_page, cursor)
			count.increment()
			if count.value % 100 == 0:
				print ("Progress : %d" % int(count.value))
				with open('twitter_get_lists_for_user.txt', 'w') as f:
					f.write(str(count.value))
				f.close()	
		except Exception as e:
			print(e)
			self.cnx.close()
			(self.cursor, self.cnx) = reconnect()
			self.insert_list(user, screen_name)

def main():
	"""For users with listed_count > 10, get lists they are members of and insert into DB"""
	users = deque([])
	threads = []
	print("Starting with: %d " % SO_FAR)
	try:
		cursor.execute("SET SESSION net_read_timeout = 3600")
		cursor.execute("SELECT user_id, screen_name FROM `test`.`new_temp` WHERE listed_count > 10 LIMIT %d OFFSET %d" % (NUM_USERS, SO_FAR))
		for row in cursor:
			users.append((int(row[0]), row[1]))
		for t in range(0, NO_THREADS):
			t = Worker(users)
			threads.append(t)
			t.start()
		for t in threads:
			t.join()
		with open('twitter_get_lists_for_user.txt', 'w') as f:
			f.write(str(count.value))
		f.close()
		sys.exit(0)
	except Exception as e:
		print e
	finally:
		cnx.close()

if __name__ == "__main__":
	main()
