from requests_oauthlib import OAuth1
from requests.exceptions import Timeout, ConnectionError
from requests.packages.urllib3.exceptions import ReadTimeoutError
from key import KeyManager
from tweepy import OAuthHandler, API, Cursor
from tweepy.error import TweepError
import mysql.connector, math, requests, subprocess, shlex, sys

def main():
	""" Remove inactive user_ids from database and add listed_count information for each user"""
	SO_FAR = 95
	NUM_PAGES = math.ceil((43983853 - SO_FAR) / 100)
	NO_PROCESS = 100
	PG_PER_PROCESS = math.ceil(NUM_PAGES / NO_PROCESS)
	start = int(sys.argv[1])
	end   = start + PG_PER_PROCESS
	master = len(sys.argv) == 3
	# Spin up multiple processes
	if master:
		process = []
		for i in range(0, NO_PROCESS):
			start_arg = math.floor(i * PG_PER_PROCESS)
			cmd = "python twitter_get_listed_count.py %d" % start_arg
			args = shlex.split(cmd)
			process.append(subprocess.Popen(args))
			print("Starting child process [%s]" % cmd)

	cnx = mysql.connector.connect(user='root', password='root', host='104.196.149.230', database='test')
	cursor = cnx.cursor()
	km = KeyManager('Twitter-Search-v1.1', 'keys.json')
	key = km.get_key()
	# auth = OAuthHandler(key['consumer_key'], key['consumer_secret'])
	# auth.set_access_token(key['access_token_key'], key['access_token_secret'])
	# api = API(auth_handler=auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)
	oauth = OAuth1(key['consumer_key'], key['consumer_secret'], key['access_token_key'], key['access_token_secret'])
	while start <= end:
		print("Executing page %d" % start)
		data = []
		offset = start * 100
		try:
			cursor.execute("SELECT `id` FROM test.users LIMIT 100 OFFSET %d" % offset)
		except mysql.connector.errors.IntegrityError as e:
			print e
		query = ''
		for row in cursor:
			query += str(row[0]) + ','
		r = requests.get("https://api.twitter.com/1.1/users/lookup.json?user_id="+query[:-1], auth=oauth)
		# Processing stage
		if r.json() is not None:
			for user in r.json():
				try:
					# print(user['listed_count'])
					data.append((user['id'], user['listed_count'], user['listed_count'], user['id']))
				except Exception as e:
					# May be 404 error, which means user is not found, delete from DB
					print e
					print r.json()

		# Insert listed_count
		print("Updating user listed count...")	
		try:
			cursor.executemany("INSERT INTO test.users (id, listed_count) VALUES(%d, %d) ON DUPLICATE KEY UPDATE SET listed_count=%d WHERE id=%d", data)
		except mysql.connector.errors.IntegrityError as e:
			print e
		print("Update done")
		# Remove inactive accounts
		cnx.commit()
		start += 1
	cnx.close()
	if master:
		while len(process) > 0:
			process.pop().terminate()

if __name__=="__main__":
	main()