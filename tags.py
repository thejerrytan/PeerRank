from list import PeerRank
import random, seed

def main():
	pr = PeerRank()
	topics = seed.SEED.keys()
	random.shuffle(topics)
	for topic in topics:
		pr.get_se_tags(topic)

if __name__ == "__main__":
	main()