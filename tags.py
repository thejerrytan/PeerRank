from list import PeerRank
import random, seed

def main():
	pr = PeerRank()
	# topics = seed.SEED.keys()
	topics = ['math.stackexchange.com','graphicdesign.stackexchange.com','space.stackexchange.com','bitcoin.stackexchange.com','history.stackexchange.com','linguistics.stackexchange.com','workplace.stackexchange.com','spanish.stackexchange.com','arduino.stackexchange.com','bicycles.stackexchange.com','programmers.stackexchange.com','islam.stackexchange.com','expatriates.stackexchange.com','cogsci.stackexchange.com','earthscience.stackexchange.com','judaism.stackexchange.com','tex.stackexchange.com','photo.stackexchange.com','salesforce.stackexchange.com','german.stackexchange.com','stats.stackexchange.com','tor.stackexchange.com','expressionengine.stackexchange.com','rpg.stackexchange.com','travel.stackexchange.com','quant.stackexchange.com','sustainability.stackexchange.com','poker.stackexchange.com','gaming.stackexchange.com','parenting.stackexchange.com','sports.stackexchange.com','cs50.stackexchange.com','gardening.stackexchange.com','japanese.stackexchange.com','biology.stackexchange.com','aviation.stackexchange.com','academia.stackexchange.com','security.stackexchange.com']
	random.shuffle(topics)
	for topic in topics:
		pr.get_se_tags(topic)

if __name__ == "__main__":
	main()