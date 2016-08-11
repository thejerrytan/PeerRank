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
	union = set1 | set2
	# print "union : " + str(union)
	intersect = len(set1 & set2)
	# print "intersect : " + str(intersect)
	jaccard_score = intersect / (len(set1) + len(set2) - intersect)
	print "Score : " + str(jaccard_score)
	return jaccard_score

def pairwise_set(s):
	"""Given a set s of sets, return a generator set of all pairwise combinations of each set in s"""
	return itertools.combinations(s, 2)

def average_jaccard_sim(s):
	"""Given a set s of sets, calculate the average jaccard similiarity score for all pairwise 2-tuple of s"""
	return reduce(lambda x,y : x+y , map(lambda x : jaccard_sim(x[0], x[1]), pairwise_set(s)), 0) / len([x for x in pairwise_set(s)])

def CDR(q, doc_set):
	"""Given a query q and set of documents doc_set, return a ranked doc_set according to most relevant first"""
	ranked_set = set()
	

def cover_density_ranking(q, i, docstring):
	"""Given a query q, and a document, return the cover density score ref:http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.12.1615&rep=rep1&type=pdf"""
	def r(t, k):
		"""returns position of first occurence of term t at or after position k in the term sequence represented by doc"""
		for index, term in enumerate(doc[k:]):
			if term.lower() == t.lower():
				return k + index
		return N + 1

	def l(t, k):
		"""returns position of last occurence of term t located at or before k in the term sequence"""
		if k > len(doc) - 1:
			k = len(doc) - 1
		for index, term in enumerate(doc[k::-1]):
			if term.lower() == t.lower():
				print index, term
				return k - index
		return -1

	def cover(q, i, k):
		print "%d-cover starting at position %d" % (i, k)
		R = []
		L = []
		for j in range(0,len(q)):
			_q_pos = r(q[j], k)
			R.append(_q_pos)
			print "r returns %d " % _q_pos
		_q_pos = sorted(R)[i-1]
		print "q position is: %d " % _q_pos
		q_prime = set()
		for j in range(0, len(q)):
			if R[j] <= _q_pos:
				# print q[j]
				q_prime = q_prime | set([q[j]])
		q_prime = list(q_prime)
		for j in range(0, len(q_prime)):
			_p_pos = l(q_prime[j], _q_pos)
			L.append(_p_pos)
			print "l returns %d " % _p_pos
		_p_pos = sorted(L)[0]
		return (_p_pos, _q_pos)

	def score_cover(cover):
		kappa = 3.0
		if cover[1] - cover[0] + 1 > kappa:
			return kappa / (cover[1] - cover[0] + 1)
		else:
			return 1

	doc = remove_special_chars(docstring.split(' '))
	q = q.split(' ')
	N = len(doc)
	cover_seq = []
	for _index, w in enumerate(doc):
		print _index, w
	print "length of document is: %d " % N
	(p_pos, q_pos) = cover(q, i, 0)
	print (p_pos, q_pos)
	score = 0
	while q_pos <= N:
		score = score + score_cover((p_pos, q_pos)) # score of last cover is not added because it will always not be a minimal cover
		cover_seq.append((p_pos,q_pos))
		(p_pos, q_pos) = cover(q, i, p_pos + 1)
		print (p_pos, q_pos)
		# break

	for (t1,t2) in cover_seq:
		print ' '.join(doc[t1:t2+1])
	return score

def remove_special_chars(doc):
	""" doc is a list"""
	for i, word in enumerate(doc):
		doc[i] = ''.join(e for e in word if e.isalnum())
	return doc

if __name__ == "__main__":
	"""Testing"""
	# Must use frozenset for inner sets, python only accepts immutable elements as set elements
	# print "Testing average_jaccard_sim"
	# a = frozenset(['jonskeet', 'Linus__Torvalds', 'codinghorror'])
	# b = frozenset(['Microsoft', 'JavaScript_Warriors', 'AITay'])
	# c = frozenset(['DavidTanenbaum', 'shanselman', 'AITay', 'codinghorror'])
	# d = frozenset(['jonskeet', 'Linus__Torvalds', 'Microsoft', 'AITay'])

	# score = average_jaccard_sim(set([a,b,c,d]))

	print "Testing cover_density_ranking"
	doc = """
			Erosion 

			It took the sea a thousand years, 
			A thousand years to trace. 
			The granite features of this cliff, 
			In crag and scarp and base. 

			It took the sea an hour one night, 
			An hour of storm to place. 
			The sculpture of these granite seams, 
			Upon a woman's face. 
			--E. J. Pratt (1882- 1964)
		  """
	q1 = "sea thousand years"
	ranking_score = cover_density_ranking(q1, 3, doc.strip())
	print "score : %.2f" % ranking_score