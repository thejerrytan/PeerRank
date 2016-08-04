PeerRank
Identifying topical experts on Twitter using information from StackOverflow and Quora

Architecture
- Redis database
- Scrapy crawler for crawling Quora

Methodology
Part i - Linking up accounts on different social networks
1) Link up users from Twitter to their accounts on Quora and StackOverflow
2) Discover Twitter accounts using a few seed accounts on Twitter Lists, and do a recursive crawl
3) Decision of when to stop crawling a non-trivial one which requires investigation
4) Identify foreign accounts using i) Name jaro-wrinkler string-similarity search, ii) Location string matching, iii) Goldberg profile image similarity
5) Repeat crawl periodically every 7 days

Part ii - Ranking of experts individually on each OSN for a given topic query
1) Native - tag-score on StackOverflow, number of views on Quora, ? (no native methods) on Twitter
	i) Following Cognos, for each user, obtain topic vector {(t, f)} where t is set of topics (tags for StackOverflow, topics for Quora on user profile page, inferred from lists for Twitter)
	   and f is i)score for tags for StackOverflow, ii)number of views for topic (use most viewed writers page) on Quora, iii)frequency of occurence of topic in the names and desc of lists containing the user
	ii) Obtain topical similarity between the topic vector and search query using Cover Density Ranking, multiply by log(f) to arrive at final rankings
2) PageRank - using followee-follower graph of data on Quora, StackOverflow? (BONUS)
3) ExpertiseRank (variant of PageRank) - http://www.ladamic.com/papers/expertiserank/ExpertiseRank.pdf, extract User-helped->User graph and run PageRank (BONUS)

Part iii - Combining rankings on individual OSNs into overall score
1) Tier 1 weighting - proportion of time user spends on each OSN (users/id/network_activity for SO, tweet frequency on Twitter, www.quora.com/profile/{username}/activity on Quora)
2) Tier 2 weighting - MAUs of each OSN

Analysis - How did the inclusion of external OSNs i) Change the ranking of experts on Twitter and ii) Improve the system overall

Evaluation of System
1) Using human evaluators - blind testing (BONUS)

Outstanding questions
1) How to automate seeding of accounts in order to automatically discover new topics
2) What if we change the analysis to start from Quora and find matching accounts on Twitter?
3) How do we determine the activity of each user on a OSN

Redis Schema
Default DB - 0
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
	"so_account_id" -> "11683"
	"so_last_crawled" -> "1470072846.222038"
	"so_url" -> "http://stackoverflow.com/users/22656"
	"so_creation_date" -> "2008-09-26 20:05:05"
	"so_display_name" -> "Jon Skeet"
	"so_location" -> "Reading, United Kingdom",
	"so_profile_image" -> "https://www.gravatar.com/avatar/6d8ebb117e8d83d74ea95fbdd0f87e13?s=128&d=identicon&r=PG"
	"so_reputation" -> "883882"
	"so_tags" ->
		""

Scraping Quora:
What is needed?
1) Start from https://www.quora.com/topic/Computer-Programming
2) Look for more topic under related topics section, repeat step 1
3) If most viewed writers section exist, follow link
4) Scrap number of views, username,
5) Follow username link to user profile about page, scrap user profile
6) Get username, description, followers, following, location, links to social network, all time views, last 30-day views, profile_image_url, Knows About section

Quora User Activity
For every user:
1) Go to https://www.quora.com/profile/Ken-Mazaika/activity
2) Count number of posts between start and end time to arrive at activity frequency