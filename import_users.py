import mysql.connector, math, requests, subprocess, shlex, sys

MYSQL_USER      = 'root'
MYSQL_PW        = 'root'
MYSQL_TABLE     = 'follows'
MYSQL_DB        = 'test'
MYSQL_HOST_DEV  = '104.196.149.230'
MYSQL_HOST_LIVE = '104.198.155.210'
# PATH_TO_DATA  = "/Users/Jerry/Desktop/anon-links.txt"
# PATH_TO_DATA  = "/Volumes/Mac/data/links1.txt"
# PATH_TO_DATA  = "gs://peerrank-141304.appspot.com/data/links-anon.txt"
# PATH_TO_DATA  = "/tmp/links%s.txt"
PATH_TO_DATA    = "/tmp/links1.txt"
PER_PAGE        = 10000
NO_PROCESS      = 10

def main(hostname=None):
	if hostname is None:
		hostname = MYSQL_HOST_LIVE
	elif hostname == 'live':
		hostname = MYSQL_HOST_LIVE
	elif hostname == 'dev':
		hostname = MYSQL_HOST_DEV
	else:
		hostname = 'localhost'
	cnx = mysql.connector.connect(user='root', password='root', host=hostname, database='test')
	cursor = cnx.cursor()
	f = open(PATH_TO_DATA, 'r')
	data = []
	line_count = 0
	print("Reading file...")
	for line in f:
		(follower, followee) = line.split(' ')
		data.append((int(follower.strip('\n')), int(followee.strip('\n'))))
		line_count += 1
		if line_count % PER_PAGE == 0:
			temp  = set(map(lambda x: (x[1],), data))
			print("Entering data...")
			try:
				cursor.executemany("INSERT IGNORE INTO test.temp (id) VALUES(%s)", temp)
				cursor.executemany("INSERT IGNORE INTO test.new_temp (user_id) VALUES(%s)", temp)
				print("Rows affected: %d" % cursor.rowcount)
			except Exception as e:
				print e
			cnx.commit()
			data = []
			print("Processed so far : %d" % line_count)
	cnx.close()
	f.close()

if __name__ == "__main__":
	if sys.argv[1] is not None:
		main(hostname=sys.argv[1])
	else:
		main()