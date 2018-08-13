# -*- coding: utf-8 -*-
import logging

from openprocurement.auction.core import RunDispatcher
from openprocurement.auction.interfaces import (
    IFeedItem, IAuctionDatabridge, IAuctionsChronograph, IAuctionsServer
)

from openprocurement.auction.insider.interfaces import IDutchAuction
from openprocurement.auction.insider.planning import InsiderPlanning
from openprocurement.auction.insider.views import includeme as _includeme


LOGGER = logging.getLogger(__name__)


def dutch_components(components, procurement_method_types):
    for procurement_method_type in procurement_method_types:
        includeme(components, procurement_method_type)


def dutch_routes(components):
    server = components.queryUtility(IAuctionsServer)
    _includeme(server)


def includeme(components, procurement_method_type):
    components.add_auction(IDutchAuction,
                           procurementMethodType=procurement_method_type)
    components.registerAdapter(InsiderPlanning, (IAuctionDatabridge, IFeedItem),
                               IDutchAuction)
    components.registerAdapter(RunDispatcher,
                               (IAuctionsChronograph, IFeedItem),
                               IDutchAuction)
    LOGGER.info("Included %s plugin" % procurement_method_type,
                extra={'MESSAGE_ID': 'included_plugin'})
