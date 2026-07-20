from logging import Logger

from .helpers import ExabeamNewScaleClient
from .sc_settings import Settings
from .sc_types import ExabeamNewScaleCollectorAgent


def import_all(
    user_log: Logger,
    settings: Settings
):
    """
    Import all Site Collector agents from Exabeam New-Scale.
    """
    user_log.info("Getting '%s' from '%s'", ExabeamNewScaleCollectorAgent.__name__, settings.get("region"))

    client = ExabeamNewScaleClient(user_log=user_log, settings=settings)

    for collector in client.get_collectors():
        yield ExabeamNewScaleCollectorAgent(collector)
