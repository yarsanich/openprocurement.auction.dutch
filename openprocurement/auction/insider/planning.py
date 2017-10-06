import iso8601
import logging
from datetime import datetime
from time import mktime, time

from openprocurement.auction.core import Planning
from openprocurement.auction.design import startDate_view, endDate_view
from openprocurement.auction.systemd_msgs_ids import \
    DATA_BRIDGE_PLANNING_TENDER_ALREADY_PLANNED as ALREADY_PLANNED,\
    DATA_BRIDGE_PLANNING_TENDER_SKIP


LOGGER = logging.getLogger('Openprocurement Auction')


class InsiderPlanning(Planning):

    def __iter__(self):
        if self.item['status'] == 'active.tendering':
            LOGGER.info('Prepare insider auction id={}'.format(self.item['id']))
            yield ("prepare", str(self.item['id']), "")
        if self.item['status'] == "active.auction":
            if 'auctionPeriod' in self.item \
                    and 'startDate' in self.item['auctionPeriod'] \
                    and 'endDate' not in self.item['auctionPeriod']:

                start_date = iso8601.parse_date(
                    self.item['auctionPeriod']['startDate'])
                start_date = start_date.astimezone(self.bridge.tz)
                auctions_start_in_date = startDate_view(
                    self.bridge.db,
                    key=(mktime(start_date.timetuple()) +
                         start_date.microsecond / 1E6) * 1000
                )
                if datetime.now(self.bridge.tz) > start_date:
                    LOGGER.info(
                        "Auction {} start date in past. "
                        "Skip it for planning".format(self.item['id']),
                        extra={
                            'MESSAGE_ID': DATA_BRIDGE_PLANNING_TENDER_SKIP
                        }
                    )
                    raise StopIteration
                elif not self.bridge.re_planning and \
                        [row.id for row in auctions_start_in_date.rows
                         if row.id == self.item['id']]:
                    LOGGER.info(
                        "Auction {} already planned on same date".format(self.item['id']),
                        extra={
                            'MESSAGE_ID': ALREADY_PLANNED
                        }
                    )
                    raise StopIteration
                yield ("planning", str(self.item['id']), "")
        if self.item['status'] == "cancelled":
            future_auctions = endDate_view(
                self.bridge.db, startkey=time() * 1000
            )
            if self.item["id"] in [i.id for i in future_auctions]:
                LOGGER.info('Auction {0} selected for cancellation'.format(
                    self.item['id']))
                yield ('cancel', self.item['id'], "")
        raise StopIteration
