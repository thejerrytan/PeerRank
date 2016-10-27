# Infers topics of expertise and obtain rankings for each expert identified on Twitter
from list import PeerRank
from time import time
import math, threading, sys
from parallel import BaseWorker, Counter

NUM_THREADS = 5
try:
	SO_FAR      = int(open('twitter_infer_topics.txt', 'r').readline())
except Exception as e:
	SO_FAR      = 0
qlock       = threading.Lock()
count       = Counter(start=SO_FAR)

class InferWorker(BaseWorker):
	def run(self):
		# Acquire qlock
		hasWork = True
		while hasWork:
			qlock.acquire()
			try:
				size = len(self.users)
				if size > 0:
					user = self.users.popleft()
				else:
					self.pr.close()
					hasWork = False
			finally:
				qlock.release()
			if hasWork: 
				topic_vector = self.pr.infer_twitter_topics(user)
				self.pr.insert_topic_vector(user, topic_vector)
				self.pr.sql.commit()
				count.increment()
				if count.value % 100 == 0:
					print("Processed %d users" % count.value)
					with open('twitter_infer_topics.txt', 'w') as f:
						f.write(str(count.value))
					f.close()
		print("Exiting thread %s" % self.name)

def main():
	threads   = []
	start     = time()
	pr        = PeerRank()
	experts   = pr.get_all_twitter_experts(so_far=SO_FAR, close=True)
	for t in range(0, NUM_THREADS):
		thread = InferWorker(experts, name=t)
		threads.append(thread)
		thread.start()
	for t in threads:
		t.join()
	with open('twitter_infer_topics.txt', 'w') as f:
		f.write(str(count.value))
	f.close()
	print("Time taken %.2f" % (time() - start))
	sys.exit(0)

if __name__ == "__main__":
	main()