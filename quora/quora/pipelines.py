# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html
import redis, time
from scrapy.exceptions import DropItem

DBNAME = 3
DBHOST = 'localhost'
DBPORT = 6379

class QuoraTopicPipeline(object):
    def __init__(self):
        self.r_conn = redis.Redis(host=DBHOST, port=DBPORT, db=DBNAME)
        topics = set()
        for k in self.r_conn.scan_iter():
            topics.add(k)
        self.processed_keys = topics
        # print self.processed_keys
        
    def process_item(self, item, spider):
        """Only process if item is QuoraTopic"""
        if spider.name in ['quoran']:
            try:
                if item['q_name'] not in self.processed_keys:
                    self.r_conn.hmset(item['q_name'], item)
                    self.processed_keys.add(item['q_name'])
                else:
                    raise DropItem("Duplicate topic: %s" % item['q_name'])
            except Exception as e:
                print e
                pass
            return item
        else:
            return item

    def close_spider(self, spider):
        pass

class QuoraMostViewedWriterPipeline(object):
    def __init__(self):
        self.r_conn           = redis.Redis(host=DBHOST, port=DBPORT, db=4)
        self.expert_namespace = "quora:expert:"
        self.topic_namespace  = "quora:topics:"

    def process_item(self, item, spider):
        """Only process if item is QuoraMostViewedWriter"""

        if spider.name in ['quoraExpert']:
            try:
                if 'q_name' in item:
                    topic = item.pop('q_topic', None)
                    self.r_conn.hmset(self.expert_namespace + item['q_name'], item)
                    self.r_conn.sadd(self.topic_namespace + item['q_name'], topic)
            except Exception as e:
                print e
            return item
        else:
            return item

    def close_spider(self, spider):
        pass