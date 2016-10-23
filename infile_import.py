import mysql.connector

MYSQL_HOST        = '104.198.155.210'
MYSQL_USER        = 'root'
MYSQL_PW          = 'root'
cnx               = mysql.connector.connect(user=MYSQL_USER, password=MYSQL_PW, host=MYSQL_HOST, database='test', allow_local_infile=True)
cursor            = cnx.cursor()

cursor.execute("SET autocommit = 0;")
cursor.execute("SET unique_checks = 0;")
cursor.execute("SET foreign_key_checks = 0")
cursor.execute("LOAD DATA LOCAL INFILE '/tmp/links17.txt' IGNORE INTO TABLE test.follows FIELDS TERMINATED BY ' ' LINES TERMINATED BY '\n' (follower, followee);")
cnx.commit()
cursor.execute("LOAD DATA LOCAL INFILE '/tmp/links18.txt' IGNORE INTO TABLE test.follows FIELDS TERMINATED BY ' ' LINES TERMINATED BY '\n' (follower, followee);")
cnx.commit()
cursor.execute("LOAD DATA LOCAL INFILE '/tmp/links19.txt' IGNORE INTO TABLE test.follows FIELDS TERMINATED BY ' ' LINES TERMINATED BY '\n' (follower, followee);")
cnx.commit()
cursor.execute("LOAD DATA LOCAL INFILE '/tmp/links20.txt' IGNORE INTO TABLE test.follows FIELDS TERMINATED BY ' ' LINES TERMINATED BY '\n' (follower, followee);")
cnx.commit()
cursor.execute("SET autocommit = 1;")
cursor.execute("SET unique_checks = 1;")
cursor.execute("SET foreign_key_checks = 1")
cnx.close()