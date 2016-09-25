import mysql.connector, math, requests, subprocess, shlex, sys

MYSQL_USER     = 'root'
MYSQL_PW       = 'root'
MYSQL_TABLE    = 'follows'
MYSQL_DB       = 'test'
# PATH_TO_DATA = "/Users/Jerry/Desktop/anon-links.txt"
PATH_TO_DATA = "/Volumes/Mac/data/links1.txt"
# PATH_TO_DATA   = "gs://peerrank-141304.appspot.com/data/links-anon.txt"
PER_PAGE = 100000

def main():
	cnx = mysql.connector.connect(user='root', password='root', host='104.196.149.230', database='test')
	cursor = cnx.cursor()
	f = open(PATH_TO_DATA, 'r')
	data = []
	count = 0
	for line in f:
		(follower, followee) = line.split(' ')
		data.append((int(follower.strip('\n')), int(followee.strip('\n'))))
		count += 1
		if count % 100000 == 0:
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
			data = []
			cnx.commit()
	f.close()
	cnx.close()

if __name__ == "__main__":
	main()