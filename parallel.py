from list import PeerRank
from key import KeyManager
import threading, mysql.connector, logging

class Counter(object):
	""" Thread-safe counter"""
	def __init__(self, start=0):
		self.lock = threading.Lock()
		self.value = start
	def increment(self):
		logging.debug('Waiting for lock')
		self.lock.acquire()
		try:
			logging.debug('Acquired lock')
			self.value = self.value + 1
		finally:
			self.lock.release()

class BaseWorker(threading.Thread):
	
	def __init__(self, users, group=None, target=None, name=None, args=(), kwargs=None, verbose=None):
		self.local  = threading.local()
		self.pr     = PeerRank()
		# self.pr.__init_sql_connection()
		# self.pr.cursor.execute("SET SESSION net_read_timeout = 3600")
		# self.pr.cursor.execute("SET SESSION net_write_timeout = 3600")
		self.users  = users # shared resource
		threading.Thread.__init__(self, group=group, target=target, name=name, verbose=verbose)