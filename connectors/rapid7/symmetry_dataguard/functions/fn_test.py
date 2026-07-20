from logging import Logger

from .sc_settings import Settings
from .helpers import SymmetryDSPMClient
from .fn_import_all import ENDPOINT_TYPES


def test(
    user_log: Logger,
    **settings: Settings
):
    """
    Test the Connection for this Connector

    Args:
        user_log (Logger): The logger object.
        settings (Settings): The connector settings, including the API URL and credentials.
    """
    client = SymmetryDSPMClient(user_log=user_log,
                                settings=settings)
    params = {"limit": 1}
    import_classified_object = settings.get("import_classified_object", False)
    for endpoint_key in ENDPOINT_TYPES:
        if endpoint_key == "object" and not import_classified_object:
            continue
        client.make_request(params=params, path_key=endpoint_key)

    return {
        "status": "success",
        "message": f"Successfully Connected to {settings.get('url')}"
    }
