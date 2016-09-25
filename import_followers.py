import mysql.connector, math, requests, subprocess, shlex, sys

MYSQL_USER     = 'root'
MYSQL_PW       = 'root'
MYSQL_TABLE    = 'follows'
MYSQL_DB       = 'test'
MYSQL_HOST     = '104.196.149.230'
# PATH_TO_DATA = "/Users/Jerry/Desktop/anon-links.txt"
# PATH_TO_DATA   = "/Volumes/Mac/data/links1.txt"
# PATH_TO_DATA = "gs://peerrank-141304.appspot.com/data/links-anon.txt"
PATH_TO_DATA = "/tmp/links%s.txt"
PER_PAGE       = 100000
NO_PROCESS     = 20
def process(data, cursor):
	try:
		cursor.executemany("INSERT INTO test.follows (follower, followee) VALUES(%s, %s)", data)
		print("New edges added: %d" % cursor.rowcount)
	except Exception as e:
		print e
		new_users = map(lambda x: x[1], data)
		try:
			new_user_count = 0
			for r in new_users:
				cursor.execute("INSERT IGNORE INTO test.temp (id) VALUES(%s)" % r)
				new_user_count += cursor.rowcount
				cursor.execute("INSERT IGNORE INTO test.new_temp (user_id) VALUES(%s)" % r)
			print("New users: %d" % new_user_count)
			cursor.executemany("INSERT INTO test.follows (follower, followee) VALUES(%s, %s)", data)
			print("New edges added: %d" % cursor.rowcount)
		except Exception as e:
			print e
	print("INSERTED SO FAR: %d" % count)

def generate_filename(i):
	return PATH_TO_DATA % i

def main(host=MYSQL_HOST):
	master = len(sys.argv) == 4
	# Spin up multiple processes
	if master:
		process = []
		for i in range(2, NO_PROCESS+1):
			host_arg  = host
			start_arg = i
			cmd = "python import_followers.py %s %d" % (host_arg, start_arg)
			args = shlex.split(cmd)
			process.append(subprocess.Popen(args, stdin=subprocess.PIPE))
			print("Starting child process [%s]" % cmd)
	cnx = mysql.connector.connect(user='root', password='root', host=host, database='test')
	cursor = cnx.cursor()
	f = open(generate_filename(sys.argv[2]), 'r')
	
	data = []
	count = 0
	for line in f:
		(follower, followee) = line.split(' ')
		data.append((int(follower.strip('\n')), int(followee.strip('\n'))))
		count += 1
		if count % 100000 == 0:
			process(data, cursor)
			data = []
			cnx.commit()
	process(data, cursor)
	cnx.commit()
	f.close()
	cnx.close()
	if master:
		while len(process) > 0:
			print("Terminating child process...")
			process.pop().terminate()
		sys.exit(0)
	sys.exit(0)

if __name__ == "__main__":
	try:
		main(host=sys.argv[1])
	except Exception as e:
		main()