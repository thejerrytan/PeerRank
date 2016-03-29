# -*- coding: utf-8 -*-
import scrapy

class QuoranSpider(scrapy.Spider):
    name = "quoran"
    allowed_domains = ["quora.com"]
    start_urls = (
        'https://www.quora.com/',
    )

    def parse(self, response):
        response.get
