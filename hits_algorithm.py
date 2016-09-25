import mysql.connector, math, requests, subprocess, shlex, sys

def main():
	ITERATIONS = 10000
	iter_count = 0
	cnx = mysql.connector.connect(user='root', password='root', host='104.196.149.230', database='test')
	cursor = cnx.cursor()
	TOTAL = 1000000000
	PER_PAGE = 1000000
	start = 1
	while iter_count < ITERATIONS:
		print("ITERATION: %d" % iter_count)
		while (start + PER_PAGE - 1) < TOTAL:
			end = start + PER_PAGE - 1
			users = []
			try:
				cursor.execute("SELECT `user_id` FROM test.users_for_hits WHERE id BETWEEN %d AND %d LIMIT 1000000" % (start, end))
				for row in cursor:
					users.append(int(row[0]))
				# Calculate authority score
				while len(users) > 0:
					# Find followers
					user = users.pop()
					cursor.execute("SELECT `follower` FROM test.follows WHERE followee = %d" % user)
					auth = 0
					followers = []
					for row in cursor:
						followers.append(int(row[0]))
					query = ','.join(followers)
					cursor.execute("SELECT hub FROM test.users_for_hits WHERE id IN (%s)" % query)
					auth = reduce(lambda x, y: x + int(y[0]), cursor, 0)
					cursor.execute("UPDATE test.users_for_hits SET authority = %d WHERE id = %d" % (auth, user))
					cnx.commit()
					# Calculate hub score
					followee = []
					cursor.execute("SELECT followee FROM test.follows WHERE follower = %d" % user)
					for row in cursor:
						followee.append(int(row[0]))
					query = ','.join(followee)
					cursor.execute("SELECT authority FROM test.users_for_hits WHERE id IN (%s)" % query)
					hub = reduce(lambda x, y: x + int(y[0]), cursor, 0)
					cursor.execute("UPDATE test.users_for_hits SET hub = %d WHERE id = %d" % (hub, user))
					cnx.commit()
				start += PER_PAGE
			except Exception as e:
				print e
		
		# Normalize
		start = 1
		norm_hub = 0
		norm_auth = 0
		while (start + PER_PAGE -1) < TOTAL:
			end = start + PER_PAGE - 1
			cursor.execute("SELECT hub, authority FROM test.users_for_hits WHERE id BETWEEN %d AND %d LIMIT 1000000" % (start, end))
			norm_hub += reduce(lambda x, y: x + y[0] * y[0], cursor, 0)
			norm_auth += reduce(lambda x, y: x + y[1] * y[1], cursor, 0)
			start += PER_PAGE

		norm_hub = math.sqrt(norm_hub)
		norm_auth = math.sqrt(norm_auth)
		while (start + PER_PAGE - 1) < TOTAL:
			end = start + PER_PAGE - 1
			cursor.execute("UPDATE test.users_for_hits SET hub = (hub / %d), authority = (authority / %d) WHERE id BETWEEN %d AND %d" % (norm_hub, norm_auth, start, end))
			start += PER_PAGE
			cnx.commit()
		# next iteration
		iter_count += 1
	cnx.close()

if __name__=="__main__":
	main()