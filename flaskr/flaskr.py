import os, pprint, json, sys, time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mysql.connector
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash
from list import PeerRank

app = Flask(__name__)
app.config.from_object(__name__)
pr = PeerRank()

# Load default config and override config from an environment variable
app.config.update(dict(
	DATABASE=os.path.join(app.root_path, 'flaskr.db'),
	SECRET_KEY='development key',
	USERNAME='root',
	PASSWORD='root'
))
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

@app.route('/', methods=['GET', 'POST'])
def index():
	return render_template('index.html')

@app.route('/search', methods=['GET'])
def search():
	start = time.time()
	query = unicode(request.args.get('q'))
	include_so = True if request.args.get('include_so') is not None else False
	include_quora = True if request.args.get('include_q') is not None else False
	# results = pr.get_twitter_rankings(query, include_so=True)
	results = {}
	time_taken = time.time() - start
	num_results = len(results.keys())
	context = {
		'query' : query,
		'include_so' : include_so,
		'include_q' : include_quora,
		'time_taken' : time_taken,
		'num_results' : num_results,
		'results' : results
	}
	# return render_template('index.html', results=results, query=query, num_results=num_results, time_taken=time_taken)
	return render_template('index.html', **context)