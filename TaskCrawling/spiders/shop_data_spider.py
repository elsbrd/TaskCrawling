import json
import scrapy

from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Union, Generator
from scrapy.http import TextResponse
from constants import (
    MAIN_URL,
    QUERY_URL,
    COMMENT_PARAMS,
    COMMENTS_LIMIT,
    DATA_ATTRIBUTES,
)


class ShopDataSpider(scrapy.Spider):
    name = "shop_info"
    allowed_domains = ["www.yelp.com"]

    def __init__(self, **kwargs) -> None:
        """
        Initialize spider with query parameters.

        :param kwargs: Keyword arguments.
        """
        super().__init__(**kwargs)
        self.query_data = {
            "find_desc": input("Enter the desired category (like 'contractors'): "),
            "find_loc": input(
                "Specify the location (for instance, 'San Francisco, CA'): "
            ),
            "start": "0",
        }

    def initial_queries(self) -> Generator:
        """
        Generate initial requests for the spider.

        :return: A generator yielding the initial requests.
        """
        yield scrapy.FormRequest(
            url=QUERY_URL,
            method="GET",
            formdata=self.query_data,
            callback=self.extract_data,
        )

    def extract_data(self, response: TextResponse, **kwargs) -> Generator:
        """
        Extract data from the search page and generate further requests or items.

        :param response: A TextResponse object containing the page content.
        :param kwargs: Additional arguments.
        :return: A generator yielding further requests or items.
        """
        page_data = json.loads(response.text)
        data_list = [
            data
            for data in page_data["searchPageProps"]["mainContentComponentsListProps"]
            if "bizId" in data and not data["searchResultBusiness"]["isAd"]
        ]

        for data in data_list:
            yield from self._extract_shop_data(data)

        navigation = self._gather_navigation_data(page_data)
        if self._is_next_page_available(navigation):
            next_page_data = {
                "start": str(navigation["startResult"] + navigation["resultsPerPage"])
            }
            yield scrapy.FormRequest(
                url=QUERY_URL,
                method="GET",
                formdata={**self.query_data, **next_page_data},
                callback=self.extract_data,
            )

    def _extract_shop_data(self, data: dict) -> Generator:
        """
        Extract individual shop data and generate further requests or items.

        :param data: A dictionary representing a shop data.
        :return: A generator yielding further requests or items.
        """
        shop = data["searchResultBusiness"]
        shop_id = data["bizId"]
        comments_url = f"{MAIN_URL}/biz/{shop_id}/review_feed"

        yield scrapy.FormRequest(
            url=comments_url,
            method="GET",
            formdata=COMMENT_PARAMS,
            callback=self.extract_comments,
            meta={
                "business_name": shop["name"],
                "business_rating": shop["rating"],
                "number_of_reviews": shop["reviewCount"],
                "business_yelp_url": f"{MAIN_URL}{shop['businessUrl']}",
                "business_website": None,
            },
        )

    def extract_website(
        self, response: TextResponse
    ) -> Dict[str, Union[str, List[Dict[str, str]]]]:
        """
        Extract the website URL for a shop.

        :param response: A TextResponse object containing the shop details.
        :return: A dictionary with the shop details including the website URL.
        """
        site_link = response.css("a[href^='/biz_redir']").xpath("@href").get()
        if site_link:
            parsed_link = urlparse(site_link)
            site_link = parse_qs(parsed_link.query)["url"][0]

        attributes = {
            key: value for key, value in response.meta.items() if key in DATA_ATTRIBUTES
        }
        return {**attributes, "shop_website": site_link}

    def extract_comments(self, response: TextResponse, **kwargs) -> Generator:
        """
        Extract comments for a shop and generate further requests or items.

        :param response: A TextResponse object containing the reviews content.
        :param kwargs: Additional arguments.
        :return: A generator yielding further requests or items.
        """
        page_data = json.loads(response.text)
        user_comments = page_data["reviews"][:COMMENTS_LIMIT]
        comments_data = {
            "user_comments": [
                {
                    "reviewer_name": comment["user"]["markupDisplayName"],
                    "reviewer_location": comment["user"]["displayLocation"],
                    "review_date": comment["localizedDate"],
                }
                for comment in user_comments
            ],
        }

        yield scrapy.Request(
            url=response.meta["business_yelp_url"],
            callback=self.extract_website,
            meta={**response.meta, **comments_data},
        )

    @staticmethod
    def _gather_navigation_data(
        page_data: Dict[str, Union[str, List[Dict[str, str]]]]
    ) -> dict:
        """
        Retrieve pagination information from a page data.

        :param page_data: The dictionary containing the response data.
        :return: A dictionary with pagination information.
        """
        content = page_data["searchPageProps"]["mainContentComponentsListProps"]
        navigation = next(item for item in content if item.get("type") == "pagination")
        return navigation["props"]

    def _is_next_page_available(self, navigation: dict) -> bool:
        """
        Determine if there's a subsequent page based on the navigation info.

        :param navigation: A dictionary with pagination information.
        :return: True if there's a subsequent page, otherwise False.
        """
        remaining_results = navigation["totalResults"] - navigation["startResult"]
        return remaining_results > navigation["resultsPerPage"]
