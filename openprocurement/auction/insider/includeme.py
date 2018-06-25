# -*- coding: utf-8 -*-
import logging

from openprocurement.auction.core import RunDispatcher
from openprocurement.auction.interfaces import (
    IFeedItem, IAuctionDatabridge, IAuctionsChronograph, IAuctionsServer
)

from openprocurement.auction.insider.constants import PROCUREMENT_METHOD_TYPE
from openprocurement.auction.insider.interfaces import IDutchAuction
from openprocurement.auction.insider.planning import InsiderPlanning
from openprocurement.auction.insider.views import includeme as _includeme


LOGGER = logging.getLogger(__name__)


def dgfInsider(components):
    includeme(components, PROCUREMENT_METHOD_TYPE)
    LOGGER.info("Included dgfInsider plugin",
                extra={'MESSAGE_ID': 'included_plugin'})


def sellout_insider(components):
    includeme(components, 'sellout.insider')
    LOGGER.info("Included sellout.insider plugin",
                extra={'MESSAGE_ID': 'included_plugin'})


def includeme(components, procurement_method_type):
    components.add_auction(IDutchAuction,
                           procurementMethodType=procurement_method_type)
    components.registerAdapter(InsiderPlanning, (IAuctionDatabridge, IFeedItem),
                               IDutchAuction)
    components.registerAdapter(RunDispatcher,
                               (IAuctionsChronograph, IFeedItem),
                               IDutchAuction)
    server = components.queryUtility(IAuctionsServer)
    _includeme(server)
