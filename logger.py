import time, json

class Logger:
	def __init__(self, filename=None):
		self.LOG_INTERVAL = 100 # Number of keys processed before saving log to disk
		self.dir = './log'
		self.ext = '.log'
		self.__log = {'time_started': time.time()}
		if filename is not None: self.open_log_file(filename)

	def __create_log_file(self, filename):
		"""Create new log file if no such file exists"""
		self.log_file = open(self.dir + '/' + filename + self.ext ,'w')
		self.__log = {
			'process': filename,
			'time_started': time.time(),
			'num_keys_processed': 0
		}
		json.dump(self.__log, self.log_file, indent=4)

	def open_log_file(self, filename):
		try:
			self.log_file = open(self.dir + '/' + filename + self.ext, 'r+')
			self.__log = json.load(self.log_file)
			self.__log['time_started'] = time.time()
		except IOError as e:
			print e
			self.__create_log_file(filename)

	def log(self, **kw):
		if kw is not None:
			self.__log.update(kw)
		self.log_file.seek(0)
		json.dump(self.__log, self.log_file, indent=4)
		self.log_file.truncate()

	def get_value(self, key):
		if key in self.__log:
			return self.__log[key]
		else:
			return None

	def close(self):
		"""Close system resources"""
		self.log_file.close()
