# -*- coding: utf-8 -*-
import scrapy, selenium, time
from quora.items import QuoraTopic, QuoraUser, QuoraMostViewedWriter
from quora.loaders import TopicLoader, UserLoader
from selenium import webdriver

def topic_to_url(topic):
    return topic.replace(' ', '-').replace(',', '').replace('.', '-').replace('/', '-')

def url_to_topic(topic):
    return topic.replace('-', ' ')

class QuoranewexpertSpider(scrapy.Spider):
    name = "quoraNewExpert"
    allowed_domains = ["www.quora.com"]
    base_url   = 'https://www.quora.com/'
    start_urls = ['https://www.quora.com/']
    handle_httpstatus_list = [400]

    def parse(self, response):
        driver = webdriver.Chrome()
        driver.get(self.start_urls[0])
        # Login
        time.sleep(2)
        email = driver.find_elements_by_name('email')[1]
        pw = driver.find_elements_by_name('password')[1]
        login = driver.find_element_by_css_selector('input[value="Login"]')
        email.send_keys('jerrytansk@gmail.com')
        pw.send_keys('RootBeer10*')
        time.sleep(2)
        login.click()
        time.sleep(2)

        # Extract topics
        topics = driver.find_elements_by_xpath('//a[contains(@class, "TrendingTopicNameLink")]')
        topics = [x.get_attribute('href').split('pinned/')[1] for x in topics]
        for topic in topics:
            yield scrapy.Request(self.base_url + 'topic/' + topic, callback=self.parseTopic)
            yield scrapy.Request(self.base_url + 'topic/' + topic + '/Writers', callback=self.parseExpert)
        
    def parseTopic(self, response):
        t = TopicLoader(item=QuoraTopic(), response=response)
        t.add_xpath('q_name', '//span[contains(@class,"TopicNameSpan")]/text()')
        t.add_xpath('q_description', '//div[contains(@class, "TruncatedTopicWiki")]/span[contains(@class,"rendered_qtext")]/text()')
        t.add_xpath('q_num_questions', '//a[contains(@class, "TopicQuestionsStatsRow")]/strong/text()')
        t.add_xpath('q_num_followers','//a[contains(@class, "TopicFollowersStatsRow")]/strong/text()')
        t.add_xpath('q_num_edits', '//a[contains(@class, "TopicEditsStatsRow")]/strong/text()')
        t.add_value('q_last_crawled', time.time())
        yield t.load_item()

    def parseExpert(self, response):
        if response.status == 400:
            print response
        else:
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
