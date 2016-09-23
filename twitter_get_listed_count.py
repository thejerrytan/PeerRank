from requests_oauthlib import OAuth1
from requests.exceptions import Timeout, ConnectionError
from requests.packages.urllib3.exceptions import ReadTimeoutError
from key import KeyManager
from tweepy import OAuthHandler, API, Cursor
from tweepy.error import TweepError
import mysql.connector, math, requests, subprocess, shlex, sys


def get_users(query, km):
	data = []
	key = km.get_key()
	oauth = OAuth1(key['consumer_key'], key['consumer_secret'], key['access_token_key'], key['access_token_secret'])
	r = requests.get("https://api.twitter.com/1.1/users/lookup.json?user_id="+query[:-1], auth=oauth)
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
				if response['errors'][0]['code'] == 88:
					# Rate Limit exceeded
					km.invalidate_key()
					km.change_key()
					return get_users(query, km)
	return data

def main():
	""" Remove inactive user_ids from database and add listed_count information for each user"""
	SO_FAR         = 0
	NUM_PAGES      = math.ceil((43983853 - SO_FAR) / 100)
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

	cnx = mysql.connector.connect(user='root', password='root', host='104.196.149.230', database='test')
	cursor = cnx.cursor()
	km = KeyManager('Twitter-Search-v1.1', 'keys.json')
	key = km.get_key()
	# auth = OAuthHandler(key['consumer_key'], key['consumer_secret'])
	# auth.set_access_token(key['access_token_key'], key['access_token_secret'])
	# api = API(auth_handler=auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)
	while start <= end:
		print("Executing page %d" % start)
		offset = start * 100
		try:
			cursor.execute("SELECT `id` FROM test.temp WHERE listed_count IS NULL LIMIT 100 OFFSET %d" % offset)
		except mysql.connector.errors.IntegrityError as e:
			print e
		query = ''
		for row in cursor:
			query += str(row[0]) + ','
		
		data = get_users(query, km)

		# Insert listed_count
		if len(data) > 0:
			print("Updating user listed count...")
			try:
				cursor.executemany("INSERT INTO test.temp (id, listed_count) VALUES(%s, %s) ON DUPLICATE KEY UPDATE listed_count=VALUES(listed_count)", data)
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

if __name__=="__main__":
	main()