from requests_oauthlib import OAuth1
from requests.exceptions import Timeout, ConnectionError
from requests.packages.urllib3.exceptions import ReadTimeoutError
from key import KeyManager
from tweepy import OAuthHandler, API, Cursor
from tweepy.error import TweepError
import mysql.connector, math, requests, subprocess, shlex, sys, time, json

ENV        = json.loads(open(os.path.join(os.path.dirname(__file__), 'env.json')).read())
MYSQL_HOST = ENV['MYSQL_HOST']
MYSQL_USER = ENV['MYSQL_USER']
MYSQL_PW   = ENV['MYSQL_PW']
MYSQL_PORT = ENV['MYSQL_PORT']

def get_users(query, km, retry=None):
	data = []
	key = km.get_key()
	oauth = OAuth1(key['consumer_key'], key['consumer_secret'], key['access_token_key'], key['access_token_secret'])
	try:
		r = requests.get("https://api.twitter.com/1.1/users/lookup.json?user_id="+query, auth=oauth)
	except Exception as e:
		retry = 10 if retry is None else retry - 1
		if retry == 0:
			return data
		else:
			return get_users(query, km, retry=retry)
	response = r.json()
	if response is not None:
		for user in response:
			try:
				# print(user['listed_count'])
				data.append((int(user['id']), int(user['listed_count'])))
			except Exception as e:
				# May be 404 error, which means user is not found, delete from DB
				print e
				print(response)
				if response['errors'][0]['code'] == 88 or response['errors'][0]['code'] == 32:
					# Rate Limit exceeded
					time.sleep(5)
					km.invalidate_key()
					km.change_key()
					return get_users(query, km)
	return data

def main():
	""" Remove inactive user_ids from database and add listed_count information for each user"""
	SO_FAR         = 0
	NUM_PAGES      = math.ceil((52579682 - SO_FAR) / 100)
	NO_PROCESS     = 10
	PG_PER_PROCESS = math.ceil(NUM_PAGES / NO_PROCESS)
	start          = int(sys.argv[1])
	end            = start + PG_PER_PROCESS
	master         = len(sys.argv) == 3
	# Spin up multiple processes
	if master:
		process = []
		for i in range(1, NO_PROCESS):
			start_arg = math.floor(i * PG_PER_PROCESS)
			cmd = "python twitter_get_listed_count.py %d" % start_arg
			args = shlex.split(cmd)
			process.append(subprocess.Popen(args, stdin=subprocess.PIPE))
			print("Starting child process [%s]" % cmd)

	cnx = mysql.connector.connect(user=MYSQL_USER, password=MYSQL_PW, host=MYSQL_HOST, database='test')
	cursor = cnx.cursor()
	km = KeyManager('Twitter-Search-v1.1', 'keys.json')
	key = km.get_key()
	# auth = OAuthHandler(key['consumer_key'], key['consumer_secret'])
	# auth.set_access_token(key['access_token_key'], key['access_token_secret'])
	# api = API(auth_handler=auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)
	while start <= end:
		print("Executing page %d" % start)
		start_id = (start * 100) + 1
		end_id   = start_id + 99
		try:
			cursor.execute("SELECT `user_id` FROM test.new_temp WHERE id BETWEEN %d AND %d" % (start_id, end_id))
		except mysql.connector.errors.IntegrityError as e:
			print e
		
		query = ','.join([str(row[0]) for row in cursor])

		data = get_users(query, km)

		# Insert listed_count
		if len(data) > 0:
			print("Updating user listed count...")
			try:
				cursor.executemany("INSERT INTO test.new_temp (user_id, listed_count) VALUES(%s, %s) ON DUPLICATE KEY UPDATE listed_count=VALUES(listed_count)", data)
				print("Rows affected: %d" % cursor.rowcount)
			except Exception as e:
				print e
			print("Update done")
		print("Remaining pages: %d" % (int(end) - int(start)))
		# Remove inactive accounts
		cnx.commit()
		start += 1
	cnx.close()
	if master:
		while len(process) > 0:
			print("Terminating child process...")
			process.pop().terminate()
		sys.exit(0)

if __name__=="__main__":
	main()