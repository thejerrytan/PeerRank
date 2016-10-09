from key import KeyManager
from tweepy import OAuthHandler, API, Cursor
from tweepy.error import TweepError
from collections import deque
import mysql.connector, math, sys, time, tweepy, threading, logging

MYSQL_HOST        = '104.198.155.210'
MYSQL_USER        = 'root'
MYSQL_PW          = 'root'
NUM_USERS         = 281699
NO_THREADS        = 3
USERS_PER_PROCESS = math.ceil(NUM_USERS / NO_THREADS)
SO_FAR            = int(open('twitter_get_lists_for_user_count.txt', 'r').readline())
cnx               = mysql.connector.connect(user=MYSQL_USER, password=MYSQL_PW, host=MYSQL_HOST, database='test')
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

class Worker(threading.Thread):
	def __init__(self, users, group=None, target=None, name=None, args=(), kwargs=None, verbose=None):
		self.local  = threading.local()
		self.cnx    = mysql.connector.connect(user=MYSQL_USER, password=MYSQL_PW, host=MYSQL_HOST, database='test')
		self.cursor = self.cnx.cursor()
		self.km     = KeyManager('Twitter-Search-v1.1', 'keys.json')
		self.api    = authenticate(self.km.get_key())
		self.users  = users # shared resource
		threading.Thread.__init__(self, group=group, target=target, name=name, verbose=verbose)

	def run(self):
		# Acquire qlock
		while True:
			qlock.acquire()
			size = len(self.users)
			if size > 0:
				user = self.users.popleft()
				# Release qlock
				qlock.release()
				self.insert_list(user)
			else:
				qlock.release()
				self.cnx.close()
				break

	def insert_list(self, user):
		# Insert list
		try:
			for l in tweepy.Cursor(self.api.lists_memberships, id=user).items(2000):
				self.cursor.execute("INSERT IGNORE INTO test.lists (list_id, url, name, description, subscriber_count, member_count, created_at) VALUES(%s, %s, %s, %s, %s, %s, %s)", (l.id, l.uri, l.name, l.description, l.subscriber_count, l.member_count, l.created_at))
				self.cnx.commit()
				self.cursor.execute("INSERT IGNORE INTO test.member_of (user_id, list_id) VALUES(%s, %s)", (user, l.id))
				self.cnx.commit()
				count.increment()
				if count.value % 100 == 0:
					print ("Progress : %d" % int(count.value))
					with open('twitter_get_lists_for_user_count.txt', 'w') as f:
						f.write(str(count.value))
					f.close()
		except tweepy.RateLimitError as e:
			print e
			time.sleep(60)
			self.km.invalidate_key()
			self.km.change_key()
			self.api = authenticate(self.km.get_key())
			self.insert_list(user)
		except TweepError as e:
			print(e)
			if type(e.message) is list and e.message[0]['code'] == 32: # Could not authenticate
				time.sleep(60)
				self.km.invalidate_key()
				self.km.change_key()
				self.api = authenticate(self.km.get_key())
				self.insert_list(user)

def main():
	"""For users with listed_count > 10, get lists they are members of and insert into DB"""
	users = deque([])
	threads = []
	print("Starting with: %d " % SO_FAR)
	try:
		cursor.execute("SELECT user_id FROM test.new_temp WHERE listed_count > 10 LIMIT %d OFFSET %d" % (NUM_USERS, SO_FAR))
		cnx.close()
		for row in cursor:
			users.append(int(row[0]))
		for t in range(0, NO_THREADS):
			t = Worker(users)
			threads.append(t)
			t.start()
		for t in threads:
			t.join()
		with open('twitter_get_lists_for_user_count.txt', 'w') as f:
			f.write(str(count.value))
		f.close()
		sys.exit(1)
	except Exception as e:
		print e
		cnx.close()

if __name__ == "__main__":
	main()