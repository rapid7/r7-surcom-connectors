
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""

from datetime import datetime, timedelta, timezone
from logging import Logger
from typing import Generator

from furl import furl
from r7_surcom_api import HttpSession

from .sc_settings import Settings

# from https://platform.openai.com/docs/api-reference/users/list
USERS_PER_PAGE = 100

# from https://platform.openai.com/docs/api-reference/usage/completions
# Usage API limits per bucket_width=1d: max 31 buckets
USAGE_DAILY_LIMIT = 31


class OpenAIClient:

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        # Set base URL to OpenAI API (hardcoded)
        self.base_url = "https://api.openai.com"

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()

        # Enforce TLS verification
        self.session.verify = True

        # Configure Bearer token authentication
        admin_api_key = settings.get("admin_api_key")
        self.session.headers.update({
            "Authorization": f"Bearer {admin_api_key}"
        })

    def test_connection(self) -> bool:
        """
        Validate connectivity by making a test request to the
        Organization Users API and Usage API.
        """
        # Test Organization Users API
        url = furl(self.base_url).set(path=["v1", "organization", "users"]).url
        params = {"limit": 1}

        self.logger.info("Testing connection to OpenAI Organization Users API")
        r = self.session.get(url, params=params)
        r.raise_for_status()

        # Test Usage API
        usage_url = furl(self.base_url).set(
            path=["v1", "organization", "usage", "completions"]
        ).url
        start_time = int(
            (datetime.now(timezone.utc) - timedelta(days=1)).timestamp()
        )
        params = {"start_time": start_time, "limit": 1}

        self.logger.info("Testing connection to OpenAI Usage API")
        r = self.session.get(usage_url, params=params)
        r.raise_for_status()

        return True

    def get_users(self) -> Generator[dict, None, None]:
        """
        Retrieve all users from the Organization Users API with pagination.
        Yields each user as a dictionary.
        """
        url = furl(self.base_url).set(path=["v1", "organization", "users"]).url
        after = None
        total_users = 0

        self.logger.info(
            "Starting user retrieval from Organization Users API"
        )

        while True:
            params = {"limit": USERS_PER_PAGE}
            if after:
                params["after"] = after

            r = self.session.get(url, params=params)
            r.raise_for_status()

            response_data = r.json()
            users = response_data.get("data", [])

            if not users:
                break

            for user in users:
                # Convert top-level id field to string
                user["id"] = str(user["id"])
                total_users += 1
                yield user

            # Check for pagination
            has_more = response_data.get("has_more", False)
            if not has_more:
                break

            # Get the next cursor
            after = response_data.get("last_id")
            if not after:
                break

        self.logger.info(f"User retrieval complete. Total: {total_users}")

    def get_completions_usage(self) -> Generator[dict, None, None]:
        """
        Retrieve completions usage data grouped by user for the configured
        lookback period. Yields exactly ONE combined record per active user
        containing total tokens and a per-model breakdown dictionary.
        """
        url = furl(self.base_url).set(
            path=["v1", "organization", "usage", "completions"]
        ).url

        lookback_days = self.settings.get("lookback_days", 7)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=lookback_days)
        start_ts = int(start_time.timestamp())

        self.logger.info(
            f"Fetching completions usage for the last {lookback_days} days"
        )

        user_aggregation = {}
        page = None

        while True:
            params = {
                "start_time": start_ts,
                "bucket_width": "1d",
                "group_by": ["user_id", "model"],
                "limit": USAGE_DAILY_LIMIT,
            }
            if page:
                params["page"] = page

            r = self.session.get(url, params=params)
            r.raise_for_status()

            response_data = r.json()
            buckets = response_data.get("data", [])

            if not buckets:
                break

            for bucket in buckets:
                for result in bucket.get("results", []):
                    user_id = result.get("user_id")
                    model = result.get("model")

                    # Skip if there is no user tracking tag
                    if not user_id:
                        continue

                    input_tokens = result.get("input_tokens", 0)
                    output_tokens = result.get("output_tokens", 0)
                    input_cached_tokens = result.get("input_cached_tokens", 0)
                    num_model_requests = result.get("num_model_requests", 0)
                    input_text_tokens = result.get("input_text_tokens", 0)
                    input_image_tokens = result.get("input_image_tokens", 0)
                    input_cached_text_tokens = result.get("input_cached_text_tokens", 0)
                    input_cached_audio_tokens = result.get("input_cached_audio_tokens", 0)
                    input_cached_image_tokens = result.get("input_cached_image_tokens", 0)
                    input_uncached_tokens = result.get("input_uncached_tokens", 0)
                    input_cache_write_tokens = result.get("input_cache_write_tokens", 0)
                    output_text_tokens = result.get("output_text_tokens", 0)
                    output_image_tokens = result.get("output_image_tokens", 0)

                    if user_id not in user_aggregation:
                        user_aggregation[user_id] = {
                            "user_id": user_id,
                            "total_input_tokens": 0,
                            "total_output_tokens": 0,
                            "total_input_cached_tokens": 0,
                            "total_num_model_requests": 0,
                            "total_input_text_tokens": 0,
                            "total_input_image_tokens": 0,
                            "total_input_cached_text_tokens": 0,
                            "total_input_cached_audio_tokens": 0,
                            "total_input_cached_image_tokens": 0,
                            "total_input_uncached_tokens": 0,
                            "total_input_cache_write_tokens": 0,
                            "total_output_text_tokens": 0,
                            "total_output_image_tokens": 0,
                            "models": {},
                        }

                    user_aggregation[user_id]["total_input_tokens"] += input_tokens
                    user_aggregation[user_id]["total_output_tokens"] += output_tokens
                    user_aggregation[user_id]["total_input_cached_tokens"] += input_cached_tokens
                    user_aggregation[user_id]["total_num_model_requests"] += num_model_requests
                    user_aggregation[user_id]["total_input_text_tokens"] += input_text_tokens
                    user_aggregation[user_id]["total_input_image_tokens"] += input_image_tokens
                    user_aggregation[user_id]["total_input_cached_text_tokens"] += input_cached_text_tokens
                    user_aggregation[user_id]["total_input_cached_audio_tokens"] += input_cached_audio_tokens
                    user_aggregation[user_id]["total_input_cached_image_tokens"] += input_cached_image_tokens
                    user_aggregation[user_id]["total_input_uncached_tokens"] += input_uncached_tokens
                    user_aggregation[user_id]["total_input_cache_write_tokens"] += input_cache_write_tokens
                    user_aggregation[user_id]["total_output_text_tokens"] += output_text_tokens
                    user_aggregation[user_id]["total_output_image_tokens"] += output_image_tokens

                    if model:
                        if model not in user_aggregation[user_id]["models"]:
                            user_aggregation[user_id]["models"][model] = {
                                "input_tokens": 0,
                                "output_tokens": 0,
                                "input_cached_tokens": 0,
                                "num_model_requests": 0,
                                "input_text_tokens": 0,
                                "input_image_tokens": 0,
                                "input_cached_text_tokens": 0,
                                "input_cached_audio_tokens": 0,
                                "input_cached_image_tokens": 0,
                                "input_uncached_tokens": 0,
                                "input_cache_write_tokens": 0,
                                "output_text_tokens": 0,
                                "output_image_tokens": 0,
                            }
                        model_data = user_aggregation[user_id]["models"][model]
                        model_data["input_tokens"] += input_tokens
                        model_data["output_tokens"] += output_tokens
                        model_data["input_cached_tokens"] += input_cached_tokens
                        model_data["num_model_requests"] += num_model_requests
                        model_data["input_text_tokens"] += input_text_tokens
                        model_data["input_image_tokens"] += input_image_tokens
                        model_data["input_cached_text_tokens"] += input_cached_text_tokens
                        model_data["input_cached_audio_tokens"] += input_cached_audio_tokens
                        model_data["input_cached_image_tokens"] += input_cached_image_tokens
                        model_data["input_uncached_tokens"] += input_uncached_tokens
                        model_data["input_cache_write_tokens"] += input_cache_write_tokens
                        model_data["output_text_tokens"] += output_text_tokens
                        model_data["output_image_tokens"] += output_image_tokens

            if not response_data.get("has_more", False):
                break

            page = response_data.get("next_page")
            if not page:
                break

        total_records = 0
        for user_record in user_aggregation.values():
            total_records += 1
            yield user_record

        self.logger.info(
            f"Usage retrieval complete. Yielded {total_records} aggregated user records."
        )
