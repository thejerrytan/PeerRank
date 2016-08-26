# -*- coding: utf-8 -*-
import scrapy


class QuoratopicurlSpider(scrapy.Spider):
    name = "quoraTopicUrl"
    allowed_domains = ["www.quora.com"]
    start_urls = (
        'http://www.www.quora.com/',
    )

    def parse(self, response):
        pass
