from openprocurement.auction.core import RunDispatcher
from openprocurement.auction.insider.planning import InsiderPlanning
from openprocurement.auction.interfaces import IAuctionsServer
from openprocurement.auction.insider.interfaces import IDutchAuction
from openprocurement.auction.insider.views import includeme as _includeme
from openprocurement.auction.insider.constants import PROCUREMENT_METHOD_TYPE

from openprocurement.auction.interfaces import (
    IFeedItem, IAuctionDatabridge, IAuctionsChronograph)


def includeme(components):
    components.add_auction(IDutchAuction,
                           procurementMethodType=PROCUREMENT_METHOD_TYPE)
    components.registerAdapter(InsiderPlanning, (IAuctionDatabridge, IFeedItem),
                               IDutchAuction)
    components.registerAdapter(RunDispatcher,
                               (IAuctionsChronograph, IFeedItem),
                               IDutchAuction)
    server = components.queryUtility(IAuctionsServer)
    _includeme(server)
