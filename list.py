#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pprint, sys, tweepy, cv2, jellyfish, time, redis, json
sys.path.append('./Py-StackExchange')
import stackexchange
from util import *
from skimage.transform import *
from skimage.io import *
from image_match.goldberg import ImageSignature
# from matplotlib import pyplot as plt
from tweepy.error import TweepError
from tweepy import OAuthHandler, API, Cursor
from urllib2 import HTTPError, URLError
from collections import deque

DEVELOPERS = {
	# 'codinghorror' : {
	# 	'twitter_screen_name' : 'codinghorror',
	# 	'twitter_name' : 'Jeff Atwood',
	# 	'so_display_name' : None
	# },
	# 'Linus__Torvalds' : {
	# 	'twitter_screen_name' : 'Linus__Torvalds',
	# 	'twitter_name' : 'Linus Torvalds',
	# 	'so_display_name' : None
	# },
	'jonskeet' : {
		'twitter_screen_name' : 'jonskeet',
		'twitter_name' : 'Jon Skeet',
		'so_display_name' : None
	},
	# 'BorisPouderous' : {
	# 'twitter_screen_name' : 'BorisPouderous',
	# 	'name' : "Boris Poudérous",
	# 	"so_user" : None
	# }
}

DEVELOPERS_THRES    = 100
NAME_SEARCH_FILTER  = 10
NAME_JARO_THRES     = 0.80
LOC_JARO_THRES      = 0.90
IMG_SIM_THRES       = 0.50
TOTAL_MATCHED_ACC   = 0
# LIVE 
CONSUMER_KEY        = 'fTxnhb0nVeVfQG1a4c77FadFx'
CONSUMER_SECRET     = 'IgRFOa8ijfFVWoa01N9mKX1cQvOTIYh4tyQrVP4o5xzdDuXGTn'
ACCESS_TOKEN_KEY    = '918825662-3OzaE9V5KTjArMrFdnZ9vraz4ZtraVwyceoolChG'
ACCESS_TOKEN_SECRET = 'iOXklGWNcZdJS1goVHbxCFi11Lb65nF8CnFfNVrJSNZpg'
# DEV
# CONSUMER_KEY        = "djE9yKkygAhKaBnUcJnrZXybf"
# CONSUMER_SECRET     = "aaJHJZ8qYlX5yV8O4w8DE2mULcD7XK15khcdHJUfqcB5yQGLi6"
# ACCESS_TOKEN_KEY    = "918825662-hIm9wYSnjGAwgsmYUDs0jFLZcPsPW4YI5ijddbj1"
# ACCESS_TOKEN_SECRET = "0zhcnheOwX8XqZXEkvAbGBSlQUVCB3DkRvkSxxEiHLeTZ"

# SO_CLIENT_SECRET  = 'AjN*KCYPu9qFontnH1T7Fw(('
# SO_CLIENT_KEY     = 'PlqChK)JFcqzNx23OZe30Q((' # LIVE version
SO_CLIENT_KEY       = '4wBVVG2jcCrwIUbUZjHlEQ((' # DEV version 

LAST_CRAWL_INTERVAL = 0 # Duration since last crawl such that data is deemed stale and a new crawl is required

def init():
	auth = OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
	auth.set_access_token(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET)
	api = API(auth_handler=auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)
	return api

def get_matching_so_profile(user):
	"""
	User must be a dict containing screen_name, name, location and profile_image_url
	"""
	result = []
	matches = compare_name_string(user['screen_name'], user['name'])
	for i, u in enumerate(matches):
		img_sim = compare_image(user['profile_image_url'], u.profile_image)
		try:
			loc_sim = compare_location(user['location'], u.location)
		except (AttributeError, KeyError) as e: # Twitter's location field is optional
			loc_sim = 0
		matches[i] = (u, img_sim, loc_sim)
	matches = sorted(matches, cmp=lambda x, y: cmp(x[1], y[1]))
	matches = filter(lambda x: x[1] < IMG_SIM_THRES, matches)
	return matches[0][0] if len(matches) == 1 else None

def compare_location(twitter_loc, so_loc):
	score = jellyfish.jaro_winkler(unicode(twitter_loc), unicode(so_loc))
	return score

def compare_image(twitter_url, so_url):
	# t   = imread(twitter_url)
	# so  = imread(so_url)
	# fig = plt.figure("Twitter v.s. StackOverflow")
	# ax  = fig.add_subplot(1,3,1)
	# ax.set_title("Twitter")
	# plt.imshow(t)
	# ax  = fig.add_subplot(1,3,2)
	# ax.set_title("StackOverflow")
	# plt.imshow(so)
	# plt.show()
	gis    = ImageSignature()
	try:
		t_sig  = gis.generate_signature(twitter_url)
		so_sig = gis.generate_signature(so_url)
	except (URLError, HTTPError) as e:
		# 404 File not found errors
		print e
		return 1.0
	return gis.normalized_distance(t_sig, so_sig)

def compare_name_string(screen_name, name):
	so = stackexchange.Site(stackexchange.StackOverflow, SO_CLIENT_KEY, impose_throttling=True)
	matches = so.users_by_name(unicode(name, "utf-8"))
	result = []
	if len(matches) < NAME_SEARCH_FILTER:
		for m in matches:
			score = jellyfish.jaro_winkler(unicode(name, "utf-8"), m.display_name)
			if score > NAME_JARO_THRES:
				result.append(m)
	return result

def deserialize_twitter_user(twitter):
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

def deserialize_so_user(so):
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

def serialize_and_flatten_twitter_user(twitter):
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

def serialize_and_flatten_so_user(so):
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

if __name__ == "__main__":
	api   = init()
	r     = redis.Redis()
	q     = deque([x for x in DEVELOPERS.keys()])
	list_set = []
	count = 0
	for x in q:
		# Process starting nodes
		new_member = {"so_display_name" : None}
		new_member.update(serialize_and_flatten_twitter_user(api.get_user(screen_name=x)._json))
		r.hmset(x, new_member)
	print "Name search filter              : %d" % NAME_SEARCH_FILTER
	print "Name jaro-winkler sim threshold : %.2f" % NAME_JARO_THRES
	print "Image similarity threshold      : %.2f" % IMG_SIM_THRES
	print "Getting Twitter developers starting with : jonskeet"
	print ''
	# Collect new developers phase
	while len(DEVELOPERS) < DEVELOPERS_THRES and len(q) != 0:
		user = q.popleft()
		# print "Developer: " + user
		list_count = 0
		try:
			for pg in Cursor(api.lists_memberships, screen_name=user).pages(1):
				for l in pg:
					list_count += 1
					try:
						member_list = []
						for member_pg in Cursor(api.list_members, l.user.screen_name, l.slug).pages(1):
							for member in member_pg[0:20]:
								member_list.append(member.screen_name)
								if member.screen_name not in DEVELOPERS:
									print "%20s" % member.screen_name,
									count += 1
									if count % 5 == 0:
										print ''
									new_member = {'so_display_name' : None}
									new_member.update(serialize_and_flatten_twitter_user(member._json))
									q.append(new_member)
									DEVELOPERS[member.screen_name] = new_member
									r.hmset(member.screen_name, new_member)
						list_set.append(frozenset(member_list))
					except TweepError as e:
						print e
						continue
					# print "List : " + l.name + " done"
				# print "Number of lists : " + str(list_count)
		except TweepError as e:
			# Read time out etc.
			print e

	# score = average_jaccard_sim(set(list_set))
	# print "Average Jaccard-sim score : " + str(score)

	print ''
	for k, v in DEVELOPERS.iteritems():
		# Process twitter account
		r_acct = r.hgetall(k) # Remote account
		r_user = {} 		  # Local account which we will push later on
		if ('twitter_last_crawled' in r_acct and (time.time() - float(r_acct['twitter_last_crawled']))) >  LAST_CRAWL_INTERVAL:
			# Update twitter user profile info
			try:
				user   = api.get_user(screen_name=k)
				r_user.update(serialize_and_flatten_twitter_user(user._json))
			except TweepError as e:
				print e
		else:
			# Preserve old twitter user profile data, so_ prefixed keys will be overwritten or preserved later on
			r_user = r_acct
		# Process StackOverflow account
		so_user = None
		if len(r_acct) != 0:
			if (r_acct['so_display_name'] == 'None' and 'so_last_crawled' not in r_acct) or (time.time() - float(r_acct['so_last_crawled'])) > LAST_CRAWL_INTERVAL:
				twitter_acct = deserialize_twitter_user(r_acct)
				try:
					so_user = get_matching_so_profile(twitter_acct)
					time.sleep(10)
				except UnicodeDecodeError as e:
					print str(e) + str(twitter_acct['name'])
				if so_user is not None:
					print "Twitter(" + k + ") -> StackOverflow(" + so_user.display_name + ")"
					# Save into DB
					r_user.update(serialize_and_flatten_so_user(so_user.__dict__))
					# pprint.pprint(r_user)
				else:
					# Set the last crawled date
					r_user.update({'so_last_crawled' : time.time()})
		r.hmset(k, r_user)
		TOTAL_MATCHED_ACC = TOTAL_MATCHED_ACC + 1 if so_user is not None else TOTAL_MATCHED_ACC
		DEVELOPERS[k]['so_user'] = so_user.__dict__ if so_user is not None else None
	print ''
	print "Total targeted Twitter accounts : %d" % len(DEVELOPERS)
	print "Total SO accounts matched : %d" % TOTAL_MATCHED_ACC