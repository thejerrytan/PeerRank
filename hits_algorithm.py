import mysql.connector, math, time, threading, logging

ITERATIONS = 100
iter_count = 0
MYSQL_HOST = '104.198.155.210'
MYSQL_USER = 'root'
MYSQL_PW   = 'root'
SO_FAR     = open('hits_algorithm.txt', 'r').readline()
start      = int(SO_FAR.split(',')[0])
skip       = int(SO_FAR.split(',')[1])
cnx        = mysql.connector.connect(user='root', password='root', host='104.198.155.210', database='test')
cursor     = cnx.cursor()
TOTAL      = 1000000000
PER_PAGE   = 1000000
NO_THREADS = 50
qlock      = threading.Lock()
hub_lock   = threading.Lock()
auth_lock  = threading.Lock()
startTime  = time.time()
norm_hub   = int(SO_FAR.split(',')[2])
norm_auth  = int(SO_FAR.split(',')[3])

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

count = Counter(start=skip)
class Worker(threading.Thread):
	def __init__(self, users, group=None, target=None, name=None, args=(), kwargs=None, verbose=None):
		self.cnx    = mysql.connector.connect(user=MYSQL_USER, password=MYSQL_PW, host=MYSQL_HOST, database='test')
		self.cursor = self.cnx.cursor()
		self.users  = users # shared resource
		threading.Thread.__init__(self, group=group, target=target, name=name, verbose=verbose)

	def run(self):
		# Acquire qlock
		while True:
			qlock.acquire()
			size = len(self.users)
			if size > 0:
				user = self.users.pop()
				# Release qlock
				qlock.release()
				self.update(user)
			else:
				qlock.release()
				self.cnx.close()
				break

	def update(self, user):
		global norm_auth, norm_hub, start
		count.increment()
		# Find followers
		if count.value % 100 == 0:
			print("Processed %d users." % count.value)
			print("Time taken per user: %f" % ((time.time() - startTime) / count.value))
			with open('hits_algorithm.txt', 'w') as f:
				f.write(str(start) +  ',' + str(count.value) + ',' + str(norm_hub) + ',' + str(norm_auth))
			f.close()
		try:
			self.cursor.execute("SELECT `follower` FROM test.follows WHERE followee = %s LIMIT 10000000" , (user,))
			auth = 0
			followers = []
			for row in self.cursor:
				followers.append(str(row[0]))
			query = ','.join(followers)
			if len(followers) == 0:
				auth = 0
			else:
				self.cursor.execute("SELECT hub FROM test.users_for_hits WHERE id IN (%s)"  % query)
				auth = reduce(lambda x, y: x + int(y[0]), self.cursor, 0)
			auth_lock.acquire()
			norm_auth += auth * auth
			auth_lock.release()
			# print("Auth score for user %s : %d" % (user, auth))
			self.cursor.execute("UPDATE test.users_for_hits SET authority = %s WHERE id = %s" % (auth, user))
			self.cnx.commit()
			# Calculate hub score
			followee = []
			self.cursor.execute("SELECT followee FROM test.follows WHERE follower = %s LIMIT 10000000" , (user,))
			for row in self.cursor:
				followee.append(str(row[0]))
			query = ','.join(followee)
			if len(followee) == 0:
				hub = 0
			else:
				self.cursor.execute("SELECT authority FROM test.users_for_hits WHERE id IN (%s)" % query)
				hub = reduce(lambda x, y: x + int(y[0]), self.cursor, 0)
			hub_lock.acquire()
			norm_hub += hub * hub
			hub_lock.release()
			# print("Hub  score for user %s : %d" % (user, hub))
			self.cursor.execute("UPDATE test.users_for_hits SET hub = %s WHERE id = %s" , (hub, user))
			self.cnx.commit()
		except Exception as e:
			print e
			time.sleep(30)
			self.cnx.close()
			(self.cursor, self.cnx) = reconnect()

def reconnect():
	""" Create a new connection"""
	cnx = mysql.connector.connect(user=MYSQL_USER, password=MYSQL_PW, host=MYSQL_HOST, database='test')
	return (cnx.cursor(), cnx)

def reset():
	""" Reset hub and authority scores to 1 for all users"""
	cursor.execute("UPDATE test.users_for_hits SET hub = 1, authority = 1 ")
	cnx.commit()

def get_users(end, retry=None):
	global cursor
	""" Fault tolerant way of getting users from MySQL db, retry for max 10 tries if connection to MYSQL is lost"""
	try:
		cursor.execute("SELECT `id` FROM test.users_for_hits WHERE id BETWEEN %s AND %s LIMIT %s" , (start, end, PER_PAGE))
	except Exception as e:
		print e
		time.sleep(30) # Back off for 30 seconds
		if retry == 0:
			print("Exceeded maximum number of retries in function get_users")
			sys.exit(1)
		retry = 10 if retry is None else retry - 1
		cnx.close()
		(cursor, cnx) = reconnect()
		get_users(retry=retry)

def normalize_scores(end, retry=None):
	""" Fault tolerant sql query, retry for max 10 tries if connection to MYSQL is lost"""
	global cursor
	try:
		cursor.execute("UPDATE test.users_for_hits SET hub = (hub / %s), authority = (authority / %s) WHERE id BETWEEN %s AND %s" , (norm_hub, norm_auth, start, end))
	except Exception as e:
		print e
		time.sleep(30)
		if retry == 0:
			print("Exceeded maximum number of retries in function normalize_scores")
			sys.exit(1)
		retry = 10 if retry is None else retry - 1
		cnx.close()
		(cursor, cnx) = reconnect()
		normalize_scores(end, retry=retry)

def main():
	global iter_count, norm_hub, norm_auth, start, skip
	while iter_count < ITERATIONS:
		print("ITERATION: %d" % iter_count)
		while (start + PER_PAGE - 1) < TOTAL:
			end     = start + PER_PAGE - 1
			threads = []
			users   = []
			get_users(end, retry=None)
			for row in cursor:
				users.append(int(row[0]))
			# Skip number of users processed so far for this batch of start
			skipped = 0
			while skipped < skip:
				users.pop()
				skipped += 1
			# Single producer multiple workers multithreading model
			for t in range(0, NO_THREADS):
				t = Worker(users)
				threads.append(t)
				t.start()
			# Synchronize wait for all threads to finish
			for t in threads:
				t.join()
			start += PER_PAGE
			with open('hits_algorithm.txt', 'w') as f:
				f.write(str(start) +  ',' + str(count.value) + ',' + str(norm_hub) + ',' + str(norm_auth))
			f.close()
		# Normalize
		start     = 0
		norm_hub  = math.sqrt(norm_hub)
		norm_auth = math.sqrt(norm_auth)
		while (start + PER_PAGE - 1) < TOTAL:
			end = start + PER_PAGE - 1
			normalize_scores(end, retry=None)
			start += PER_PAGE
			cnx.commit()
		# next iteration, reset values
		iter_count  += 1
		count.value = 0
		start       = 0
		norm_hub    = 0
		norm_auth   = 0
		skip        = 0
	cnx.close()

if __name__=="__main__":
	reset()
	main()