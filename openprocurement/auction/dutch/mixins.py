import logging
import sys

from copy import deepcopy

from openprocurement.auction.utils import get_tender_data
from openprocurement.auction.worker.mixins import DBServiceMixin, PostAuctionServiceMixin
from openprocurement.auction.worker.journal import (
    AUCTION_WORKER_API_AUCTION_CANCEL,
    AUCTION_WORKER_API_AUCTION_NOT_EXIST,
    AUCTION_WORKER_API_AUCTION_RESULT_NOT_APPROVED,
)
from openprocurement.auction.dutch import utils as simple


LOGGER = logging.getLogger("Auction Worker")


class DutchDBServiceMixin(DBServiceMixin):
    """ Mixin class to work with couchdb"""
    def get_auction_info(self, prepare=False):
        if not self.debug:
            if prepare:
                self._auction_data = get_tender_data(
                    self.tender_url,
                    request_id=self.request_id,
                    session=self.session
                )
            else:
                self._auction_data = {'data': {}}
            auction_data = get_tender_data(
                self.tender_url + '/auction',
                user=self.worker_defaults["TENDERS_API_TOKEN"],
                request_id=self.request_id,
                session=self.session
            )
            if auction_data:
                self._auction_data['data'].update(auction_data['data'])
                self.startDate = self.convert_datetime(self._auction_data['data']['auctionPeriod']['startDate'])
                del auction_data
            else:
                self.get_auction_document()
                if self.auction_document:
                    self.auction_document["current_stage"] = -100
                    self.save_auction_document()
                    LOGGER.warning("Cancel auction: {}".format(
                        self.auction_doc_id
                    ), extra={"JOURNAL_REQUEST_ID": self.request_id,
                              "MESSAGE_ID": AUCTION_WORKER_API_AUCTION_CANCEL})
                else:
                    LOGGER.error("Auction {} not exists".format(
                        self.auction_doc_id
                    ), extra={"JOURNAL_REQUEST_ID": self.request_id,
                              "MESSAGE_ID": AUCTION_WORKER_API_AUCTION_NOT_EXIST})
                    self._end_auction_event.set()
                    sys.exit(1)

        self.startDate = self.convert_datetime(
            self._auction_data['data']['auctionPeriod']['startDate']
        )

    def prepare_public_document(self):
        public_document = deepcopy(dict(self.auction_document))
        return public_document

    def prepare_auction_document(self):
        self.generate_request_id()
        public_document = self.get_auction_document()

        self.auction_document = {}
        if public_document:
            self.auction_document = {"_rev": public_document["_rev"]}
        if self.debug:
            self.auction_document['mode'] = 'test'
            self.auction_document['test_auction_data'] = deepcopy(self._auction_data)

        self.get_auction_info(prepare=True)
        if self.worker_defaults.get('sandbox_mode', False):
            submissionMethodDetails = self._auction_data['data'].get('submissionMethodDetails', '')
            if submissionMethodDetails == 'quick(mode:no-auction)':
                simple.post_results_data(self, with_auctions_results=False)
                return 0
            elif submissionMethodDetails == 'quick(mode:fast-forward)':
                self.auction_document = simple.prepare_auction_document(self)

                self.get_auction_info()
                self.prepare_auction_stages_fast_forward()
                self.save_auction_document()
                simple.post_results_data(self, with_auctions_results=False)
                simple.announce_results_data(self, None)
                self.save_auction_document()
                return

        self.auction_document = simple.prepare_auction_document(self)
        self.save_auction_document()


class DutchPostAuctionMixin(PostAuctionServiceMixin):

    def put_auction_data(self):
        if self.worker_defaults.get('with_document_service', False):
            doc_id = self.upload_audit_file_with_document_service()
        else:
            doc_id = self.upload_audit_file_without_document_service()

        results = simple.post_results_data(self)

        if results:
            bids_information = simple.announce_results_data(self, results)

            if doc_id and bids_information:
                # self.approve_audit_info_on_announcement(approved=bids_information)
                if self.worker_defaults.get('with_document_service', False):
                    doc_id = self.upload_audit_file_with_document_service(doc_id)
                else:
                    doc_id = self.upload_audit_file_without_document_service(doc_id)
                return True
        else:
            LOGGER.info(
                "Auctions results not approved",
                extra={"JOURNAL_REQUEST_ID": self.request_id,
                       "MESSAGE_ID": AUCTION_WORKER_API_AUCTION_RESULT_NOT_APPROVED}
            )

    def post_announce(self):
        self.generate_request_id()
        with simple.update_auction_document(self):
            simple.announce_results_data(self, None)
