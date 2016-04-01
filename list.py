#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pprint, sys, tweepy, cv2, jellyfish, time, redis, json
sys.path.append('./Py-StackExchange')
import stackexchange
from skimage.transform import *
from skimage.io import *
from image_match.goldberg import ImageSignature
# from matplotlib import pyplot as plt
from tweepy.error import TweepError
from tweepy import OAuthHandler, API, Cursor
from urllib2 import HTTPError

DEVELOPERS = {
	'codinghorror' : {
		'twitter_name' : 'Jeff Atwood',
		'so_user' : None
	},
	'Linus__Torvalds' : {
		'twitter_name' : 'Linus Torvalds',
		'so_user' : None
	},
	'jonskeet' : {
		'twitter_name' : 'Jon Skeet',
		'so_user' : None
	},
	# 'BorisPouderous' : {
	# 	'name' : "Boris Poudérous",
	# 	"so_user" : None
	# }
}

DEVELOPERS_THRES    = 2500
NAME_SEARCH_FILTER  = 10
NAME_JARO_THRES     = 0.90
LOC_JARO_THRES      = 0.90
IMG_SIM_THRES       = 0.50
TOTAL_MATCHED_ACC   = 0

CONSUMER_KEY        = 'fTxnhb0nVeVfQG1a4c77FadFx'
CONSUMER_SECRET     = 'IgRFOa8ijfFVWoa01N9mKX1cQvOTIYh4tyQrVP4o5xzdDuXGTn'
ACCESS_TOKEN_KEY    = '918825662-3OzaE9V5KTjArMrFdnZ9vraz4ZtraVwyceoolChG'
ACCESS_TOKEN_SECRET = 'iOXklGWNcZdJS1goVHbxCFi11Lb65nF8CnFfNVrJSNZpg'
# SO_CLIENT_SECRET  = 'AjN*KCYPu9qFontnH1T7Fw(('
# SO_CLIENT_KEY     = 'PlqChK)JFcqzNx23OZe30Q(('
SO_CLIENT_KEY       = '4wBVVG2jcCrwIUbUZjHlEQ((' # DEV version 

def paginate(iterable, page_size):
	i1, i2 = itertools.tee(iterable)
	while True:
		iterable, page = (itertools.islice(i1, page_size, None), list(itertools.islice(i2, page_size)))
		if len(page)==0:
			break
		yield page

def init():
	auth = OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
	auth.set_access_token(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET)
	api = API(auth_handler=auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)
	return api

def get_lists(screen_name):
	api = init()
	lists = api.lists_memberships(screen_name=screen_name)
	return lists[:10]

def get_matching_so_profile(user):
	result = []
	matches = compare_name_string(user['screen_name'], user['name'])
	for i, u in enumerate(matches):
		img_sim = compare_image(user['profile_image_url'], u.profile_image)
		try:
			loc_sim = compare_location(user['location'], u.location)
		except AttributeError as e:
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
	except HTTPError as e:
		# 404 File not found errors
		print e
		return 1.0
	return gis.normalized_distance(t_sig, so_sig)

def compare_name_string(screen_name, name):
	so = stackexchange.Site(stackexchange.StackOverflow, SO_CLIENT_KEY, impose_throttling=True)
	matches = so.users_by_name(name)
	result = []
	if len(matches) < NAME_SEARCH_FILTER:
		for m in matches:
			score = jellyfish.jaro_winkler(unicode(name), unicode(m.display_name))
			if score > NAME_JARO_THRES:
				result.append(m)
	return result

if __name__ == "__main__":
	api = init()
	r = redis.Redis()
	hname = 'users'
	count = 0
	print "Name search filter              : %d" % NAME_SEARCH_FILTER
	print "Name jaro-winkler sim threshold : %.2f" % NAME_JARO_THRES
	print "Image similarity threshold      : %.2f" % IMG_SIM_THRES
	print "Getting Twitter developers starting with : jonskeet"
	print ''
	while len(DEVELOPERS) < DEVELOPERS_THRES:
		key = DEVELOPERS.iterkeys().next()
		print "Developer: " + key
		r.hset(hname, key, DEVELOPERS[key]) # insert into database
		lists = get_lists(key)
		for l in lists:
			try:
				for member in l.members()[:100]:
					if member.screen_name not in DEVELOPERS:
						# print "%20s" % member.screen_name,
						count += 1
						if count % 5 == 0:
							print ''
						new_member = {'twitter_name' : member.name, 'so_user' : None}
						DEVELOPERS[member.screen_name] = new_member
						r.hset(hname, member.screen_name, new_member)
			except TweepError as e:
				print e
				continue
			print "List : " + l.name + " done"
		time.sleep(5)


	print ''
	for k, v in DEVELOPERS.iteritems():
		try:
			user = api.get_user(screen_name=k)
		except TweepError as e:
			print e
			continue
		so_user = get_matching_so_profile(user._json)
		if r.hexists(hname, k):
			r_acct = r.hget(hname, k)
			if r_acct['so_user'] is None:
				so_user = get_matching_so_profile(user._json)
				time.sleep(2) # Delay to prevent rate limiting from SO
				if so_user is not None:
					print "Twitter(" + k + ") -> StackOverflow(" + so_user.display_name + ")"
					# Save into DB
					r.hset(hname, k, {"twitter_name" : user.name, "twitter_user" : user._json, "so_user" : so_user.__dict__})
		TOTAL_MATCHED_ACC = TOTAL_MATCHED_ACC + 1 if so_user is not None else TOTAL_MATCHED_ACC
		DEVELOPERS[k]['so_user'] = so_user.__dict__ if so_user is not None else None
	print ''
	print "Total targeted Twitter accounts : %d" % len(DEVELOPERS)
	print "Total SO accounts matched : %d" % TOTAL_MATCHED_ACC