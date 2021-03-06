# -*- coding: utf-8 -*-
import scrapy, time, redis, re
from quora.items import QuoraTopic, QuoraUser, QuoraMostViewedWriter
from quora.loaders import TopicLoader
from random import shuffle
import numpy as np

CRAWL_INTERVAL = 7 * 60 * 60 * 24

class QuoratopicSpider(scrapy.Spider):
    """This spider crawls all topics indexed by Quora on their sitemap in an alphabetical order"""
    name = "quoraTopic"
    allowed_domains = ["www.quora.com"]
    base_url   = 'https://www.quora.com'
    start_urls = []
    # download_delay = 10
    handle_httpstatus_list = [403, 429]

    def __init__(self):
        self.r_conn       = redis.Redis(db=15)
        self.r_topic_urls = self.r_conn.smembers("quora:topicUrls")
        self.start_urls   = list(map(lambda x: self.base_url + x if not self.is_crawled(self.base_url+x) else '', self.r_topic_urls))
        shuffle(self.start_urls)

    def is_crawled(self, topic_url):
        x = self.r_conn.hget(topic_url, 'q_last_crawled')
        if x is not None:
            return (time.time() - float(x)) < CRAWL_INTERVAL
        else:
            return False

    def parse(self, response):
        if response.status == 403:
            raise scrapy.exceptions.CloseSpider('403 encountered')
        elif response.status == 429:
            raise scrapy.exceptions.CloseSpider('429 encountered')
        else:
            # Set topic url as crawled
            self.r_conn.hset(response.url.split('?')[0], 'q_last_crawled', time.time())
            next = response.xpath('//a[contains(@rel, "next")]/@href').extract()
            if len(next) == 1:
                next_page = scrapy.Request(self.base_url + next[0], callback=self.parse)
                yield next_page
            urls = response.xpath('//a/@href').extract()
            pattern = re.compile('^https://www.quora.com/topic/*')
            for url in urls:
                if pattern.match(url) is not None:
                    # print url
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
