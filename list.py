#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pprint, sys, time, json, seed, random, httplib, logger, signal, urllib, os, socket, math
import jellyfish, redis, tweepy
sys.path.append(os.path.join(os.path.dirname(__file__), 'Py-StackExchange'))
import stackexchange
from util import *
# from skimage.transform import *
from skimage.io import *
from image_match.goldberg import ImageSignature
# from matplotlib import pyplot as plt
from tweepy.error import TweepError
from tweepy.error import RateLimitError
from tweepy import OAuthHandler, API, Cursor
from urllib2 import HTTPError, URLError
# from collections import deque
from key import KeyManager

class PeerRank:
	DEVELOPERS_THRES    = 100
	NAME_SEARCH_FILTER  = 10
	NAME_JARO_THRES     = 0.80
	LOC_JARO_THRES      = 0.90
	IMG_SIM_THRES       = 0.50
	TOTAL_MATCHED_ACC   = 0

	# SO_CLIENT_SECRET  = 'AjN*KCYPu9qFontnH1T7Fw(('
	# SO_CLIENT_KEY     = 'PlqChK)JFcqzNx23OZe30Q((' # LIVE version
	SO_CLIENT_KEY       = '4wBVVG2jcCrwIUbUZjHlEQ((' # DEV version 

	LAST_CRAWL_INTERVAL = 0 # Duration since last crawl such that data is deemed stale and a new crawl is required
	ENV        = json.loads(open(os.path.join(os.path.dirname(__file__), 'env.json')).read())
	MYSQL_HOST = ENV['MYSQL_HOST'] if socket.gethostname() != ENV['INSTANCE_HOSTNAME'] else "localhost"
	MYSQL_USER = ENV['MYSQL_USER']
	MYSQL_PW   = ENV['MYSQL_PW']
	MYSQL_PORT = ENV['MYSQL_PORT']
	MYSQL_DB   = ENV['MYSQL_DB']
	STOPWORDS  = ["Twitter", "List", "Formulist", "Follow", "Follow-back"]
	def __init__(self, se_site='stackoverflow.com'):
		self.logger            = logger.Logger()
		self.twitter_km        = KeyManager('Twitter-Search-v1.1', 'keys.json')
		self.so                = stackexchange.Site(se_site, PeerRank.SO_CLIENT_KEY, impose_throttling=True)
		self.__init_twitter_api()
		self.r                 = redis.Redis(db=0)
		self.r_tags            = redis.Redis(db=1)
		self.r_se_experts      = redis.Redis(db=2)
		self.r_q_topics        = redis.Redis(db=3)
		self.r_q_experts       = redis.Redis(db=4)
		self.r_combined        = redis.Redis(db=5)
		self.r_combined_topics = redis.Redis(db=6)
		self.r_twitter_lookup  = redis.Redis(db=7)
		self.total_matched     = 0
		self.start_time        = time.time()

	def __init_sql_connection(self):
		import mysql.connector
		self.sql    = mysql.connector.connect(user=PeerRank.MYSQL_USER, password=PeerRank.MYSQL_PW, host=PeerRank.MYSQL_HOST, database=PeerRank.MYSQL_DB, charset='utf8mb4', collation='utf8mb4_general_ci', get_warnings=True)
		self.cursor = self.sql.cursor()

	def __init_twitter_api(self):
		auth = OAuthHandler(self.twitter_km.get_key()['consumer_key'], self.twitter_km.get_key()['consumer_secret'])
		auth.set_access_token(self.twitter_km.get_key()['access_token_key'], self.twitter_km.get_key()['access_token_secret'])
		self.api = API(auth_handler=auth, wait_on_rate_limit=False, wait_on_rate_limit_notify=True)

	def __serialize_se_tag(self, tag):
		"""Takes a stackexchange tag object and returns the keys that are allowed before storage into Redis"""
		tag              = tag.json
		new_tag          = {}
		new_tag['name']  = tag['name']
		new_tag['count'] = tag['count']
		new_tag['site']  = tag['_params_']['site']
		return new_tag

	def change_se_site(self, se_site):
		self.so = stackexchange.Site(se_site, SO_CLIENT_KEY, impose_throttling=True)

	def print_time_taken_for_user(self, user):
		print "Time taken for user: %20s %.2fs" % (user, (time.time() - self.start_time))

	def reset_start_time(self):
		self.start_time = time.time()

	def get_matching_so_profile(self, user):
		"""User must be a dict containing screen_name, name, location and profile_image_url"""
		result = []
		matches = self.compare_name_string(user['screen_name'], user['name'])
		for i, u in enumerate(matches):
			img_sim = self.compare_image(user['profile_image_url'], u.profile_image)
			try:
				loc_sim = self.compare_location(user['location'], u.location)
			except (AttributeError, KeyError) as e: # Twitter's location field is optional
				loc_sim = 0
			matches[i] = (u, img_sim, loc_sim)
		matches = sorted(matches, cmp=lambda x, y: cmp(x[1], y[1]))
		matches = filter(lambda x: x[1] < PeerRank.IMG_SIM_THRES, matches)
		return matches[0][0] if len(matches) == 1 else None

	def is_matching_twitter_profile(self, twitter_user, src_user):
		"""se_user must be a dict containing screen_name, name, location and profile_image_url"""
		if 'profile_image_url' in src_user:
			src_profile_img = src_user['profile_image_url']
		elif 'profile_image' in src_user:
			src_profile_img = src_user['profile_image']
		else:
			src_profile_img = None
		if 'display_name' in src_user:
			src_name = src_user['display_name']
		else:
			src_name = src_user['name']

		if self.compare_name_string_se(twitter_user['screen_name'], src_name):
			img_sim = self.compare_image(twitter_user['profile_image_url'], src_profile_img)
			print "       IMG_SIM : %.2f" % img_sim,
			if 'location' in twitter_user and 'location' in src_user:
				loc_sim = self.compare_location(twitter_user['location'], src_user['location'])
				print "       LOC_SIM : %.2f" % loc_sim
			print
			return True if img_sim < PeerRank.IMG_SIM_THRES else False
		print
		return False

	def compare_location(self, twitter_loc, so_loc):
		score = jellyfish.jaro_winkler(unicode(twitter_loc), unicode(so_loc))
		return score

	def plot_image(self, twitter_url, so_url):
		"""
		Given twitter profile image url and stackexchange profile image url, show image to user.
		Only for use on develop environment.
		"""
		t   = imread(twitter_url)
		so  = imread(so_url)
		fig = plt.figure("Twitter v.s. StackOverflow")
		ax  = fig.add_subplot(1,3,1)
		ax.set_title("Twitter")
		plt.imshow(t)
		ax  = fig.add_subplot(1,3,2)
		ax.set_title("StackOverflow")
		plt.imshow(so)
		plt.show(block=False)
		
	def compare_image(self, twitter_url, so_url):
		# self.plot_image(twitter_url, so_url)
		gis = ImageSignature()
		try:
			t_sig  = gis.generate_signature(twitter_url)
			so_sig = gis.generate_signature(so_url)
		except Exception as e:
			# 404 File not found errors
			print e
			return 1.0 # Most dissimilar score
		return gis.normalized_distance(t_sig, so_sig)

	def compare_name_string(self, screen_name, name):
		"""Compare name string for use when matching Twitter experts to SE accounts"""
		try:
			matches = self.so.users_by_name(unicode(name, "utf-8"))
		except (URLError, stackexchange.core.StackExchangeError) as e:
			print e
			matches = []
		result = []
		if len(matches) < PeerRank.NAME_SEARCH_FILTER:
			for m in matches:
				score = jellyfish.jaro_winkler(unicode(name, "utf-8"), m.display_name)
				if score > PeerRank.NAME_JARO_THRES:
					result.append(m)
		return result

	def compare_name_string_se(self, screen_name, so_name):
		"""Compare name string for use when matching SE experts to Twitter accounts. Returns boolean"""
		score = jellyfish.jaro_winkler(unicode(so_name, "utf-8"), screen_name)
		return True if score > PeerRank.NAME_JARO_THRES else False

	def deserialize_twitter_user(self, twitter):
		"""
		Take a remote redis user account hash, retrieves keys prefixed with twitter OSN, and removes the prefix, returns a dict
		"""
		key_prefix = "twitter_"
		allowed_keys = ['id', 'name', 'screen_name', 'description', 'profile_image_url', 'location', 'listed_count', 'created_at', 'verified']
		result = {}
		for k, v in twitter.iteritems():
			if k.startswith(key_prefix):
				result[k[len(key_prefix):]] = v
		return result

	def deserialize_so_user(self, so):
		"""Take a remote redis user account hash, retrieves keys prefixed with twitter OSN, and removes the prefix, returns a dict"""
		key_prefix = "so_"
		allowed_keys = ['id','account_id', 'user_id', 'display_name', 'profile_image', 'location', 'reputation', 'url', 'link', 'creation_date']
		result = {}
		for k, v in so.iteritems():
			if k.startswith(key_prefix):
				result[k[len(key_prefix):]] = v
		return result

	def deserialize_q_user(self, q):
		key_prefix = 'q_'
		allowed_keys = ['name','profile_image_url','num_views','short_description','num_answers']
		result = {}
		for k, v in q.iteritems():
			if k.startswith(key_prefix):
				result[k[len(key_prefix):]] = v
		return result

	def serialize_and_flatten_twitter_user(self, twitter):
		"""
		Flatten (remove nested objects and dicts) Twitter user json dict and returns a dict of key : value for insert into REDIS
		Add a prefix to each key corresponding to the social network for namespacing
		Add timestamp of last modified time
		"""
		key_prefix   = "twitter_"
		allowed_keys = ['id', 'name', 'screen_name', 'description', 'profile_image_url', 'location', 'listed_count', 'created_at', 'verified']
		result = {}
		for k in allowed_keys:
			try:
				result[key_prefix+k] = twitter[k]
			except KeyError as e:
				pass
		result['twitter_last_crawled'] = time.time()
		return result

	def serialize_and_flatten_so_user(self, so):
		"""
		Flatten (remove nested objects and dicts) StackOverflow user json dict and returns a dict of key: value for insert into REDIS
		Add a prefix to each key corresponding to the social network for namespacing
		Add timestamp of last modified time
		"""
		key_prefix = "so_"
		allowed_keys = ['id','account_id', 'user_id', 'display_name', 'profile_image', 'location', 'reputation', 'url', 'link', 'creation_date']
		result = {}
		for k in allowed_keys:
			try:
				result[key_prefix+k] = so[k]
			except KeyError as e:
				pass
		result['so_last_crawled'] =  time.time()
		return result

	def serialize_and_flatten_q_user(self, q):
		"""
		Flatten (remove nested objects and dicts) Quora user json dict and returns a dict of key: value for insert into REDIS
		Add a prefix to each key corresponding to the social network for namespacing
		Add timestamp of last modified time
		"""
		key_prefix = "q_"
		allowed_keys = ['name','profile_image_url','num_views','short_description','num_answers']
		result = {}
		for k in allowed_keys:
			try:
				result[key_prefix+k] = q[k]
			except KeyError as e:
				pass
		result['q_last_crawled'] =  time.time()
		return result

	def twitter_to_stackexchange(self, users):
		for k, v in users.iteritems():
			# Process twitter account
			r_acct = self.r.hgetall(k) # Remote account
			r_user = {} 		  # Local account which we will push later on
			if ('twitter_last_crawled' in r_acct and (time.time() - float(r_acct['twitter_last_crawled']))) >  PeerRank.LAST_CRAWL_INTERVAL:
				# Update twitter user profile info
				try:
					user   = self.api.get_user(screen_name=k)
					r_user.update(self.serialize_and_flatten_twitter_user(user._json))
				except RateLimitError as e:
					print e
					self.twitter_km.invalidate_key()
					self.twitter_km.change_key()
					self.__init_twitter_api()
				except TweepError as e:
					print e
			else:
				# Preserve old twitter user profile data, so_ prefixed keys will be overwritten or preserved later on
				print "Skipped getting Twitter user profile for user %s" % k
				r_user = r_acct
			# Process StackOverflow account
			self.reset_start_time()
			so_user = None
			if len(r_acct) != 0:
				if (r_acct['so_display_name'] == 'None' and 'so_last_crawled' not in r_acct) or (time.time() - float(r_acct['so_last_crawled'])) > PeerRank.LAST_CRAWL_INTERVAL:
					twitter_acct = self.deserialize_twitter_user(r_acct)
					try:
						so_user = self.get_matching_so_profile(twitter_acct)
						time.sleep(1)
					except UnicodeDecodeError as e:
						print str(e) + str(twitter_acct['name'])
					if so_user is not None:
						print "Twitter(" + k + ") -> StackOverflow(" + so_user.display_name + ")"
						r_user.update(self.serialize_and_flatten_so_user(so_user.__dict__))
						# pprint.pprint(r_user)
					else:
						# Set the last crawled date
						r_user.update({'so_last_crawled' : time.time()})
				else:
					print "Skipped getting StackOverflow user profile for user %s" % k
			# Save into DB
			self.r.hmset(k, r_user)
			self.total_matched = self.total_matched + 1 if so_user is not None else self.total_matched
			self.print_time_taken_for_user(k)
			users[k]['so_user'] = so_user.__dict__ if so_user is not None else None
		return users

	def search_similar_twitter_acct(self, seed_user):
		q = deque(seed_user)
		results = {}
		count = 0
		list_set = []
		while len(results) < DEVELOPERS_THRES and len(q)!=0:
			user = q.popleft()
			# print "Expert: " + user
			list_count = 0
			try:
				for pg in Cursor(self.api.lists_memberships, screen_name=user).pages(1):
					for l in pg:
						list_count += 1
						try:
							member_list = []
							for member_pg in Cursor(self.api.list_members, l.user.screen_name, l.slug).pages(1):
								for member in member_pg[0:20]:
									member_list.append(member.screen_name)
									if member.screen_name not in results:
										print "%20s" % member.screen_name,
										count += 1
										if count % 5 == 0:
											print ''
										new_member = {'so_display_name' : None}
										new_member.update(self.serialize_and_flatten_twitter_user(member._json))
										q.append(new_member)
										results[member.screen_name] = new_member
										self.r.hmset(member.screen_name, new_member)
							list_set.append(frozenset(member_list))
						except RateLimitError as e:
							print e
							self.twitter_km.invalidate_key()
							self.twitter_km.change_key()
							self.__init_twitter_api()
						except TweepError as e:
							print e
							continue
						# print "List : " + l.name + " done"
					# print "Number of lists : " + str(list_count)
			except RateLimitError as e:
				print e
				self.twitter_km.invalidate_key()
				self.twitter_km.change_key()
				self.__init_twitter_api()
			except TweepError as e:
				# Read time out etc.
				print e
		print ''
		score = average_jaccard_sim(set(list_set))
		print "Average Jaccard-sim score : " + str(score)
		return results

	def get_se_tags(self, site):
		"""Get all tags for stackexchange site and store into Redis"""
		print "Getting tags for site %s" % site
		try:
			self.change_se_site(site)
			tags = self.so.tags()
			count = 1
			for tag in tags:
				tag.name = self.__add_se_namespace(site, tag.name)
				print str(count) + ' ' + tag.name + ' ' + str(tag.count)
				count += 1
				self.r_tags.hmset(tag.name, self.__serialize_se_tag(tag))
			time.sleep(10) # Backoff throttle
		except stackexchange.core.StackExchangeError as e:
			print e
			pass
		return

	def __add_se_namespace(self, site, key):
		"""Add stackexchange site prefix to key, before inserting into redis as namespace"""
		return site + ":" + key

	def __get_namespace_from_key(self, key, index):
		"""Takes a redis key of the form site:content and returns site or content depending on index"""
		return key.split(':')[index]

	def get_experts_from_se(self):
		"""
			Get experts starting from StackExchange, using top answerers from every tag (topic), and map to their Twitter acct
			Run this at the start, and once a week subsequently to update changes in reputation.
		"""
		def save_on_interrupt(signum, frame):
			self.logger.log(num_keys_processed=self.count, time_terminated=time.time(), time_logged=time.time(), process=sys._getframe().f_code.co_name, exception='')
			self.logger.close()
			sys.exit(0)
		for sig in (signal.SIGINT, signal.SIGSEGV, signal.SIGTERM):
			signal.signal(sig, save_on_interrupt)
		self.logger.open_log_file(sys._getframe().f_code.co_name)
		skip = self.logger.get_value('num_keys_processed')
		skip = 0 if skip is None else skip
		self.count = 0
		try:
			for t in self.r_tags.scan_iter():
				try:
					if self.count < skip:
						print "Skipped %s" % t
						self.count += 1
						continue
					site_str = self.__get_namespace_from_key(t, 0)
					site = stackexchange.Site(site_str, SO_CLIENT_KEY, impose_throttling=True)
					tag = stackexchange.models.Tag(self.r_tags.hgetall(t), site)
					topic = site_str.split('.')[0] + ' ' + tag.name
					print "Getting top experts for: %s (%d)" % (tag.name, self.count)
					a_count = 0
					top_answerers = tag.top_answerers('all_time')
					for topuser in top_answerers:
						a_count += 1
						user = topuser.user.__dict__
						try:
							print '    ' + str(a_count) + ' ' + user['display_name'].encode('ascii','ignore')
						except (UnicodeDecodeError, UnicodeEncodeError) as e:
							print '    ' + e
						user = self.serialize_and_flatten_so_user(user)
						user['so_last_crawled'] = time.time()
						# Only add if user is matched to a Twitter account
						if self.r_se_experts.sismember("set:stackexchange:matched_experts_set", site_str + ":" + user['so_display_name']):
							name = "stackexchange:" + user['so_display_name']
							self.r_combined_topics.zadd("stackexchange:" + topic, name, float(user['so_reputation']))
						self.r_se_experts.hmset(site_str + ':' + user['so_display_name'], user)
						self.r_se_experts.sadd("topics:" + site_str + ':' + user['so_display_name'], t)
					time.sleep(5)
					if self.count % self.logger.LOG_INTERVAL == 0: self.logger.log(num_keys_processed=self.count, time_logged=time.time(), exception='')
				except Exception as e:
					print e # Continue to next tag
					self.logger.log(num_keys_processed=self.count, time_terminated=time.time(), time_logged=time.time(), exception=repr(e) + e.__str__(), process=sys._getframe().f_code.co_name)
				self.count += 1
		except Exception as e:
			print e # unhandled exceptions will terminate program
			self.logger.log(num_keys_processed=self.count, time_terminated=time.time(), time_logged=time.time(), exception=repr(e) + e.__str__(), process=sys._getframe().f_code.co_name)
			self.logger.close()

	def stackexchange_to_twitter(self):
		# closure to ensure logger has context
		def save_on_interrupt(signum, frame):
			self.logger.log(num_keys_processed=self.count, time_terminated=time.time(), time_logged=time.time(), process=sys._getframe().f_code.co_name, exception='')
			self.logger.close()
			sys.exit(0)
		for sig in (signal.SIGINT, signal.SIGSEGV, signal.SIGTERM):
			signal.signal(sig, save_on_interrupt)
		print "Name search filter              : %d"       % PeerRank.NAME_SEARCH_FILTER
		print "Name jaro-winkler sim threshold : %.2f"     % PeerRank.NAME_JARO_THRES
		print "Image similarity threshold      : %.2f"     % PeerRank.IMG_SIM_THRES
		self.logger.open_log_file(sys._getframe().f_code.co_name)
		skip = self.logger.get_value('num_keys_processed')
		skip = 0 if skip is None else skip
		self.count = 0
		try:
			for user in self.r_se_experts.scan_iter():
				if self.count < skip:
					self.count += 1
					continue
				print "Matching for StackExchange user: %s (%.2f)" % (user, self.count)
				self.reset_start_time()
				try:
					for t_user in self.api.search_users(q=self.__get_namespace_from_key(user, 1))[0:PeerRank.NAME_SEARCH_FILTER]:
						u_hash = self.deserialize_so_user(self.r_se_experts.hgetall(user))
						matches = []
						print "    Possible candidate: %20s" % t_user.screen_name,
						if self.is_matching_twitter_profile(t_user._json, u_hash):
							matches.append(t_user)
						u_hash = self.serialize_and_flatten_so_user(u_hash)
						u_hash['twitter_last_crawled'] = time.time()
						if len(matches) is 1:
							# Found
							u_hash.update(self.serialize_and_flatten_twitter_user(matches[0]._json))
							print "Matched twitter account: %20s" % matches[0].screen_name 
						else:
							pass
						self.r_se_experts.hmset(user, u_hash)
					self.print_time_taken_for_user(user)
					if self.count % self.logger.LOG_INTERVAL == 0: self.logger.log(num_keys_processed=self.count, time_logged=time.time(), exception='')
					self.count += 1
					print
					time.sleep(1) # throttling to avoid RateLimitError
				except RateLimitError as e:
					print e
					self.twitter_km.invalidate_key()
					self.twitter_km.change_key()
					self.__init_twitter_api()
				except TweepError as e:
					print e
					continue
		except Exception as e:
			self.logger.log(num_keys_processed=self.count, time_terminated=time.time(), time_logged=time.time(), exception=repr(e) + e.__str__(), process=sys._getframe().f_code.co_name)
			self.logger.close()

	def find_self_declared_link(self):
		"""Quora user profile loads Twitter links asynchronously, to be implemented"""
		pass

	def rename_keys(self):
		"""Use this to rename keys in redis database to a desired key prefix"""
		for k in self.r_q_experts.scan_iter():
			if not k.startswith("quora:topics"):
				username = k.split(':')[-1]
				try:
					self.r_q_experts.rename(k, "quora:expert:%s" % username)
				except redis.exceptions.ResponseError as e:
					print e

	def quora_to_twitter(self, key_pattern='quora:expert:*'):
		# closure to ensure logger has context
		def save_on_interrupt(signum, frame):
			self.logger.log(num_keys_processed=self.count, time_terminated=time.time(), time_logged=time.time(), process=sys._getframe().f_code.co_name, exception='')
			self.logger.close()
			sys.exit(0)
		for sig in (signal.SIGINT, signal.SIGSEGV, signal.SIGTERM):
			signal.signal(sig, save_on_interrupt)
		print "Name search filter              : %d"       % PeerRank.NAME_SEARCH_FILTER
		print "Name jaro-winkler sim threshold : %.2f"     % PeerRank.NAME_JARO_THRES
		print "Image similarity threshold      : %.2f"     % PeerRank.IMG_SIM_THRES
		self.logger.open_log_file(sys._getframe().f_code.co_name)
		skip = self.logger.get_value('num_keys_processed')
		skip = 0 if skip is None else skip
		self.count = 0
		try:
			for user in self.r_q_experts.scan_iter(match=key_pattern):
				if self.count < skip:
					self.count += 1
					continue
				print "Matching for Quora user: %s (%.2f)" % (user, self.count)
				self.reset_start_time()
				try:
					for t_user in self.api.search_users(q=self.__get_namespace_from_key(user, 2))[0:PeerRank.NAME_SEARCH_FILTER]:
						u_hash = self.deserialize_q_user(self.r_q_experts.hgetall(user))
						matches = []
						print "    Possible candidate: %20s" % t_user.screen_name,
						if self.is_matching_twitter_profile(t_user._json, u_hash):
							matches.append(t_user)
						u_hash = self.serialize_and_flatten_q_user(u_hash)
						u_hash['twitter_last_crawled'] = time.time()
						if len(matches) is 1:
							# Found
							u_hash.update(self.serialize_and_flatten_twitter_user(matches[0]._json))
							print "Matched twitter account: %20s" % matches[0].screen_name 
						else:
							pass
						self.r_q_experts.hmset(user, u_hash)
					self.print_time_taken_for_user(user)
					if self.count % self.logger.LOG_INTERVAL == 0: self.logger.log(num_keys_processed=self.count, time_logged=time.time(), exception='')
					self.count += 1
					print
				except RateLimitError as e:
					print e
					self.twitter_km.invalidate_key()
					self.twitter_km.change_key()
					self.__init_twitter_api()
				except TweepError as e:
					print e
					continue
		except Exception as e:
			print e
			self.logger.log(num_keys_processed=self.count, time_terminated=time.time(), time_logged=time.time(), exception=repr(e) + e.__str__(), process=sys._getframe().f_code.co_name)
			self.logger.close()

	def count_matched_experts(self, site):
		"""Returns count of matched experts for a given Site, and adds matched expert to matched_expert_set in respective db"""
		if site.lower() == 'quora':
			db = self.r_q_experts
			key_namespace = 'quora:expert:*'
			matched_experts_coll = 'quora:matched_experts_set'
		elif site.lower() == 'stackexchange':
			db = self.r_se_experts
			key_namespace = '*.com:*'
			matched_experts_coll = 'set:stackexchange:matched_experts_set'
		else:
			raise PeerRankError('Invalid site argument')
		count = 0
		num_keys = 0
		for user in db.scan_iter(match=key_namespace):
			if not user.startswith("topics"): # filter out user topics set
				twitter_acct = db.hget(user, 'twitter_screen_name')
				num_keys += 1
				if twitter_acct is not None:
					db.sadd(matched_experts_coll, user)
					count += 1
		print "Total key count: %d" % num_keys
		print "Total matched %s experts : %d in %.2fs" % (site, count, (time.time() - self.start_time))

	def combine_users(self):
		""" Combine all linked accounts into 1 db, with site namespaced keys for O(1) retrieval """
		for k in self.r.scan_iter():
			so_display_name = self.r.hget(k, 'so_display_name')
			if so_display_name is not None and so_display_name != "None":
				self.r_combined.hmset("twitter:"+k, {"so_display_name" : so_display_name})
		for k in self.r_se_experts.scan_iter():
			if not k.startswith("topics") and not k.startswith('set'):
				twitter_screen_name = self.r_se_experts.hget(k, "twitter_screen_name")
				if twitter_screen_name is not None:
					self.r_combined.hmset("stackexchange:"+k.split(':')[1], {"twitter_screen_name" : twitter_screen_name})
		for k in self.r_q_experts.scan_iter(match="quora:expert:*"):
			twitter_screen_name = self.r_q_experts.hget(k, "twitter_screen_name")
			quora_name = k.split(':')[2]
			if twitter_screen_name is not None:
				self.r_combined.hmset("quora:"+quora_name, {"twitter_screen_name" : twitter_screen_name})
				self.r_combined.hset("twitter:"+twitter_screen_name, "quora_name", quora_name)

	def combine_topics(self):
		""" 
			For every topic, store all ranked users in that topic in a zset sorted by score.
			This is used to populate the db which will be used for the query-based ranking algorithm 
		"""
		def save_on_interrupt(signum, frame):
			self.logger.log(num_keys_processed=self.count, time_terminated=time.time(), time_logged=time.time(), process=sys._getframe().f_code.co_name, exception='')
			self.logger.close()
			sys.exit(0)
		for sig in (signal.SIGINT, signal.SIGSEGV, signal.SIGTERM):
			signal.signal(sig, save_on_interrupt)
		self.logger.open_log_file(sys._getframe().f_code.co_name)
		skip = self.logger.get_value('num_keys_processed')
		skip = 0 if skip is None else skip
		self.count = 0
		# For stackexchange topics
		for t in self.r_tags.scan_iter():
			try:
				if self.count < skip:
					print "Skipped %s" % t
					self.count += 1
					continue
				site_str = self.__get_namespace_from_key(t, 0)
				site = stackexchange.Site(site_str, SO_CLIENT_KEY, impose_throttling=True)
				tag = stackexchange.models.Tag(self.r_tags.hgetall(t), site)
				topic = site_str.split('.')[0] + ' ' + tag.name
				print "Getting top experts for: %s (%d)" % (tag.name, self.count)
				a_count = 0
				top_answerers = tag.top_answerers('all_time')
				for topuser in top_answerers:
					a_count += 1
					user = topuser.user.__dict__
					try:
						print '    ' + str(a_count) + ' ' + user['display_name'].encode('ascii','ignore')
					except (UnicodeDecodeError, UnicodeEncodeError) as e:
						print '    ' + e
					user = self.serialize_and_flatten_so_user(user)
					# Only add if user is matched to a Twitter account
					if self.r_se_experts.sismember("set:stackexchange:matched_experts_set", site_str + ":" + user['so_display_name']):
						name = "stackexchange:" + user['so_display_name']
						self.r_combined_topics.zadd("stackexchange:"+topic, name, float(user['so_reputation']))
				time.sleep(5)
				if self.count % self.logger.LOG_INTERVAL == 0: self.logger.log(num_keys_processed=self.count, time_logged=time.time(), exception='')
			except Exception as e:
				print e # Continue to next tag
				self.logger.log(num_keys_processed=self.count, time_terminated=time.time(), time_logged=time.time(), exception=repr(e) + e.__str__(), process=sys._getframe().f_code.co_name)
			self.count += 1

		# For quora topics
		matched_quora_experts = self.r_q_experts.smembers("quora:matched_experts_set")
		for expert in matched_quora_experts:
			name    = expert.split(":")[2]
			profile = self.r_q_experts.hgetall(expert)
			topics  = self.r_q_experts.smembers("quora:topics:" + name)
			q_name = "quora:" + name
			for topic in topics:
				print (topic, q_name, float(profile['q_num_views']))
				self.r_combined_topics.zadd("quora:" + topic, q_name, float(profile['q_num_views'])) # TODO - supposed to get views per topic, not from userprofile

	def add_twitter_for_matched_experts(self, close=False):
		""" Add twitter profile to DB for matched experts, if close, close sql connection at end"""
		import codecs
		codecs.register(lambda name: codecs.lookup('utf8') if name == 'utf8mb4' else None)
		try:	
			_a = self.sql
		except AttributeError as e:
			self.__init_sql_connection()
		count = 0
		for t in self.r_combined_topics.scan_iter():
			site = t.split(':')[0]
			for (expert, score) in self.r_combined_topics.zscan_iter(t):
				twitter_screen_name = self.r_combined.hget(expert, "twitter_screen_name")
				try:
					twitter_user = self.api.get_user(screen_name=twitter_screen_name)._json
					listed_count = twitter_user['listed_count']
					user_id      = twitter_user['id']
					flattened_twitter_user = self.serialize_and_flatten_twitter_user(twitter_user)
					self.r.hmset(twitter_screen_name, flattened_twitter_user)
					count += 1
					if count % 100 == 0:
						print("Progress: %d" % count)
				except RateLimitError as e:
					print e
					self.twitter_km.invalidate_key()
					self.twitter_km.change_key()
					self.__init_twitter_api()
					twitter_user = self.api.get_user(screen_name=twitter_screen_name)._json
				except TweepError as e:
					print("ERROR screen_name: %s " % twitter_screen_name)
					print e
				# Insert into MYSQL DB
				try:
					self.cursor.execute("INSERT INTO `test`.`new_temp` (user_id, listed_count, name, screen_name, verified, profile_image_url, description) VALUES(%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE user_id=%s, listed_count=%s, name=%s, screen_name=%s, verified=%s, profile_image_url=%s, description=%s" , (twitter_user['id'], twitter_user['listed_count'], twitter_user['name'], twitter_user['screen_name'], twitter_user['verified'], twitter_user['profile_image_url'], twitter_user['description'], twitter_user['id'], twitter_user['listed_count'], twitter_user['name'], twitter_user['screen_name'], twitter_user['verified'], twitter_user['profile_image_url'], twitter_user['description']))
					self.sql.commit()
					print("INSERTED user %s, listed_count %s" % (user_id, listed_count))
				except Exception as e:
					print("ERROR    user %s, listed_count %s" % (user_id, listed_count))
					print e
		if close:
			self.close()

	def close(self):
		""" Close system resources"""
		try:
			print("Closing SQL connection...")
			self.sql.close()
		except AttributeError as e:
			pass

	def get_all_twitter_experts(self, so_far=0, close=False):
		""" Get all twitter user_ids with listed_count > 10 from DB"""
		try:
			a = self.sql
		except AttributeError as e:
			self.__init_sql_connection()
		from collections import deque
		users = deque([])
		num_experts = self.ENV['NUM_TWITTER_EXPERTS']

		try:
			self.cursor.execute("SET SESSION net_read_timeout = 3600")
			self.cursor.execute("SELECT user_id FROM test.new_temp WHERE listed_count > 10 LIMIT %d OFFSET %d" % (500000, so_far))
			for row in self.cursor:
				users.append(int(row[0]))
		except Exception as e:
			print e
		finally:
			if close:
				self.close()
			return users

	def populate_all_twitter_users(self):
		users = self.get_all_twitter_experts()
		from parallel import Counter, BaseWorker
		import threading
		NUM_THREADS = 20
		qlock = threading.Lock()
		count = Counter(start=0)
		start = time.time()
		class PopulateWorker(BaseWorker):
			def run(self):
				# Acquire qlock
				hasWork = True
				while hasWork:
					qlock.acquire()
					try:
						if len(self.users) > 0:
							i = 0
							users_list = []
							while i < 100 and len(self.users) > 0:
								users_list.append(str(self.users.popleft()))
								i += 1
						else:
							hasWork = False
					finally:
						qlock.release()
					if hasWork:
						self.pr.lookup_and_insert_twitter_accounts(users_list)
						self.data['counter'].increment()
						print("Processed users : %d" % self.data['counter'].value * 100)
		threads = []
		for i in range(0, NUM_THREADS):
			t = PopulateWorker(users, counter=count)
			threads.append(t)
			t.start()
		for t in threads:
			t.join()
		print("Time taken : %.2f " % (time.time() - start))

	def lookup_and_insert_twitter_accounts(self, user_ids):
		""" Batch lookup twitter accounts and insert into MYSQL DB"""
		import codecs
		codecs.register(lambda name: codecs.lookup('utf8') if name == 'utf8mb4' else None)
		try:
			_a = self.sql
		except AttributeError as e:
			self.__init_sql_connection()
		try:
			user_objs = self.api.lookup_users(user_ids=user_ids)
			data = []
			for u in user_objs:
				data.append((u.id, u.name, u.screen_name, u.verified, u.profile_image_url, u.description, u.id, u.name, u.screen_name, u.verified, u.profile_image_url, u.description))
			stmt = "INSERT INTO `test`.`new_temp` (user_id, name, screen_name, verified, profile_image_url, description) VALUES(%s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE user_id=%s, name=%s, screen_name=%s, verified=%s, profile_image_url=%s, description=%s"
			try:
				self.cursor.executemany(stmt, data)
				self.sql.commit()
			except Exception as e:
				print "[MYSQL ERROR] " + str(e)
		except Exception as e:
			print e

	def get_listed_count_for_twitter_user(self, user_id, close=False):
		try:
			_a = self.sql
		except AttributeError as e:
			self.__init_sql_connection()
		self.cursor.execute("SELECT listed_count FROM test.new_temp WHERE user_id = %d" % (user_id))
		if close:
			self.close()
		for row in self.cursor:
			listed_count = row[0]
			return listed_count
		raise(PeerRankError("Cannot find user in database"))

	def batch_get_twitter_profile(self, user_rankings):
		""" Batch fetch twitter profiles for all user_ids (user_ids, score, flag)"""
		try:
			_a = self.sql
		except AttributeError as e:
			self.__init_sql_connection()
		stats = {
			'q_merged'  : 0,
			'q_added'   : 0,
			'so_merged' : 0,
			'so_added'  : 0
		}
		if len(user_rankings) > 0:
			user_ids    = map(lambda x: x[0], user_rankings)
			user_scores = map(lambda x: x[1], user_rankings)
			in_params   = ', '.join(map(lambda x: '%s', user_ids))
			stmt = "SELECT user_id, screen_name, name, description, verified, profile_image_url FROM `test`.`new_temp` WHERE user_id IN (%s)" % in_params
			self.cursor.execute(stmt, user_ids)
			user_profiles = {}
			for row in self.cursor:
				user_profiles[row[0]] = {
					'user_id' : row[0],
					'screen_name' : row[1],
					'name' : row[2],
					'description' : row[3],
					'verified' : row[4],
					'profile_image_url' : row[5]
					}
			# Add in ranking scores
			for (user, score, flag) in user_rankings:
				try:
					user_profiles[user]['score'] = score
					if flag == 0:
						pass
					elif flag == 1:
						user_profiles[user]['is_merged_stackoverflow'] = True
						stats['so_merged'] += 1
						pprint.pprint(user_profiles[user])
					elif flag == 2:
						user_profiles[user]['is_added_stackoverflow'] = True
						stats['so_added'] += 1
						pprint.pprint(user_profiles[user])
					elif flag == 3:
						user_profiles[user]['is_merged_quora'] = True
						stats['q_merged'] += 1
						pprint.pprint(user_profiles[user])
					elif flag == 4:
						user_profiles[user]['is_added_quora'] = True
						stats['q_added'] += 1
						pprint.pprint(user_profiles[user])
					else:
						print("Error user %d, flag %d" % (user, flag))
				except KeyError as e:
					# Possibility of user not in our Database
					print(e)
			return (user_profiles.values(), stats)
		else:
			return ([], stats)

	def infer_twitter_topics(self, user_id, close=False, verbose=False):
		""" 
			For every Twitter expert identified, return a vector of <topics, frequency> using Cognos methodology
			1. Separate CamelCase words into individual words
			2. Apply case-folding, stemming, removal of stop-words + domain-specific stop-words
			3. Identify nouns and adjectives using part-of-speech tagger
			4. Group together words that are similar to each other based on edit-distance
			5. Consider only unigram and bigrams as topics
		"""
		try:
			a = self.sql
		except AttributeError as e:
			self.__init_sql_connection()
			
		import re
		def camel_case_split(identifier):
			matches = re.finditer('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', identifier)
			return [m.group(0) for m in matches]

		lists = []
		self.cursor.execute("SELECT * FROM test.member_of WHERE user_id = %d" % (user_id))
		for row in self.cursor:
			lists.append(int(row[2]))
		doc = []
		for l in lists:
			self.cursor.execute("SELECT name, description FROM test.lists WHERE list_id = %d LIMIT 1" % (l))
			for row in self.cursor:
				doc.append(unicode(row[0]) + ' ' + unicode(row[1]))
		if verbose: print(doc)

		# Close SQL connection
		if close:
			self.close()

		if verbose: print("Tokenizing")
		from nltk.tokenize import TweetTokenizer
		tokenizer = TweetTokenizer(strip_handles=True)
		token_doc = []
		for desc in doc:
			token_doc += tokenizer.tokenize(desc)
		# if verbose: pprint.pprint(token_doc)

		# Separate CamelCase
		temp_token_doc = []
		if verbose: print("Separate CamelCase")
		for token in token_doc:
			matches = camel_case_split(token)
			temp_token_doc += matches
		if verbose: pprint.pprint(temp_token_doc)

		# Split on -, _ , /, .,\,|,(,),{,},,
		if verbose: print("Separate DOT, DASH, SLASHES and UNDERSCORES")
		token_doc = []
		for token in temp_token_doc:
			token_doc += re.split('\W+|_', token)
		temp_token_doc = [x for x in token_doc if x != ''] # Remove empty strings
		if verbose: pprint.pprint(temp_token_doc)

		# Case-folding, stemming, stop-word removal
		from nltk.stem.snowball import SnowballStemmer
		from nltk.corpus import stopwords
		stop = set(stopwords.words('english'))
		stop.update(PeerRank.STOPWORDS)
		if verbose: print("Case folding, stemming and stop-word removal")
		stemmer = SnowballStemmer('english')
		token_doc = [stemmer.stem(x.lower()) for x in temp_token_doc if stemmer.stem(x.lower()) not in stop]
		if verbose: pprint.pprint(token_doc)

		# Identify nouns and adjectives
		if verbose: print("Identifying nouns and adjectives")
		from nltk import pos_tag
		tagged_doc = pos_tag(token_doc)
		temp_token_doc = [x[0] for x in tagged_doc if x[1] == 'NN' or x[1] == 'JJ']
		if verbose: pprint.pprint(temp_token_doc)

		# Group similar words
		# if verbose: print("Group similar words together")
		# from itertools import combinations
		# for (w1, w2) in combinations(temp_token_doc, 2):
		# 	score = jellyfish.jaro_winkler(unicode(w1), unicode(w2))
		# 	if score > 0.8 and score < 1.0:
				# if verbose: print(w1, w2)
				# pass
		# if verbose: pprint.pprint(temp_token_doc)

		# Finally, unigram and bigram as topics
		topics = []
		from nltk.util import ngrams
		if verbose: print("Generating unigram and bigram")
		topics = set(ngrams(temp_token_doc, 1))
		topics.update(set(ngrams(temp_token_doc, 2)))
		# if verbose: pprint.pprint(topics)

		# Convert tuples to string
		topics = [reduce(lambda y,z : y + " " + z, x) for x in topics]

		# Count frequency of occurence
		from nltk import FreqDist
		if verbose: print("Generating <topic, frequency> vector for user %d" % user_id)
		#compute frequency distribution for all the ngrams in the text
		fdist = FreqDist(topics)
		for token in temp_token_doc:
			fdist[token] += 1
		if verbose:
			pass
			for k,v in fdist.items():
				print k,v

		return fdist

	def build_inverted_index(self):
		""" Build up a "word" -> [user_ids] inverted index"""
		from nltk import word_tokenize
		try:
			_a = self.sql
		except AttributeError as e:
			self.__init_sql_connection()
		count = 0

		start = time.time()
		topic_vectors = [] # (topic_vector, user_id) tuple
		self.cursor.execute("SELECT topics, user_id from `test`.`twitter_topics_for_user` LIMIT 500000")
		for row in self.cursor:
			topic_vectors.append((json.loads(row[0]), row[1]))

		inverted_index = {}
		for (topic_vector, user_id) in topic_vectors:
			topics = set()
			for (sentence, freq) in topic_vector.iteritems():
				topics.update(word_tokenize(sentence))
			for t in topics:
				try:
					inverted_index[t].append(user_id)
				except KeyError as e:
					inverted_index[t] = [user_id]

		# Write to DB
		size = len(inverted_index)
		for (word, index) in inverted_index.iteritems():
			json_list = json.dumps(index)
			try:
				self.cursor.execute("INSERT INTO `test`.`inverted_index` (word, doc_index) VALUES(%s, %s) ON DUPLICATE KEY UPDATE word=%s, doc_index=%s, last_updated=CURRENT_TIMESTAMP", (word, json_list, word, json_list))
				count += 1
				if count % 100 == 0:
					self.sql.commit()
					print("%d words to go..." % (size - count))
			except Exception as e:
				print e
		print("Inverted index built in %.2f" % (time.time() - start))

	def insert_topic_vector(self, user_id, topic_vector):
		""" Inserts a topic_vector for a given user into the DB"""
		json_str = json.dumps(topic_vector, ensure_ascii=False)
		try:
			# print json_str
			self.cursor.execute("INSERT INTO `test`.`twitter_topics_for_user` (user_id, topics) VALUES(%s, %s) ON DUPLICATE KEY UPDATE `topics`=%s, `last_updated`=CURRENT_TIMESTAMP", (str(user_id), json_str, json_str))
			return True
		except Exception as e:
			print e
			return False

	def get_query_vector(self, query):
		""" Given a raw user-input query, convert to query vector"""
		from nltk import word_tokenize
		tokenized_query = word_tokenize(query.strip())

		from nltk.stem.snowball import SnowballStemmer
		stemmer = SnowballStemmer('english')
		tokenized_query = [stemmer.stem(x.lower()) for x in tokenized_query]
		return ' '.join(tokenized_query)

	def get_twitter_rankings(self, query, include_so=False, include_q=False):
		""" 
			For a query, return top twitter experts, multi-threaded implementation
			If include_so = True, include ranking score from matched stackoverflow account
			If include_q = True, include ranking score from matched Quora account
		"""
		from parallel import Counter, BaseWorker
		import threading
		
		NUM_THREADS = 8
		qlock = threading.Lock()
		count = Counter(start=0)
		class RankWorker(BaseWorker):
			def run(self):
				# Acquire qlock
				hasWork = True
				while hasWork:
					qlock.acquire()
					try:
						if self.data['counter'].value < len(self.users):
							(topic_vector, user_id) = self.users[self.data['counter'].value]
							self.data['counter'].increment()
						else:
							hasWork = False
					finally:
						qlock.release()
					if hasWork:
						rankings.append((user_id, self.pr.rank_twitter_user(user_id, self.data['query_vector'], topic_vector), 0))

		try:
			_a = self.sql
		except AttributeError as e:
			self.__init_sql_connection()
		query_vector = self.get_query_vector(query)

		# Lookup inverted index
		start = time.time()
		user_ids = []
		query_tokens = query_vector.split(' ')
		in_params = ', '.join(map(lambda x: '%s', query_tokens))
		stmt = "SELECT doc_index FROM `test`.`inverted_index` WHERE word IN (%s)" % in_params
		self.cursor.execute(stmt, query_tokens)
		for row in self.cursor:
			user_id_list = json.loads(row[0])
			user_ids.extend(user_id_list)
		print("Time taken to lookup inverted index : %.2f" % (time.time() - start))
		print("No. of users to rank : %d" % len(user_ids))
		
		start = time.time()
		in_params = ', '.join(map(lambda x: '%s', user_ids))
		stmt = "SELECT topics, user_id from `test`.`twitter_topics_for_user` WHERE user_id IN (%s) LIMIT 1000" % in_params
		topic_vectors = []
		if len(user_ids) > 0:
			self.cursor.execute(stmt, user_ids)
			for row in self.cursor:
				topic_vectors.append((json.loads(row[0]), row[1]))
		print("Time taken to fetch all users: %.2f " % (time.time() - start))

		# Multi-threading
		threads = []
		rankings = []
		for i in range(0, NUM_THREADS):
			thread = RankWorker(topic_vectors, query_vector=query_vector, counter=count)
			threads.append(thread)
			thread.start()
		for t in threads:
			t.join()

		start = time.time()
		rankings.sort(key=lambda x: x[1], reverse=True)
		print("Time taken to sort rankings: %.2f " % (time.time() - start))

		if len(rankings) == 0: return rankings

		max_score = max(rankings, key=lambda x: x[1])[1]
		min_score = min(rankings, key=lambda x: x[1])[1]
		twitter_range = max_score - min_score
		if include_so:
			print("Adjusting for StackOverflow contributions...")
			start = time.time()
			so_max = float(0)
			so_min = float(100000)
			topic_docs = []
			experts = []
			for t in self.r_combined_topics.scan_iter(match="stackexchange:*%s*" % (query,)):
				for (expert, reputation) in self.r_combined_topics.zscan_iter(t):
					if reputation > so_max: so_max = reputation
					if reputation < so_min: so_min = reputation
					experts.append([expert, reputation])
				t = t.split(':')[1]
				topic_docs.append(t.replace('-', ' '))
			ranked_docs = cover_density_ranking(query, topic_docs)
			for rank, (index, score) in enumerate(ranked_docs):
				experts[index][1] = score * experts[index][1] # Rescale reputation by cover density ranking score

			rescaled_rankings = {}
			so_range = so_max - so_min
			for i, l in enumerate(experts):
				expert = l[0]
				reputation = l[1]
				twitter_screen_name = self.r_combined.hget(expert, "twitter_screen_name")
				twitter_user_id = self.r.hget(twitter_screen_name, "twitter_id")
				if twitter_user_id is not None:
					so_norm = 1 if so_range == 0 else ((reputation - so_min) / so_range)
					rescaled_reputation = so_norm * twitter_range + min_score
					rescaled_rankings[int(twitter_user_id)] = rescaled_reputation

			# Merge
			so_merged_rankings = []
			for (user_id, rank_score, flag) in rankings:
				# We are doing a simple weighted average - 0.5 from Twitter, 0.5 from StackOverflow
				try:
					so_merged_rankings.append((user_id, 0.5 * rank_score + 0.5 * rescaled_rankings[user_id], 1)) # 1 to indicate merge with stackoverflow
					print("Score changed for user %d, twitter score: %.2f, stackoverflow score: %.2f" % (user_id, rank_score, rescaled_rankings[user_id]))
					del rescaled_rankings[user_id] # Remove key and value from rescaled_rankings
				except KeyError as e:
					so_merged_rankings.append((user_id, rank_score, flag)) # 0 to indicate unchanged
			# Add unmerged values back to Twitter rankings
			for (key, value) in rescaled_rankings.iteritems():
				so_merged_rankings.append((key, value, 2)) # 2 to indicate added from StackOverflow
			so_merged_rankings.sort(key=lambda x: x[1], reverse=True)
			# pprint.pprint(so_merged_rankings)
			print("Time taken to adjust StackOverflow: %.2f " % (time.time() - start))
		
		if include_q:
			print("Adjusting for Quora contributions...")
			start = time.time()
			q_max = float(0)
			q_min = float(100000)
			q_topic_docs = []
			q_experts = []
			for t in self.r_combined_topics.scan_iter(match="quora:*%s*" % (query,)):
				for (expert, reputation) in self.r_combined_topics.zscan_iter(t):
					if reputation > so_max: so_max = reputation
					if reputation < so_min: so_min = reputation
					q_experts.append([expert, reputation])
				t = t.split(':')[1]
				q_topic_docs.append(t)
			ranked_docs = cover_density_ranking(query, q_topic_docs)
			for rank, (index, score) in enumerate(ranked_docs):
				q_experts[index][1] = score * q_experts[index][1] # Rescale reputation by cover density ranking score

			rescaled_rankings = {}
			q_range = q_max - q_min
			for i, l in enumerate(q_experts):
				expert = l[0]
				reputation = l[1]
				twitter_screen_name = self.r_combined.hget(expert, "twitter_screen_name")
				twitter_user_id = self.r.hget(twitter_screen_name, "twitter_id")
				if twitter_user_id is not None:
					q_norm = 1 if q_range == 0 else ((reputation - q_min) / q_range)
					rescaled_reputation = q_norm * twitter_range + min_score
					rescaled_rankings[int(twitter_user_id)] = rescaled_reputation

			# Merge
			ref_rankings = so_merged_rankings if include_so else rankings
			q_merged_rankings = []
			for (user_id, rank_score, flag) in ref_rankings:
				# We are doing a simple weighted average - 0.5 from Twitter, 0.5 from Quora
				try:
					q_merged_rankings.append((user_id, 0.5 * rank_score + 0.5 * rescaled_rankings[user_id], 3))
					print("Score changed for user %d, twitter score: %.2f, quora score: %.2f" % (user_id, rank_score, rescaled_rankings[user_id]))
					del rescaled_rankings[user_id]
				except KeyError as e:
					q_merged_rankings.append((user_id, rank_score, flag))
			# Add unmerged values back to Twitter rankings
			for (key, value) in rescaled_rankings.iteritems():
				q_merged_rankings.append((key, value, 4)) # 2 to indicate added from StackOverflow
			q_merged_rankings.sort(key=lambda x: x[1], reverse=True)
			# pprint.pprint(q_merged_rankings)
			print("Time taken to adjust Quora : %.2f " % (time.time() - start))
			return q_merged_rankings
		else:
			if include_so:
				return so_merged_rankings
			else:
				return rankings

	def rank_twitter_user(self, user_id, query, topic_vector, verbose=False):
		"""
			Given a query vector, calculate the ranking score for
			the user with their inferred topic vector
		"""
		start = time.time()
		total = reduce(lambda x,y: x + topic_vector[y], topic_vector, 0)
		if total == 0:
			return 0
		sim_score = 0
		topic_list = [topic for topic, freq in topic_vector.iteritems()]
		ranked_docs = cover_density_ranking(query, topic_list)
		for rank, (index, score) in enumerate(ranked_docs):
			sim_score += topic_vector[topic_list[index]]
		sim_score = sim_score * 1.0 / total
		listed_count = self.get_listed_count_for_twitter_user(user_id)
		if listed_count <= 0:
			print("Error! Listed count is %d for %d" % (listed_count, user_id))
			listed_count = 10
		ranking_score = sim_score * math.log(listed_count)
		if verbose: print("Time taken to rank user %d : %.2f" % (user_id, (time.time() - start)))
		return ranking_score

class PeerRankError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)

def main():
	pr = PeerRank()
	topics = seed.SEED.keys()
	random.shuffle(topics)
	for topic in topics:
		pr.change_se_site(topic)
		print ">>> Topic: %s" % topic
		x = random.choice(seed.SEED[topic])
		new_member = {"so_display_name" : None}
		new_member.update(pr.serialize_and_flatten_twitter_user(pr.api.get_user(screen_name=x)._json))
		pr.r.hmset(x, new_member)
		print "Name search filter              : %d"       % PeerRank.NAME_SEARCH_FILTER
		print "Name jaro-winkler sim threshold : %.2f"     % PeerRank.NAME_JARO_THRES
		print "Image similarity threshold      : %.2f"     % PeerRank.IMG_SIM_THRES
		print "Getting Twitter experts starting with : %s" % x
		print ''
		targeted_list = pr.search_similar_twitter_acct(x)
		processed_list = pr.twitter_to_stackexchange(targeted_list)
		print ''
		print "Total targeted Twitter accounts : %d" % len(targeted_list)
		print "Total SO accounts matched : %d" % pr.total_matched
		pr.total_matched = 0
		
if __name__ == "__main__":
	main()