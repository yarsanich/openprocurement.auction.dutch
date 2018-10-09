# -*- coding: utf-8 -*-
import logging

from openprocurement.auction.plannings import NonClassicAuctionPlanning


LOGGER = logging.getLogger('Openprocurement Auction')


class InsiderPlanning(NonClassicAuctionPlanning):
    ready_to_plan_statuses = ["active.tendering", "active.auction"]
