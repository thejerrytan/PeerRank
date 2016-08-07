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

class QuoraPipeline(object):
    def __init__(self):
        self.r_conn = redis.Redis(host=DBHOST, port=DBPORT, db=DBNAME)
        topics = set()
        for k in self.r_conn.scan_iter():
            topics.add(k)
        self.processed_keys = topics
        print self.processed_keys
        
    def process_item(self, item, spider):
        """item is QuoraTopic"""
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

    def close_spider(self, spider):
        pass