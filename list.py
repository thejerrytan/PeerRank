#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pprint, sys, tweepy, cv2, jellyfish, time, redis, json, seed, random, httplib, logger, signal
sys.path.append('./Py-StackExchange')
import stackexchange
from util import *
from skimage.transform import *
from skimage.io import *
from image_match.goldberg import ImageSignature
from matplotlib import pyplot as plt
from tweepy.error import TweepError
from tweepy.error import RateLimitError
from tweepy import OAuthHandler, API, Cursor
from urllib2 import HTTPError, URLError
from collections import deque
from key import KeyManager

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

class PeerRank:
	def __init__(self, se_site='stackoverflow.com'):
		self.logger        = logger.Logger()
		self.twitter_km    = KeyManager('Twitter-Search-v1.1', 'keys.json')
		self.so            = stackexchange.Site(se_site, SO_CLIENT_KEY, impose_throttling=True)
		self.__init_twitter_api()
		self.r             = redis.Redis(db=0)
		self.r_tags        = redis.Redis(db=1)
		self.r_se_experts  = redis.Redis(db=2)
		self.total_matched = 0
		self.start_time    = time.time()

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
		matches = filter(lambda x: x[1] < IMG_SIM_THRES, matches)
		return matches[0][0] if len(matches) == 1 else None

	def is_matching_twitter_profile(self, twitter_user, se_user):
		"""se_user must be a dict containing screen_name, name, location and profile_image_url"""
		if self.compare_name_string_se(twitter_user['screen_name'], se_user['display_name']):
			img_sim = self.compare_image(twitter_user['profile_image_url'], se_user['profile_image'])
			print "       IMG_SIM : %.2f" % img_sim,
			if 'location' in twitter_user and 'location' in se_user:
				loc_sim = self.compare_location(twitter_user['location'], se_user['location'])
				print "       LOC_SIM : %.2f" % loc_sim
			print
			return True if img_sim < IMG_SIM_THRES else False
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
		if len(matches) < NAME_SEARCH_FILTER:
			for m in matches:
				score = jellyfish.jaro_winkler(unicode(name, "utf-8"), m.display_name)
				if score > NAME_JARO_THRES:
					result.append(m)
		return result

	def compare_name_string_se(self, screen_name, so_name):
		"""Compare name string for use when matching SE experts to Twitter accounts. Returns boolean"""
		score = jellyfish.jaro_winkler(unicode(so_name, "utf-8"), screen_name)
		return True if score > NAME_JARO_THRES else False

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
		"""
		Take a remote redis user account hash, retrieves keys prefixed with twitter OSN, and removes the prefix, returns a dict
		"""
		key_prefix = "so_"
		allowed_keys = ['id','account_id', 'user_id', 'display_name', 'profile_image', 'location', 'reputation', 'url', 'link', 'creation_date']
		result = {}
		for k, v in so.iteritems():
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

	def twitter_to_stackexchange(self, users):
		for k, v in users.iteritems():
			# Process twitter account
			r_acct = self.r.hgetall(k) # Remote account
			r_user = {} 		  # Local account which we will push later on
			if ('twitter_last_crawled' in r_acct and (time.time() - float(r_acct['twitter_last_crawled']))) >  LAST_CRAWL_INTERVAL:
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
				if (r_acct['so_display_name'] == 'None' and 'so_last_crawled' not in r_acct) or (time.time() - float(r_acct['so_last_crawled'])) > LAST_CRAWL_INTERVAL:
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
		"""Get experts starting from StackExchange, using top answerers from every tag (topic), and map to their Twitter acct"""
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
				if self.count < skip:
					print "Skipped %s" % t
					self.count += 1
					continue
				site_str = self.__get_namespace_from_key(t, 0)
				site = stackexchange.Site(site_str, SO_CLIENT_KEY, impose_throttling=True)
				tag = stackexchange.models.Tag(self.r_tags.hgetall(t), site)
				print "Getting top experts for: %s (%d)" % (tag.name, self.count)
				a_count = 0
				top_answerers = tag.top_answerers('all_time')
				for topuser in top_answerers:
					a_count += 1
					user = topuser.user.__dict__
					try:
						print '    ' + unicode(a_count) + ' ' + unicode(user['display_name'])
					except UnicodeDecodeError as e:
						print '    ' + e
					user = self.serialize_and_flatten_so_user(user)
					user['so_last_crawled'] = time.time()
					self.r_se_experts.hmset(site_str + ':' + user['so_display_name'], user)
				time.sleep(5)
				if self.count % self.logger.LOG_INTERVAL == 0: self.logger.log(num_keys_processed=self.count, time_logged=time.time(), exception='')
				self.count += 1
		except Exception as e:
			print e
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
		print "Name search filter              : %d"       % NAME_SEARCH_FILTER
		print "Name jaro-winkler sim threshold : %.2f"     % NAME_JARO_THRES
		print "Image similarity threshold      : %.2f"     % IMG_SIM_THRES
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
					for t_user in self.api.search_users(q=self.__get_namespace_from_key(user, 1))[0:NAME_SEARCH_FILTER]:
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
				except RateLimitError as e:
					print e
					self.twitter_km.invalidate_key()
					self.twitter_km.change_key()
					self.__init_twitter_api()
				except TweepError as e:
					print e
					continue
		except Exception as e:
			self.logger.log(num_keys_processed=self.count, time_terminated=time.time(), time_logged=time.time(), exception=repr(e) + e.__str__, process=sys._getframe().f_code.co_name)
			self.logger.close()

	def count_matched_se_experts(self):
		count = 0
		num_keys = 0
		for user in self.r_se_experts.scan_iter():
			twitter_acct = self.r_se_experts.hget(user, 'twitter_screen_name')
			num_keys += 1
			if twitter_acct is not None:
				count += 1
		print "Total key count: %d" % num_keys
		print "Total matched StackExchange experts : %d in %.2fs" % (count, (time.time() - self.start_time))


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
		print "Name search filter              : %d"       % NAME_SEARCH_FILTER
		print "Name jaro-winkler sim threshold : %.2f"     % NAME_JARO_THRES
		print "Image similarity threshold      : %.2f"     % IMG_SIM_THRES
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