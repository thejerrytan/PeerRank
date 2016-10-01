from key import KeyManager
from tweepy import OAuthHandler, API, Cursor
from tweepy.error import TweepError
import mysql.connector, math, requests, subprocess, shlex, sys, time, tweepy

MYSQL_HOST        = '104.198.155.210'
MYSQL_USER        = 'root'
MYSQL_PW          = 'root'
NUM_USERS         = 281699
NO_PROCESS        = 5
USERS_PER_PROCESS = math.ceil(NUM_USERS / NO_PROCESS)
km                = KeyManager('Twitter-Search-v1.1', 'keys.json')
cnx               = mysql.connector.connect(user=MYSQL_USER, password=MYSQL_PW, host=MYSQL_HOST, database='test')
cursor            = cnx.cursor()
key               = km.get_key()

def authenticate(key):
	auth = OAuthHandler(key['consumer_key'], key['consumer_secret'])
	auth.set_access_token(key['access_token_key'], key['access_token_secret'])
	api = API(auth_handler=auth, wait_on_rate_limit=False, wait_on_rate_limit_notify=True)
	return api

def insert_list(api, user):
	# Insert list
	try:
		for l in tweepy.Cursor(api.lists_memberships, id=user).items():
			cursor.execute("INSERT IGNORE INTO test.lists (list_id, url, name, description, subscriber_count, member_count, created_at) VALUES(%s, %s, %s, %s, %s, %s, %s)", (l.id, l.uri, l.name, l.description, l.subscriber_count, l.member_count, l.created_at))
			cnx.commit()
			cursor.execute("INSERT IGNORE INTO test.member_of (user_id, list_id) VALUES(%s, %s)", (user, l.id))
			cnx.commit()
	except TweepError as e:
		print e
		time.sleep(60)
		km.invalidate_key()
		km.change_key()
		api = authenticate(km.get_key())
		insert_list(api, user)

def main():
	"""For users with listed_count > 10, get lists they are members of and insert into DB"""
	start  = int(sys.argv[1])
	end    = start + USERS_PER_PROCESS
	master = len(sys.argv) == 3
	api    = authenticate(key)
	# Spin up multiple processes
	if master:
		process = []
		for i in range(1, NO_PROCESS):
			start_arg = math.floor(i * USERS_PER_PROCESS)
			cmd = "python twitter_get_lists_for_user.py %d" % start_arg
			args = shlex.split(cmd)
			process.append(subprocess.Popen(args, stdin=subprocess.PIPE))
			print("Starting child process [%s]" % cmd)
	users = []
	count = 0
	try:
		cursor.execute("SELECT * FROM test.new_temp WHERE listed_count > 10 LIMIT %d OFFSET %d" % (USERS_PER_PROCESS, end))
		for row in cursor:
			users.append(int(row[1]))
		while len(users) > 0:
			insert_list(api, users.pop())
			count += 1
			if count % 1000 == 0:
				print ("Progress : %d", start + count)
	except Exception as e:
		print e
	cnx.close()
	# Cleanup
	if master:
		while len(process) > 0:
			print("Terminating child process...")
			process.pop().terminate()
		sys.exit(0)

if __name__ == "__main__":
	main()