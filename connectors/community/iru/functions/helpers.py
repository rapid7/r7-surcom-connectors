from logging import Logger
from furl import furl

from r7_surcom_api import HttpSession

from .sc_settings import Settings

# Maximum number of devices per page supported by the Iru API
DEVICE_PER_PAGE = 300


class IruClient():

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        # Expose the logger to the client
        self.logger = user_log

        # Expose the Connector Settings to the client
        self.settings = settings

        # Set the base URL for the Iru API
        self.base_url = furl(settings.get("url"))

        # Setup a Session using the Surcom HttpSession class
        self.session = HttpSession()

        # Always verify TLS, since we're connecting to a SaaS platform
        self.session.verify = True

        self.session.headers.update({
            "Authorization": "Bearer " + settings.get("api_key")
        })

    def _offset_paginated_get(self, endpoint, offset, per_page):
        url = self.base_url.copy().add(
            path=endpoint
        ).set(
            query_params={
                "offset": offset,
                "limit": per_page
            }
        ).url

        r = self.session.get(url)
        r.raise_for_status()

        data = r.json()

        return data, per_page

    def _cursor_paginated_get(self, endpoint, cursor):
        url = self.base_url.copy().add(
            path=endpoint
        ).set(
            query_params={
                "cursor": cursor
            }
        ).url

        r = self.session.get(url)
        r.raise_for_status()

        data = r.json()

        results = data.get("results", [])

        next_url = data.get("next", None)

        if next_url:
            cursor = furl(next_url).args['cursor']
        else:
            cursor = None

        return results, cursor

    def get_devices(self, offset=0, per_page=DEVICE_PER_PAGE):
        return self._offset_paginated_get(
            ["api", "v1", "devices"], offset, per_page
        )

    def get_users(self, cursor=None):
        return self._cursor_paginated_get(
            ["api", "v1", "users"], cursor
        )

    def get_device_detail(self, device_id):
        url = self.base_url.copy().add(
            path=["api", "v1", "devices", device_id, "details"]
        ).url

        r = self.session.get(url)
        r.raise_for_status()

        return r.json()

    def test_connection(self):
        try:
            devices, _ = self.get_devices(per_page=1)
            if len(devices) == 1:
                # We can only test device details if we have
                # at least one device, otherwise we assume it
                # will work for a successful connection
                self.get_device_detail(
                    devices[0].get("device_id")
                )
            self.get_users()
            return (True, "Successfully connected")
        except Exception as e:
            return (False, f"Connection test failed: {e}")
