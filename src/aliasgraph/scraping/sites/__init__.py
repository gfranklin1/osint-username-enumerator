from aliasgraph.scraping import register
from aliasgraph.scraping.sites.devto import DevtoScraper
from aliasgraph.scraping.sites.github import GithubScraper
from aliasgraph.scraping.sites.reddit import RedditScraper

register(GithubScraper())
register(RedditScraper())
register(DevtoScraper())
