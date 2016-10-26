# Infers topics of expertise and obtain rankings for each expert identified on Twitter
from list import PeerRank
from util import cover_density_ranking
from time import time
import math

def main():
	start     = time()
	pr        = PeerRank()
	docs      = pr.infer_twitter_topics(112227235)
	total     = reduce(lambda x, y: x + docs[y], docs, 0)
	sim_score = 0
	docs_list = [topic for topic, freq in docs.iteritems()]
	ranked_docs = cover_density_ranking("leadership", docs)
	for rank, d in enumerate(ranked_docs):
		sim_score += docs[docs_list[d]]
		print rank+1, docs_list[d]
	sim_score = sim_score * 1.0 / total
	listed_count = pr.get_listed_count_for_twitter_user(112227235)
	ranking_score = sim_score * math.log(listed_count)
	print("Similarity score is : %.2f" % (sim_score))
	print("Ranking score is : %.2f" % (ranking_score))
	print("Time taken %.2f" % (time() - start))

if __name__ == "__main__":
	main()