import logging
import sys

from copy import deepcopy
from datetime import datetime
from dateutil.tz import tzlocal
from gevent import spawn, sleep
from gevent.event import Event
from gevent.queue import Queue

from openprocurement.auction.utils import get_tender_data
from openprocurement.auction.worker.mixins import DBServiceMixin,\
    PostAuctionServiceMixin
from openprocurement.auction.worker.journal import (
    AUCTION_WORKER_API_AUCTION_CANCEL,
    AUCTION_WORKER_API_AUCTION_NOT_EXIST,
    AUCTION_WORKER_API_AUCTION_RESULT_NOT_APPROVED,
    AUCTION_WORKER_SERVICE_END_FIRST_PAUSE
)
from openprocurement.auction.dutch import utils as simple
from openprocurement.auction.dutch.constants import DUTCH,\
    SEALEDBID, PREBESTBID, PRESEALEDBID, END, BESTBID


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


class DutchAuctionPhase(object):
    
    def next_stage(self, stage):

        with simple.lock_bids(self), simple.update_auction_document(self):
            current_stage = self.auction_document['current_stage'] + 1
            self.auction_document['current_stage'] = current_stage
            if stage['type'].startswith(DUTCH):
                LOGGER.info(
                    '---------------- SWITCH DUTCH VALUE ----------------'
                )
                run_time = datetime.now(tzlocal()).isoformat()
                self.auction_document['stages'][current_stage]['time']\
                    = run_time
                if self.auction_document['current_stage'] == 1:
                    self.auction_document['current_phase'] = DUTCH
                    self.audit['timeline']['stages'][DUTCH]['timeline']['start']\
                        = run_time
                else:
                    self.auction_document['stages'][current_stage - 1].update({
                        'passed': True
                    })

                old = getattr(self, 'current_value')
                self.current_value = stage['amount']
                LOGGER.info('Switched dutch phase value from {} to {}'.format(old, self.current_value))


                self.audit['timeline']['stages'][DUTCH]['turn_{}'.format(self.auction_document['current_stage'])] = {
                    'amount': self.current_value,
                    'time': run_time,
                }

            else:
                self.end_dutch()

    def approve_dutch_winner(self, bid):
        stage = self.auction_document['current_stage']
        self.auction_document['stages'][stage].update({
            "changed": True,
            "bid": bid['bidder_id'],
        })
        self.auction_document['results'][DUTCH] = bid
        return True

    def approve_audit_info_on_dutch_winner(self):
        dutch_winner = self.auction_document['results'][DUTCH]
        self.audit['results'][DUTCH] = dutch_winner

    def add_dutch_winner(self, bid):
        with simple.update_auction_document(self):
            LOGGER.info(
                '---------------- Adding dutch winner  ----------------',
                extra={"JOURNAL_REQUEST_ID": self.request_id,
                       "MESSAGE_ID": AUCTION_WORKER_SERVICE_END_FIRST_PAUSE}
            )

            try:
                if self.approve_dutch_winner(bid):
                    LOGGER.info('Approved dutch winner')
                    self.approve_audit_info_on_dutch_winner()
                    self.end_dutch()
                    if not self.debug:
                        simple.post_dutch_results(self)
                    return True

            except Exception as e:
                LOGGER.fatal("Exception during initialization dutch winner. Error: {}".format(e))
                return e

    def end_dutch(self):
        LOGGER.info(
            '---------------- End dutch phase ----------------',
        )
        self.audit['timeline']['stages'][DUTCH]['timeline']['end']\
            = datetime.now(tzlocal()).isoformat()
        spawn(self.clean_up_preplanned_jobs)

        if not self.auction_document['results'].get(DUTCH, None):
            LOGGER.info("No bids on dutch phase. End auction now.")
            self.end_auction()
            return
        self.auction_document['current_phase'] = PRESEALEDBID


class SealedBidAuctionPhase(object):

    def add_bid(self):
        LOGGER.info("Started bids worker")
        while True:
            if self.bids_queue.empty() and self._end_sealedbid.is_set():
                break
            bid = self.bids_queue.get()
            if bid:
                LOGGER.info("Adding bid {bidder_id} with value {amount} on {time}".format(
                    **bid
                ))
                self._bids_data[bid['bidder_id']] = bid
            sleep(0.1)
        
    def switch_to_sealedbid(self, stage):
        with simple.lock_bids(self), simple.update_auction_document(self):
            self._end_sealedbid = Event()
            run_time = simple.update_stage(self)
            self.auction_document['current_phase'] = SEALEDBID
            self.audit['timeline']['stages'][SEALEDBID]['timeline'] = {
                'start': run_time
            }
            spawn(self.add_bid)
            LOGGER.info("Swithed auction to {} phase".format(SEALEDBID))

    def end_sealedbid(self, stage):
        with simple.update_auction_document(self):
            run_time = simple.update_stage(self)
            self.audit['timeline']['stages'][SEALEDBID]['timeline']['end']\
                = run_time
            self.auction_document['current_phase'] = PREBESTBID

            for k, v in self._bids_data.items():
                # TODO: prepare bidders data
                pass
                

class BestBidAuctionPhase(object):

    def switch_to_bestbid(self, stage):
        with simple.lock_bids(self), simple.update_auction_document(self):
            run_time = simple.update_stage(self)
            self.auction_document['current_phase'] = BESTBID
            self.audit['timeline']['stages'][BESTBID]['timeline'] = {
                'start': run_time
            }

    def end_bestbid(self, stage):
        with simple.update_auction_document(self):
            run_time = simple.update_stage(self)
            self.auction_document['current_phase'] = END
            self.audit['timeline']['stages'][BESTBID]['timeline']['end'] = run_time
        self.end_auction()
