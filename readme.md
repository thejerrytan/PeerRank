# PeerRank
Identifying topical experts on Twitter using information from StackOverflow and Quora

# Architecture
- Redis database == v3.2.0 (Compile from Redis.org source, not brew install!)
- Scrapy crawler for crawling Quora

# Methodology
## Part i - Linking up accounts on different social networks
1. Link up users from Twitter to their accounts on Quora and StackOverflow
2. Discover Twitter accounts using a few seed accounts on Twitter Lists, and do a recursive crawl
3. Decision of when to stop crawling a non-trivial one which requires investigation
4. Identify foreign accounts using i) Name jaro-wrinkler string-similarity search, ii) Location string matching, iii) Goldberg profile image similarity
5. Repeat crawl periodically every 7 days

## Part ii - Ranking of experts individually on each OSN for a given topic query
1. Native - tag-score on StackOverflow, number of views on Quora, ? (no native methods) on Twitter
	i) Following Cognos, for each user, obtain topic vector {(t, f)} where t is set of topics (tags for StackOverflow, topics for Quora on user profile page, inferred from lists for Twitter)
	   and f is i)score for tags for StackOverflow, ii)number of views for topic (use most viewed writers page) on Quora, iii)frequency of occurence of topic in the names and desc of lists containing the user
	ii) Obtain topical similarity between the topic vector and search query using Cover Density Ranking, multiply by log(f) to arrive at final rankings
2. PageRank - using followee-follower graph of data on Quora, StackOverflow? (BONUS)
3. ExpertiseRank (variant of PageRank) - http://www.ladamic.com/papers/expertiserank/ExpertiseRank.pdf, extract User-helped->User graph and run PageRank (BONUS)

## Part iii - Combining rankings on individual OSNs into overall score
1. Tier 1 weighting - proportion of time user spends on each OSN (users/id/network_activity for SO, tweet frequency on Twitter, www.quora.com/profile/{username}/activity on Quora)
2. Tier 2 weighting - MAUs of each OSN

# Analysis - How did the inclusion of external OSNs i) Change the ranking of experts on Twitter and ii) Improve the system overall

# Evaluation of System
1. Using human evaluators - blind testing (BONUS)

# Outstanding questions
1. How to automate seeding of accounts in order to automatically discover new topics
2. What if we change the analysis to start from Quora and find matching accounts on Twitter? (Much faster and easier, because we are starting with experts on Quora and after we find the matching twitter account, we can follow Cognos methodology to arrive at expert ranking)
3. How do we determine the activity of each user on a OSN (Activity on Quora, last updated on StackOverflow, )
4. How to overcome IP based throttle limits imposed by SE
5. How to increase overall throughput to process 3 mil users in 7 days (0.2s per user)? Now, it takes ~ 10s per user, 347 days in total

# Issues
1. How to ensure all topics on Quora are scraped. How to ensure new topics are covered? (Alphabetical site map, not sure how often it is updated)
2. How to maximize data extraction from Quora (Fast in, fast out)

# Redis Schema
## DB - 0 (Twitter profiles)
	"twitter_screen_name" (HASH)
		"twitter_id" -> "18193572"
		"twitter_name" -> "Jon Skeet"
		"twitter_screen_name" -> "jonskeet"
		"twitter_profile_image_url" -> "http://pbs.twimg.com/profile_images/553764312716550144/ViDhuySK_normal.jpeg"
		"twitter_verified" -> "False"
		"twitter_description" -> "Christian, husband (of @HollyKateSkeet), father, feminist, software engineer (currently at Google), author, @stackoverflow contributor."
		"twitter_created_at" -> "Wed Dec 17 17:14:47 +0000 2008"
		"twitter_listed_count" -> "1804"
		"twitter_location" -> "Reading, UK"
		"twitter_last_crawled" -> "1470072821.846624"
		--------------if matched with StackExchange-----------------
		"so_account_id" -> "11683"
		"so_last_crawled" -> "1470072846.222038"
		"so_url" -> "http://stackoverflow.com/users/22656"
		"so_creation_date" -> "2008-09-26 20:05:05"
		"so_display_name" -> "Jon Skeet"
		"so_location" -> "Reading, United Kingdom",
		"so_profile_image" -> "https://www.gravatar.com/avatar/6d8ebb117e8d83d74ea95fbdd0f87e13?s=128&d=identicon&r=PG"
		"so_reputation" -> "883882"

## DB - 1 (StackExchange tags)
	"reverseengineering.stackexchange.com:offset"
		"count" -> 6
		"name" -> offset
		"site" -> "reverseengineering.stackexchange.com"

## DB - 2 (StackExchange top answerers for every tag)
	"set:stackexchange:matched_experts_set" : REDIS.SET("magento.stackexchange.com:ctasca",...)
	"topics:magento.stackexchange.com:user" : REDIS.SET("magento.stackexchange.com:topic1", "stackoverflow.com:topic2")
	"magento.stackexchange.com:ctasca"
		"so_reputation" -> 31
		"so_profile_image" -> "https://i.stack.imgur.com/Q7lUq.jpg?s=128&g=1"
		"so_display_name" -> "ctasca"
		"so_last_crawled" -> "1470509582.730663"
		"so_id" -> 5045
		"so_link" -> "http://magento.stackexchange.com/users/5045/ctasca"
		--------------if matched with Twitter profile---------------
		"twitter_id" -> ""
		"twitter_name" -> ""
		"twitter_screen_name" -> ""
		"twitter_profile_image_url" -> ""
		"twitter_verified" -> ""
		"twitter_description" -> ""
		"twitter_created_at" -> ""
		"twitter_listed_count" -> ""
		"twitter_location" -> ""
		"twitter_last_crawled" -> ""

## DB - 3 (Quora Topics)
	"topic"
		"q_name" -> "Computer Programming"
		"q_description" -> "Computer programming (often shortened to programming) is a process that leads from an original formulation of a computing problem to executable programs. It involves activities such as analysis, understanding, and generica..."
		"q_num_questions" -> "567000"
		"q_num_followers" -> "5000000"
		"q_num_edits" -> "567"
		"q_last_crawled" -> "1470596056.640988"
		"q_experts_last_crawled" -> "1470596056.640988"

## DB - 4 (Quora most viewed writers for every topic)
	"quora:matched_experts_set" : REDIS.SET("quora:expert:writer_name",...)
	"quora:topics:writer_name" : REDIS.SET("topic1","topic2"...)
	"quora:expert:writer_name"
		"q_name" -> "Sanjay Nandan",
		"q_short_description" -> "",
		"q_profile_image_url" -> "https://qph.ec.quoracdn.net/main-thumb-43516739-100-tnrxfcqmwqvzcrmhydixcdlheqozuznw.jpeg",
		"q_num_views" -> "88833",
		"q_last_crawled" -> "1470904208.092124"
		--------------if matched with Twitter profile---------------
		"twitter_id" -> ""
		"twitter_name" -> ""
		"twitter_screen_name" -> ""
		"twitter_profile_image_url" -> ""
		"twitter_verified" -> ""
		"twitter_description" -> ""
		"twitter_created_at" -> ""
		"twitter_listed_count" -> ""
		"twitter_location" -> ""
		"twitter_last_crawled" -> ""

## DB - 5 Combined User (Used for fast lookup given a site and username, what are their linked accounts, if any)
	"quora:username" -> Hash("twitter_screen_name": 'username')
	"stackexchange:username" -> Hash("twitter_screen_name": 'username')
	"twitter:username" -> Hash("so_display_name": 'site.stackexchange.com:username', "quora_name": 'username')

## DB - 6 Combined Topics (topic will be used for cover density ranking with user query)
	"site:topic1" -> Zset(<site:user1 : score>, <site:user2: score>)
	"site:topic2" -> Zset(<site:user3 : score, <site:user4: score>)
	"site:topic3" -> Zset(<site:user1 : score>, <site:user4 : score>)
	(Score is expertise measure on respective site - reputation for StackOverflow, views on Quora, lg(listed frequency) on Twitter)

## DB - 7 Twitter user_id -> Screen_name lookup

## DB - 15 Utility (Used to help with scraping)
	"quora:404" -> Set("https://www.quora.com/404.url", "https://www.quora.com/301.url")
	"quora:topicUrls" -> Set("/sitemap/alphabetical_topics/jp")
	"https://www.quora.com/sitemap/alphabetical_topics/n0" -> Hash("q_last_crawled" -> 12345534.223454)
	...

# Scraping Quora:
What is needed?
1. Start from https://www.quora.com/topic/Computer-Programming (example)
2. Look for more topic under related topics section, repeat step 1
3. If most viewed writers section exist, follow link e.g. url - https://www.quora.com/topic/Computer-Programming/writers
4. Scrap number of views, username,
5. Follow username link to user profile about page, scrap user profile
6. Get username, description, followers, following, location, links to social network, all time views, last 30-day views, profile_image_url, Knows About section

# Quora User Activity
For every user:
1. Go to https://www.quora.com/profile/Ken-Mazaika/activity (example)
2. Count number of posts between start and end time to arrive at activity frequency

# Setup:
1. Create virtualenv: mkvirtualenv fyp
2. Dependencies: pip install -r requirements.txt
3. Install framework python either by symbolic linking from MAC OS system installed version or follow tutorial here: 
   http://matplotlib.org/faq/virtualenv_faq.html. Name the executable as fpython (frameworkpython)

# How to run:
DEVELOPMENT
1. "workon fyp" (name of your virtualenv) to get into the virtualenv
2. fpython (name_of_pythonfile.py)

# PRODUCTION
1. Foreground: fpython list.py
2. Background, redirect output to logfile: fpython list.py & 2>3 path/to/outfile.log
3. Daemon: Circus: circusd --daemon  circus.ini (use circusctl to control the daemon)

# REFERENCES
1. Cognos - https://www.mpi-sws.org/~gummadi/papers/twitter_wtf.pdf
2. Cover Density Ranking - http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.12.1615&rep=rep1&type=pdf
3. StackExchange API - https://api.stackexchange.com/
4. Twitter API - https://dev.twitter.com/rest/public/search
5. Circus - https://circus.readthedocs.io/en/0.9.2/
6. Scrapy - http://scrapy.org/