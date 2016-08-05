#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pprint, sys, tweepy, cv2, jellyfish, time, redis, json, seed, random
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
		self.twitter_km = KeyManager('Twitter-Search-v1.1', 'keys.json')
		self.so = stackexchange.Site(se_site, SO_CLIENT_KEY, impose_throttling=True)
		self.__init_twitter_api()
		self.r = redis.Redis()
		self.total_matched = 0
		self.start_time = time.time()

	def __init_twitter_api(self):
		auth = OAuthHandler(self.twitter_km.get_key()['consumer_key'], self.twitter_km.get_key()['consumer_secret'])
		auth.set_access_token(self.twitter_km.get_key()['access_token_key'], self.twitter_km.get_key()['access_token_secret'])
		self.api = API(auth_handler=auth, wait_on_rate_limit=False, wait_on_rate_limit_notify=True)

	def change_se_site(self, se_site):
		self.so = stackexchange.Site(se_site, SO_CLIENT_KEY, impose_throttling=True)

	def print_time_taken_for_user(self, user):
		print "Time taken for user: %20s %.2fs" % (user, (time.time() - self.start_time))

	def reset_start_time(self):
		self.start_time = time.time()

	def get_matching_so_profile(self, user):
		"""
		User must be a dict containing screen_name, name, location and profile_image_url
		"""
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
		self.plot_image(twitter_url, so_url)
		gis = ImageSignature()
		try:
			t_sig  = gis.generate_signature(twitter_url)
			so_sig = gis.generate_signature(so_url)
		except (URLError, HTTPError) as e:
			# 404 File not found errors
			print e
			return 1.0 # Most dissimilar score
		return gis.normalized_distance(t_sig, so_sig)

	def compare_name_string(self, screen_name, name):
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
		allowed_keys = ['account_id', 'display_name', 'profile_image', 'location', 'reputation', 'url', 'creation_date']
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
		allowed_keys = ['account_id', 'display_name', 'profile_image', 'location', 'reputation', 'url', 'creation_date']
		result = {}
		for k in allowed_keys:
			try:
				result[key_prefix+k] = so[k]
			except KeyError as e:
				pass
		result['so_last_crawled'] =  time.time()
		return result

	def link_stackoverflow(self, users):
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
		processed_list = pr.link_stackoverflow(targeted_list)
		print ''
		print "Total targeted Twitter accounts : %d" % len(targeted_list)
		print "Total SO accounts matched : %d" % pr.total_matched
		pr.total_matched = 0
		
if __name__ == "__main__":
	main()