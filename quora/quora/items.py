# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

import scrapy


class QuoraTopic(scrapy.Item):
    # define the fields for your item here like:
    q_name = scrapy.Field()
    q_description = scrapy.Field()
    q_num_questions = scrapy.Field()
    q_num_followers = scrapy.Field()
    q_num_edits = scrapy.Field()
    q_last_crawled = scrapy.Field()
    
    def __repr__(self):
        return repr({"q_name":self['q_name']})

class QuoraUser(scrapy.Item):
    # define the fields for your item here like:
    q_name = scrapy.Field()
    q_short_description = scrapy.Field()
    q_long_description = scrapy.Field()
    q_location = scrapy.Field()
    q_profile_image_url = scrapy.Field()
    q_last_30_day_views = scrapy.Field()
    q_all_time_views = scrapy.Field()
    q_num_followers = scrapy.Field()
    q_num_following = scrapy.Field()
    q_num_edits = scrapy.Field()
    q_twitter_link = scrapy.Field()
    q_last_crawled = scrapy.Field()
    
    def __repr__(self):
        return repr({"q_name":self['q_name']})    

class QuoraMostViewedWriter(scrapy.Item):
    q_name = scrapy.Field()
    q_profile_image_url = scrapy.Field()
    q_topic = scrapy.Field()
    q_num_views = scrapy.Field()
    q_short_description = scrapy.Field()
    q_num_answers = scrapy.Field()
    q_last_crawled = scrapy.Field()

    def __repr__(self):
        return repr({"q_name":self['q_name']})