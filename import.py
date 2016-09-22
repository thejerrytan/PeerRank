import mysql.connector

cnx = mysql.connector.connect(user='root', password='root', host='104.196.149.230', database='test')
cursor = cnx.cursor()

f = open('/Volumes/Mac/data/links-anon.txt', 'r', 1)
id_set = []
count = 0
skip = temp = 31000
for line in f:
	if temp < skip:
		temp += 1
		continue
	skip += 1
	(id_1, id_2) = line.split(' ')
	id_set.append((id_1.strip('\n'),))
	id_set.append((id_2.strip('\n'),))
	try:
		cursor.execute("INSERT INTO test.users (id) VALUES (%s)", id_set[0])
	except mysql.connector.errors.IntegrityError as e:
		key = e.__str__().split('for')[0].split('entry')[1].strip(' ').strip('\'')
		# print("Removed duplicate %s " % key)
	try:
		cursor.execute("INSERT INTO test.users (id) VALUES (%s)", id_set[1])
	except mysql.connector.errors.IntegrityError as e:
		key = e.__str__().split('for')[0].split('entry')[1].strip(' ').strip('\'')
		# print("Removed duplicate %s " % key)
	count += 1
	if count % 100 == 0: 
		print("Inserted %d" % count)
		print("Lines processed: %d" % skip)
		cnx.commit() # Periodic commits
	id_set = []

f.close()
cnx.close()