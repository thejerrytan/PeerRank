# Infers topics of expertise and obtain rankings for each expert identified on Twitter
from list import PeerRank

def main():
	pr = PeerRank()
	pr.infer_twitter_topics(112227235)

if __name__ == "__main__":
	main()