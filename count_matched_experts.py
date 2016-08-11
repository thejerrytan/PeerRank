from list import PeerRank
import sys

def main():
	if len(sys.argv) < 2:
		print "Please specify site argument"
		sys.exit(1)
	pr = PeerRank()
	pr.count_matched_experts(sys.argv[1])

if __name__ == "__main__":
	main()