from __future__ import division
import itertools

def paginate(iterable, page_size):
	i1, i2 = itertools.tee(iterable)
	while True:
		iterable, page = (itertools.islice(i1, page_size, None), list(itertools.islice(i2, page_size)))
		if len(page)==0:
			break
		yield page

def jaccard_sim(set1, set2):
	# print "Set 1 : " + str(set1)
	# print "Set 2 : " + str(set2)

	union = set1 | set2
	# print "union : " + str(union)
	intersect = len(set1 & set2)
	# print "intersect : " + str(intersect)
	jaccard_score = intersect / (len(set1) + len(set2) - intersect)
	print "Score : " + str(jaccard_score)
	return jaccard_score

def pairwise_set(s):
	"""
	Given a set s of sets, return a generator set of all pairwise combinations of each set in s
	"""
	return itertools.combinations(s, 2)

def average_jaccard_sim(s):
	"""
	Given a set s of sets, calculate the average jaccard similiarity score for all pairwise 2-tuple of s
	"""
	# x = [pair for pair in pairwise_set(s)]
	# if len(x) == 0: # Guard against division by zero
		# return 0
	return reduce(lambda x,y : x+y , map(lambda x : jaccard_sim(x[0], x[1]), pairwise_set(s)), 0) / len([x for x in pairwise_set(s)])

if __name__ == "__main__":
	"""
	Testing
	"""
	# Must use frozenset for inner sets, python only accepts immutable elements as set elements
	a = frozenset(['jonskeet', 'Linus__Torvalds', 'codinghorror'])
	b = frozenset(['Microsoft', 'JavaScript_Warriors', 'AITay'])
	c = frozenset(['DavidTanenbaum', 'shanselman', 'AITay', 'codinghorror'])
	d = frozenset(['jonskeet', 'Linus__Torvalds', 'Microsoft', 'AITay'])

	score = average_jaccard_sim(set([a,b,c,d]))
	print score