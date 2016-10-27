# Builds inverted index for fast lookup, to be done after infer topics
from list import PeerRank
from time import time
import math, pprint

def main():
	pr = PeerRank()
	pr.build_inverted_index()

if __name__ == "__main__":
	main()