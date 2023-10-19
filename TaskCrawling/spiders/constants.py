MAIN_URL = "https://www.yelp.com"
QUERY_URL = MAIN_URL + "/query/fragment"
COMMENT_PARAMS = {"rl": "en", "order_by": "relevance_desc"}
COMMENTS_LIMIT = 5
DATA_ATTRIBUTES = [
    "business_name",
    "business_rating",
    "number_of_reviews",
    "business_yelp_url",
    "business_website",
    "reviews",
]
