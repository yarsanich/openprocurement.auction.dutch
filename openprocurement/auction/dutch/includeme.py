from openprocurement.auction.core import Planning, RunDispatcher
from openprocurement.auction.dutch.interfaces import IDutchAuction
from openprocurement.auction.dutch.constants import PROCUREMENT_METHOD_TYPE

from openprocurement.auction.interfaces import (IFeedItem,
                                                IAuctionDatabridge,
                                                IAuctionsChronograph)


def includeme(components):
    components.add_auction(IDutchAuction,
                           procurementMethodType=PROCUREMENT_METHOD_TYPE)
    components.registerAdapter(Planning, (IAuctionDatabridge, IFeedItem),
                               IDutchAuction)
    components.registerAdapter(RunDispatcher,
                               (IAuctionsChronograph, IFeedItem),
                               IDutchAuction)
