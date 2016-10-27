# Infers topics of expertise and obtain rankings for each expert identified on Twitter
from list import PeerRank
from util import cover_density_ranking
from time import time
import math

def main():
	pr        = PeerRank()
	while True:
		print("Enter a query :")
		print(">>>"),
		q = raw_input()
		if q == "exit":
			break
		else:
			start     = time()
			rankings = pr.get_twitter_rankings(q)
			print rankings
			print("Time taken %.2f" % (time() - start))

if __name__ == "__main__":
	main()