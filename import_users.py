import mysql.connector, math, requests, subprocess, shlex, sys

MYSQL_USER     = 'root'
MYSQL_PW       = 'root'
MYSQL_TABLE    = 'follows'
MYSQL_DB       = 'test'
MYSQL_HOST     = '104.196.149.230'
# PATH_TO_DATA = "/Users/Jerry/Desktop/anon-links.txt"
# PATH_TO_DATA   = "/Volumes/Mac/data/links1.txt"
# PATH_TO_DATA = "gs://peerrank-141304.appspot.com/data/links-anon.txt"
# PATH_TO_DATA = "/tmp/links%s.txt"
PATH_TO_DATA   = "/tmp/links-anon.txt"
PER_PAGE       = 100000
NO_PROCESS     = 10

def main(hostname=None):
	hostname = MYSQL_HOST if hostname is None else hostname
	cnx = mysql.connector.connect(user='root', password='root', host=hostname, database='test')
	cursor = cnx.cursor()
	f = open(PATH_TO_DATA, 'r')
	data = []
	print("Reading file...")
	for line in f:
		(follower, followee) = line.split(' ')
		data.append((int(follower.strip('\n')), int(followee.strip('\n'))))
	temp = set(map(lambda x: x[1], data))
	total = len(temp)
	count = 0
	print("Entering data...")
	for user in temp:
		try:
			cursor.execute("INSERT IGNORE INTO test.temp (id) VALUES(%s)" % user)
			cursor.execute("INSERT IGNORE INTO test.new_temp (user_id) VALUES(%s)" % user)
			count += 1
			if (count / 1.0 * total * 100) % 1 < 0.05:
				print(str(count / 1.0 * total * 100) + " completed")
		except Exception as e:
			print e

if __name__ == "__main__":
	if sys.argv[1] is not None:
		main(hostname=sys.argv[1])
	else:
		main()