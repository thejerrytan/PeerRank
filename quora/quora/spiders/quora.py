# -*- coding: utf-8 -*-
import scrapy, sys
# sys.path.append('../')
from scrapy.crawler import CrawlerProcess

class KickSpider(scrapy.Spider):
	name            = "PeerRank"
	base_url        = 'https://www.kickstarter.com/discover/advanced?sort=magic&seed=%d&page=' % SEED
	allowed_domains = ["www.quora.com"]
	start_urls      = [base_url+str(page) for page in xrange(0,END_PAGE)]

	def parse(self, response):
		global current_page
		current_page += 1
		print "[INFO] Starting page %d" % current_page
		for url in response.css('div.project-thumbnail a::attr(href)'):
			base_url = response.urljoin(url.extract())[:-14]
			request = scrapy.Request(base_url+"/description", callback=self.parseProject)
			request.meta['base_url'] = base_url
			yield request

	def parseUpdates(self, response):
		p = response.meta['project']
		u = response.meta['user']
		r = response.meta['rewards'] # list of rewards
		p.add_value('start_date', response.css('div.timeline__divider.timeline__divider--launched div.timeline__divider_content div.h5.bold time.js-adjust-time::text').extract())
		yield {
			'user' : u.load_item(), 
			'project' : p.load_item(),
			'rewards' : r
		}

	def parseRewards(self, response):
		count = 1
		rewards = []
		for reward in response.css('div.mb6.mobile-hide div.NS_projects__rewards_list ol li'):
			r = RewardLoader(item=Reward(), response=response)
			r.add_value('tier', count)
			r.add_value('benefits', ''.join(reward.css('div.pledge__reward-description').xpath('node()').extract()))
			r.add_css('project_owner_email', 'div.mobile-hide.py4.px2 div.NS_projects__header.center p:last-child a.remote_modal_dialog.green-dark::text')
			r.add_css('project_title', 'div.mobile-hide.py4.px2 div.NS_projects__header.center h2 a::text')
			r.add_value('min_funding', reward.css('div.pledge__currency-conversion h5.regular.grey-dark span::text').extract())
			reward = r.load_item()
			count += 1
			rewards.append(reward)
		return rewards

	def parseProject(self, response):
		u = UserLoader(item=User(), response=response)
		u.add_css('email', 'div.mobile-hide.py4.px2 div.NS_projects__header.center p:last-child a.remote_modal_dialog.green-dark::text')
		u.add_css('name', 'div.mobile-hide.py4.px2 div.NS_projects__header.center p:last-child a.remote_modal_dialog.green-dark::text')
		u.add_css('password', 'div.mobile-hide.py4.px2 div.NS_projects__header.center p:last-child a.remote_modal_dialog.green-dark::text')
		u.add_value('is_admin', False)
		u.add_value('is_active', True)

		p = ProjectLoader(item=Project(), response=response)
		p.add_css('title', 'div.mobile-hide.py4.px2 div.NS_projects__header.center h2 a::text')
		p.add_value('description', ''.join(response.xpath('//div[@class="full-description js-full-description responsive-media formatted-lists"]/node()').extract()))
		p.add_css('owner', 'div.mobile-hide.py4.px2 div.NS_projects__header.center p:last-child a.remote_modal_dialog.green-dark::text')
		p.add_css('category', 'div.mobile-hide div.NS_projects__category_location a:nth-child(2)::text')
		p.add_css('target_funds', 'div.col.col-12.mb1.stat-item span.money.no-code::text')
		p.add_css('img_url', 'div#video-section.project-image img.fit::attr(src)')
		p.add_css('img_url', 'div#video_pitch.video-player img.has_played_hide::attr(src)')
		p.add_value('is_active', True)
		p.add_value('is_deleted', False)
		p.add_css('end_date', 'div.NS_projects__deadline_copy p time.js-adjust-time::text')
		request = scrapy.Request(response.meta['base_url']+"/updates", callback=self.parseUpdates)
		request.meta['project'] = p
		request.meta['user'] = u
		request.meta['rewards'] = self.parseRewards(response)
		yield request

if __name__ == "__main__":
	process = CrawlerProcess({
		'USER_AGENT' : 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)'
	})

	process.crawl(KickSpider)
	process.start()