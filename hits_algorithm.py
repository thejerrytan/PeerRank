import mysql.connector, math, time

def main():
	ITERATIONS = 10000
	iter_count = 0
	cnx = mysql.connector.connect(user='root', password='root', host='104.198.155.210', database='test')
	cursor = cnx.cursor()
	TOTAL = 1000000000
	PER_PAGE = 1000000
	start = 1
	count = 0
	startTime = time.time()
	while iter_count < ITERATIONS:
		print("ITERATION: %d" % iter_count)
		while (start + PER_PAGE - 1) < TOTAL:
			end = start + PER_PAGE - 1
			users = []
			# try:
			cursor.execute("SELECT `id` FROM test.users_for_hits WHERE id BETWEEN %s AND %s LIMIT %s" , (start, end, PER_PAGE))
			for row in cursor:
				users.append(int(row[0]))
			# Calculate authority score
			while len(users) > 0:
				# Find followers
				user = users.pop()
				count += 1
				if count % 100 == 0:
					print("Processed %d users." % count)
					print("Time taken per user: %f" % ((time.time() - startTime) / count))
				cursor.execute("SELECT `follower` FROM test.follows WHERE followee = %s LIMIT 10000000" , (user,))
				auth = 0
				followers = []
				for row in cursor:
					followers.append(str(row[0]))
				query = ','.join(followers)
				if len(followers) == 0:
					auth = 0
				else:
					cursor.execute("SELECT hub FROM test.users_for_hits WHERE id IN (%s)"  % query)
					auth = reduce(lambda x, y: x + int(y[0]), cursor, 0)
				print("Auth score for user %s : %d" % (user, auth))
				cursor.execute("UPDATE test.users_for_hits SET authority = %s WHERE id = %s" % (auth, user))
				cnx.commit()
				# Calculate hub score
				followee = []
				cursor.execute("SELECT followee FROM test.follows WHERE follower = %s LIMIT 10000000" , (user,))
				for row in cursor:
					followee.append(str(row[0]))
				query = ','.join(followee)
				if len(followee) == 0:
					hub = 0
				else:
					cursor.execute("SELECT authority FROM test.users_for_hits WHERE id IN (%s)" % query)
					hub = reduce(lambda x, y: x + int(y[0]), cursor, 0)
				print("Hub  score for user %s : %d" % (user, hub))
				cursor.execute("UPDATE test.users_for_hits SET hub = %s WHERE id = %s" , (hub, user))
				cnx.commit()
			start += PER_PAGE
			# except Exception as e:
			# 	print e
		
		# Normalize
		start = 1
		norm_hub = 0
		norm_auth = 0
		while (start + PER_PAGE -1) < TOTAL:
			end = start + PER_PAGE - 1
			cursor.execute("SELECT hub, authority FROM test.users_for_hits WHERE id BETWEEN %s AND %s LIMIT 1000000" , (start, end))
			norm_hub += reduce(lambda x, y: x + y[0] * y[0], cursor, 0)
			norm_auth += reduce(lambda x, y: x + y[1] * y[1], cursor, 0)
			start += PER_PAGE

		norm_hub = math.sqrt(norm_hub)
		norm_auth = math.sqrt(norm_auth)
		while (start + PER_PAGE - 1) < TOTAL:
			end = start + PER_PAGE - 1
			cursor.execute("UPDATE test.users_for_hits SET hub = (hub / %s), authority = (authority / %s) WHERE id BETWEEN %s AND %s" , (norm_hub, norm_auth, start, end))
			start += PER_PAGE
			cnx.commit()
		# next iteration
		iter_count += 1
	cnx.close()

if __name__=="__main__":
	main()