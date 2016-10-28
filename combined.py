from list import PeerRank

def main():
	pr = PeerRank()
	pr.combine_users()
	pr.combine_topics()

if __name__ == "__main__":
	main()