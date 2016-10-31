import os, pprint, json, sys, time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mysql.connector
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash
from list import PeerRank

app = Flask(__name__)
app.config.from_object(__name__)
pr = PeerRank()

@app.route('/', methods=['GET', 'POST'])
def index():
	return render_template('index.html')

@app.route('/search', methods=['GET'])
def search():
	start         = time.time()
	query         = unicode(request.args.get('q'))
	include_so    = True if request.args.get('include_so') is not None else False
	include_quora = True if request.args.get('include_q') is not None else False
	results       = pr.get_twitter_rankings(query, include_so=include_so, include_q=include_quora)
	(user_profiles, stats) = pr.batch_get_twitter_profile(results)
	time_taken    = time.time() - start
	num_results   = len(results)
	print(stats)
	context = {
		'query' : query,
		'include_so' : include_so,
		'include_q' : include_quora,
		'time_taken' : time_taken,
		'num_results' : num_results,
		'results' : user_profiles,
		'stats' : stats
	}
	return render_template('index.html', **context)