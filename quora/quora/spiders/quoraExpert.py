# -*- coding: utf-8 -*-
import scrapy, time, redis, urllib
from quora.items import QuoraTopic, QuoraUser, QuoraMostViewedWriter
from quora.loaders import UserLoader

def topic_to_url(topic):
    return topic.replace(' ', '-')

class QuoraexpertSpider(scrapy.Spider):
    name = "quoraExpert"
    allowed_domains = ["quora.com"]
    base_url = 'https://www.quora.com'
    # start_urls = ['https://www.quora.com/topic/Indian-Administrative-Service-IAS-1/writers']
    start_urls = []

    def __init__(self):
        self.r_conn = redis.Redis(db=3)
        for keys in self.r_conn.scan_iter():
            self.start_urls.append('https://www.quora.com/topic/' + topic_to_url(keys) + '/writers')

    def parse(self, response):
        topic = response.xpath('//span[contains(@class, "TopicNameSpan")]/text()').extract()
        for item in response.xpath('//div[contains(@class,"LeaderboardListItem")]'):
            q_name = item.xpath('.//a[contains(@class, "user")]/text()').extract()
            if len(q_name) == 1:
                u = UserLoader(item=QuoraMostViewedWriter(), response=response)
                user_profile_url = item.xpath('.//a[contains(@class, "user")]/@href').extract()[0]
                u.add_value('q_name', q_name)
                u.add_value('q_profile_image_url', item.xpath('.//img[contains(@class, "profile_photo_img")]/@data-src').extract())
                u.add_value('q_topic', topic)
                u.add_value('q_num_views', item.xpath('.//div[contains(@class, "view_count")]/div[contains(@class, "num")]/text()').extract())
                u.add_value('q_short_description', item.xpath('.//span[contains(@class, "IdentitySig")]/span/span[contains(@class,"rendered_qtext")]/text()').extract())
                u.add_value('q_num_answers', item.xpath('.//a[contains(@class, "answers_link")]/text()').extract())
                u.add_value('q_last_crawled', time.time())
                yield u.load_item()