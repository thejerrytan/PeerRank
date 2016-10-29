import os, json
from datetime import datetime
from random import shuffle

class ExceededTransactionLimitException(Exception):
	def __init__(self, message, response):
		self.message = message
		self.response = response
	def __str__(self):
		return repr(self.message)

class KeyManager:
	def __init__(self, api, filepath, mode=None, renew=60*15):
		"""
			String  api      - name to describe the api this keymanager is used for, e.g. Twitter Search API
			String  filepath - filepath relative to this file to the key file
			String  mode     - 'arr' for array representation by default, 'dict' representation for anything else
			Integer renew    - number of seconds after lastChecked time to switch invalid keys to valid, depends on API rate limit
		"""
		self.api          = api
		self.mode         = 'arr' if mode is None or 'arr' else 'dict'
		self.renewal_time = renew
		self.dictRepr = json.loads(open(os.path.join(os.path.dirname(__file__), filepath)).read())[api]
		for key in self.dictRepr:
			self.dictRepr[key]['valid'] = True
			self.dictRepr[key]['lastChecked'] = datetime.now()
		self.arrRepr = [value for value in self.dictRepr.values()]
		shuffle(self.arrRepr)
		self.key     = self.arrRepr[0] if self.mode == 'arr' else self.dictRepr.itervalues().next()

	# Test if key has exceeded daily transaction limit
	def test_key(self):
		# raise ExceededTransactionLimitException(response['statusInfo'], response)
		return True

	def get_key(self):
		return self.key

	def invalidate_key(self):
		"""
			Call this function when it is clear the current key has reached its API limit, 
			for e.g. an Exception was raised from the API call. Note that it does not change key.
		"""
		self.key['valid'] = False
		self.key['lastChecked'] = datetime.now()

	def change_key(self):
		""" Change key and prints number of valid keys left"""
		count = 0
		if self.mode == 'arr':
			for key in self.arrRepr:
				# mark current apikey as invalid
				if self.__is_current_key(key):
					key['valid']       = False
					key['lastChecked'] = datetime.now()
				# reset invalid keys to valid if time since lastChecked is > renew
				if not key['valid']:
					tdelta = datetime.now() - key['lastChecked']
					if tdelta.seconds > self.renewal_time:
						key['valid'] = True

			# change to the next valid key
			switched = False
			for key in self.arrRepr:
				if key['valid']:
					count += 1
					if not switched:
						self.key = key
						switched = True
		else:
			for value in self.dictRepr.itervalues():
				if self.__is_current_key(value):
					value['valid'] = False
					value['lastChecked'] = datetime.now()
				if not value['valid']:
					tdelta = datetime.now() - value['lastChecked']
					if tdelta.seconds > self.renewal_time:
						value['valid'] = True
			switched = False
			for value in self.dictRepr.itervalues():
				if value['valid']:
					count += 1
					if not switched:
						self.key = value
						switched = True

		print("%s changed key, valid keys remaining: %d" % (self.api, count))

	def __is_current_key(self, key):
		return True if self.key == key else False

	def __is_valid_key(self, key):
		return self.key['valid']