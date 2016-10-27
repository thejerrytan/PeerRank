import mysql.connector, json, os, socket

ENV        = json.loads(open(os.path.join(os.path.dirname(__file__), 'env.json')).read())
MYSQL_HOST = ENV['MYSQL_HOST'] if socket.gethostname() != ENV['INSTANCE_HOSTNAME'] else "localhost"
MYSQL_USER = ENV['MYSQL_USER']
MYSQL_PW   = ENV['MYSQL_PW']
MYSQL_PORT = ENV['MYSQL_PORT']
MYSQL_DB   = ENV['MYSQL_DB']
cnx        = mysql.connector.connect(user=MYSQL_USER, password=MYSQL_PW, host=MYSQL_HOST, database=MYSQL_DB, allow_local_infile=True)
cursor     = cnx.cursor()

cursor.execute("SET autocommit = 0;")
cursor.execute("SET unique_checks = 0;")
cursor.execute("SET foreign_key_checks = 0")
for i in range(1, 21):
	cursor.execute("LOAD DATA LOCAL INFILE '/tmp/links%d.txt' IGNORE INTO TABLE test.follows FIELDS TERMINATED BY ' ' LINES TERMINATED BY '\n' (follower, followee);" % (i))
	cnx.commit()
cursor.execute("SET autocommit = 1;")
cursor.execute("SET unique_checks = 1;")
cursor.execute("SET foreign_key_checks = 1")
cnx.close()