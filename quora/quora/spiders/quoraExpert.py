# -*- coding: utf-8 -*-
import scrapy, time, redis, urllib, re, smtplib
from quora.items import QuoraTopic, QuoraUser, QuoraMostViewedWriter
from quora.loaders import UserLoader
from email.mime.text import MIMEText
import numpy as np

CRAWL_INTERVAL = 7 * 60 * 60 * 24

def topic_to_url(topic):
    return topic.replace(' ', '-').replace(',', '').replace('.', '-').replace('/', '-')

def url_to_topic(topic):
    return topic.replace('-', ' ')

class QuoraexpertSpider(scrapy.Spider):
    name = "quoraExpert"
    allowed_domains = ["quora.com"]
    base_url = 'https://www.quora.com'
    # start_urls = ['https://www.quora.com/topic/Indian-Administrative-Service-IAS-1/writers']
    start_urls = []
    handle_httpstatus_list = [404, 403, 429, 301]
    # download_delay = 10

    def __init__(self):
        self.r_conn = redis.Redis(db=3)
        self.r_404  = redis.Redis(db=15)
        self.urls_404    = self.r_404.smembers("quora:404")
        for keys in self.r_conn.scan_iter():
            start_url = 'https://www.quora.com/topic/' + topic_to_url(keys) + '/writers'
            # If need a fresh crawl and url is not in 404 set
            if not self.is_crawled(keys) and start_url not in self.urls_404:
                self.start_urls.append(start_url)
        print "Number of urls: %d " % len(self.start_urls)

    def is_crawled(self, topic):
        x = self.r_conn.hget(topic, 'q_experts_last_crawled') 
        if x is not None:
            return (time.time() - float(x)) < CRAWL_INTERVAL
        else:
            return False

    def __blacklist_url(self, url):
        self.r_404.sadd("quora:404", url)
        self.urls_404.add(url)

    def parse(self, response):
        # self.download_delay = abs(self.download_delay + np.random.standard_normal() * 10)
        if response.status == 404: # Not found
            print "(404) %s" % response.url
            self.__blacklist_url(response.url)
            pattern = re.compile(r'./topic/(.*)/writers')
            match = re.search(pattern, response.url)
            if match:
                self.r_conn.hset(url_to_topic(match.group(1)), 'q_experts_last_crawled', time.time())
        elif response.status == 403: # Forbidden, probably blocked by Quora, send email to me
            print "(403) %s" % response.url
            # msg = MIMEText('403 error has occured while crawling %s' % response.url)
            # msg['Subject'] = 'Scrapy error'
            # sender = 'sadm@peer-rank-i.comp.nus.edu.sg'
            # recipient = ['jerrytansk@gmail.com']
            # msg['From'] = sender
            # msg['To'] = ','.join(recipient)
            # s = smtplib.SMTP('localhost', timeout=10)
            # s.sendmail(sender, recipient, msg.as_string())
            # s.quit()
            raise scrapy.exceptions.CloseSpider('403 encountered')
        elif response.status == 429:
            raise scrapy.exceptions.CloseSpider('429 encountered')
        elif response.status == 301:
            self.__blacklist_url(response.url)
        else:
            print "(%s) %s" % (response.status, response.url)
            topic = response.xpath('//span[contains(@class, "TopicNameSpan")]/text()').extract()
            if len(topic) == 1: # topic is a list of strings
                topic = topic[0]
                # Mark topic as crawled
                self.r_conn.hset(topic, 'q_experts_last_crawled', time.time())
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