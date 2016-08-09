from scrapy.loader import ItemLoader
from scrapy.loader.processors import Join, MapCompose, TakeFirst
import re, locale

locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

def views_to_int(views):
	pattern = re.compile(u'^[0-9]+\.?[0-9]*(k|m)$')
	match = re.search(pattern, views)
	if match is None:
		try:
			return int(views) # '544'
		except ValueError as e: 
			return int(float(views) * 100) # '54.4'
	else:
		if match.group(1) == 'k':
			return int(float(views.split('k')[0]) * 1000)
		elif match.group(1) == 'm':
			return int(float(views.split('m')[0]) * 1000000)
		else:
			print match.group(1)
			return 1000

def extract_ans_from_str(ans_str):
	return locale.atoi(ans_str.split(' ')[1])

def str_to_int(int_str):
	return locale.atoi(int_str)

class TopicLoader(ItemLoader):
	default_output_processor = TakeFirst()
	q_num_questions_in       = MapCompose(views_to_int)
	q_num_followers_in       = MapCompose(views_to_int)
	q_num_edits_in           = MapCompose(views_to_int)

class UserLoader(ItemLoader):
	default_output_processor = TakeFirst()
	q_num_answers_in         = MapCompose(extract_ans_from_str)
	q_num_views_in           = MapCompose(str_to_int)