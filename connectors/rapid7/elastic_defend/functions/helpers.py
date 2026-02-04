
"""Helper functions for the Elastic Defend API client."""

from logging import Logger
from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# API Documentation:
# entity_store - https://www.elastic.co/docs/api/doc/kibana/operation/operation-listentities
# endpoint - https://www.elastic.co/docs/api/doc/kibana/operation/operation-getendpointmetadatalist

ENDPOINT_URLS = {
    "host_entity": "/api/entity_store/entities/list",
    "endpoint": "/api/endpoint/metadata",
}


class ElasticDefendClient:
    """A client for the Elastic Defend API."""

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings
        self.base_url = self.settings.get("url")

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()
        self.session.headers.update({
            "Authorization": f"ApiKey {self.settings.get('api_key')}"
        })

    def make_request(self, path: str, params: dict | None = None):
        """Make a request to the specified endpoint with optional query parameters.

        Args:
            path (str): The path for the endpoint to query.
            params (dict, optional): Query parameters to include in the request. Defaults to None.

        Returns:
            dict: The JSON response from the API if the request is successful, otherwise None.
        """
        url = furl(self.base_url).add(path=path).add(query_params=params)
        response = self.session.get(str(url))
        response.raise_for_status()
        return response.json()

    def get_records(self, endpoint_key: str, params: dict | None = None):
        """Get records from the specified endpoint with optional query parameters.

        Args:
            endpoint_key (str): The key for the endpoint to query.
            params (dict | None): Query parameters to include in the request. Defaults to None.

        Returns:
            dict: The JSON response from the API if the request is successful, otherwise None.
        """
        if endpoint_key not in ENDPOINT_URLS:
            raise ValueError(f"Invalid endpoint key: {endpoint_key}")

        if params is None:
            params = {}

        if endpoint_key == "host_entity":
            # For host_entity endpoint, we need to specify the entity types in the query parameters
            # this endpoint will support user, host, service, or generic entities,
            # but as of now we are only interested in host entities,
            # in future we can add support for other entity types as needed
            params['entity_types'] = "host"
        make_request_response = self.make_request(path=ENDPOINT_URLS[endpoint_key], params=params)
        return make_request_response
