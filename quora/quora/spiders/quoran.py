# -*- coding: utf-8 -*-
import scrapy, time, redis
from quora.items import QuoraTopic, QuoraUser, QuoraMostViewedWriter
from quora.loaders import TopicLoader

class QuoranSpider(scrapy.Spider):
    """This spider crawls related topics, given a starting topic page, in a breadth-first-search manner"""
    name            = "quoran"
    allowed_domains = ["quora.com"]
    base_url        = 'https://www.quora.com'
    start_urls      = ['https://www.quora.com/topic/Computer-Programming']
    target          = 100

    def __init__(self):
        self.count = 0        

    def parse(self, response):
        t = TopicLoader(item=QuoraTopic(), response=response)
        t.add_xpath('q_name', '//span[contains(@class,"TopicNameSpan")]/text()')
        t.add_xpath('q_description', '//div[contains(@class, "TruncatedTopicWiki")]/span[contains(@class,"rendered_qtext")]/text()')
        t.add_xpath('q_num_questions', '//a[contains(@class, "TopicQuestionsStatsRow")]/strong/text()')
        t.add_xpath('q_num_followers','//a[contains(@class, "TopicFollowersStatsRow")]/strong/text()')
        t.add_xpath('q_num_edits', '//a[contains(@class, "TopicEditsStatsRow")]/strong/text()')
        t.add_value('q_last_crawled', time.time())
        self.count += 1
        if self.count % self.target == 0: print "Processed %s topics (including duplicates)" % self.count
        yield t.load_item()
        for url in response.xpath("//a[contains(@class, 'RelatedTopicsListItem')]/@href").extract():
            # print url
            yield scrapy.Request(self.base_url+url, callback=self.parse)

    def parseTopic(self, response):
        pass