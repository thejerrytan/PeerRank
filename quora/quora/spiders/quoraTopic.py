# -*- coding: utf-8 -*-
import scrapy, time, redis, re
from quora.items import QuoraTopic, QuoraUser, QuoraMostViewedWriter
from quora.loaders import TopicLoader

class QuoratopicSpider(scrapy.Spider):
    """This spider crawls all topics indexed by Quora on their sitemap in an alphabetical order"""
    name = "quoraTopic"
    allowed_domains = ["www.quora.com"]
    base_url   = 'https://www.quora.com'
    start_urls = ['https://www.quora.com/sitemap/alphabetical_topics/all']

    def parse(self, response):
        urls = response.xpath('//span[contains(@class, "SitemapAlphaTopicsMain")]/a/@href').extract()
        for url in urls:
        	response = scrapy.Request(self.base_url + url, callback=self.parseTopicList)
        	yield response

    def parseTopicList(self, response):
    	urls = response.xpath('//a/@href').extract()
    	pattern = re.compile('^https://www.quora.com/topic/*')
    	for url in urls:
    		if pattern.match(url) is not None:
    			print url
    			req = scrapy.Request(url, callback=self.parseTopic)
    			yield req

    def parseTopic(self, response):
    	t = TopicLoader(item=QuoraTopic(), response=response)
        t.add_xpath('q_name', '//span[contains(@class,"TopicNameSpan")]/text()')
        t.add_xpath('q_description', '//div[contains(@class, "TruncatedTopicWiki")]/span[contains(@class,"rendered_qtext")]/text()')
        t.add_xpath('q_num_questions', '//a[contains(@class, "TopicQuestionsStatsRow")]/strong/text()')
        t.add_xpath('q_num_followers','//a[contains(@class, "TopicFollowersStatsRow")]/strong/text()')
        t.add_xpath('q_num_edits', '//a[contains(@class, "TopicEditsStatsRow")]/strong/text()')
        t.add_value('q_last_crawled', time.time())
        yield t.load_item()
