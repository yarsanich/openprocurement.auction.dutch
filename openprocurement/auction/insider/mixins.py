# -*- coding: utf-8 -*-
import logging
import sys
import simplejson

from copy import deepcopy
from couchdb.json import use
from couchdb.http import HTTPError, RETRYABLE_ERRORS
from datetime import datetime
from dateutil.tz import tzlocal
from gevent import spawn, sleep
from gevent.event import Event
from functools import partial
from dateutil import parser

from openprocurement.auction.utils import get_tender_data
from openprocurement.auction.worker.mixins import DBServiceMixin,\
    PostAuctionServiceMixin
from openprocurement.auction.worker.journal import\
    AUCTION_WORKER_API_AUCTION_CANCEL,\
    AUCTION_WORKER_API_AUCTION_NOT_EXIST,\
    AUCTION_WORKER_API_AUCTION_RESULT_NOT_APPROVED as API_NOT_APPROVED,\
    AUCTION_WORKER_SERVICE_END_FIRST_PAUSE
from openprocurement.auction.insider import utils
from openprocurement.auction.insider.constants import DUTCH,\
    SEALEDBID, PREBESTBID, PRESEALEDBID, BESTBID, AUCTION_PARAMETERS


LOGGER = logging.getLogger("Auction Worker Insider")

use(encode=partial(simplejson.dumps, use_decimal=True),
    decode=partial(simplejson.loads, use_decimal=True))


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
                user=self.worker_defaults["resource_api_token"],
                request_id=self.request_id,
                session=self.session
            )

            if auction_data:
                self._auction_data['data'].update(auction_data['data'])
                self.startDate = self.convert_datetime(
                    self._auction_data['data']['auctionPeriod']['startDate']
                )
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
                    ), extra={
                        "JOURNAL_REQUEST_ID": self.request_id,
                        "MESSAGE_ID": AUCTION_WORKER_API_AUCTION_NOT_EXIST
                    })
                    self._end_auction_event.set()
                    sys.exit(1)

        self.startDate = self.convert_datetime(
            self._auction_data['data'].get('auctionPeriod', {}).get('startDate', '')
        )
        self.bidders_data = [
            {
                'id': bid['id'],
                'date': bid['date'],
                'owner': bid.get('owner', '')
            }
            for bid in self._auction_data['data'].get('bids', [])
            if bid.get('status', 'active') == 'active'
        ]
        self.parameters = self._auction_data['data'].get('auctionParameters', AUCTION_PARAMETERS)
        for index, bid in enumerate(self.bidders_data):
            if bid['id'] not in self.mapping:
                self.mapping[self.bidders_data[index]['id']]\
                    = len(self.mapping.keys()) + 1
        return self._auction_data

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
            self.auction_document['test_auction_data'] = deepcopy(
                self._auction_data
            )

        self.get_auction_info(prepare=True)
        if self.worker_defaults.get('sandbox_mode', False):
            self.auction_document = utils.prepare_auction_document(
                self,
                fast_forward=True
            )
        else:
            self.auction_document = utils.prepare_auction_document(self)
        self.save_auction_document()

    def prepare_auction(self):
        self.generate_request_id()
        auction_data = get_tender_data(
            self.tender_url,
            request_id=self.request_id,
            session=self.session
        )
        public_document = self.get_auction_document()

        self.auction_document = {}
        if public_document:
            self.auction_document = {"_rev": public_document["_rev"]}

        if auction_data:
            LOGGER.info("Prepare insider auction id={}".format(self.auction_doc_id))
            self.auction_document = utils.prepare_auction_data(auction_data)
            self.save_auction_document()
        else:
            LOGGER.warn("Auction {} not exists".format(self.auction_doc_id))
 
    def get_auction_document(self, force=False):
        retries = self.retries
        while retries:
            try:
                public_document = self.db.get(self.auction_doc_id)
                if public_document:
                    LOGGER.info("Get auction document {0[_id]} with rev {0[_rev]}".format(public_document),
                                extra={"JOURNAL_REQUEST_ID": self.request_id})
                    if not hasattr(self, 'auction_document'):
                        self.auction_document = public_document
                    if force:
                        return public_document
                    elif public_document['_rev'] != self.auction_document['_rev']:
                        LOGGER.warning("Rev error")
                        self.auction_document["_rev"] = public_document["_rev"]
                    LOGGER.debug(simplejson.dumps(self.auction_document, indent=4))
                return public_document

            except HTTPError, e:
                LOGGER.error("Error while get document: {}".format(e))
            except Exception, e:
                ecode = e.args[0]
                if ecode in RETRYABLE_ERRORS:
                    LOGGER.error("Error while get document: {}".format(e))
                else:
                    LOGGER.critical("Unhandled error: {}".format(e))
            retries -= 1

    def save_auction_document(self):
        public_document = self.prepare_public_document()
        retries = 10
        while retries:
            try:
                response = self.db.save(public_document)
                if len(response) == 2:
                    LOGGER.info("Saved auction document {0} with rev {1}".format(*response))
                    self.auction_document['_rev'] = response[1]
                    return response
            except HTTPError, e:
                LOGGER.error("Error while save document: {}".format(e))
            except Exception, e:
                ecode = e.args[0]
                if ecode in RETRYABLE_ERRORS:
                    LOGGER.error("Error while save document: {}".format(e))
                else:
                    LOGGER.critical("Unhandled error: {}".format(e))
            if "_rev" in public_document:
                LOGGER.debug("Retry save document changes")
            saved_auction_document = self.get_auction_document(force=True)
            public_document["_rev"] = saved_auction_document["_rev"]
            retries -= 1


class DutchPostAuctionMixin(PostAuctionServiceMixin):

    def put_auction_data(self):
        if not self.debug:
            if self.worker_defaults.get('with_document_service', False):
                doc_id = self.upload_audit_file_with_document_service()
            else:
                doc_id = self.upload_audit_file_without_document_service()
        else:
            LOGGER.debug("Put auction data disabled")
        results = utils.post_results_data(self)

        if results:
            bids_information = utils.announce_results_data(self, results)
            if not self.debug:
                if doc_id and bids_information:
                    self.approve_audit_info_on_announcement(approved=bids_information)
                    if self.worker_defaults.get('with_document_service', False):
                        doc_id = self.upload_audit_file_with_document_service(
                            doc_id
                        )
                    else:
                        doc_id = self.upload_audit_file_without_document_service(
                            doc_id
                        )
            else:
                LOGGER.debug("Put auction data disabled")
            return True
        else:
            LOGGER.info(
                "Auctions results not approved",
                extra={
                    "JOURNAL_REQUEST_ID": self.request_id,
                    "MESSAGE_ID": API_NOT_APPROVED
                }
            )

    def post_announce(self):
        self.generate_request_id()
        with utils.update_auction_document(self):
            utils.announce_results_data(self, None)


class DutchAuctionPhase(object):

    def next_stage(self, stage):

        with utils.lock_bids(self), utils.update_auction_document(self):
            run_time = utils.update_stage(self)
            stage_index = self.auction_document['current_stage']
            self.auction_document['stages'][stage_index - 1].update({
                'passed': True
            })

            if stage['type'].startswith(DUTCH):
                LOGGER.info(
                    '---------------- SWITCH DUTCH VALUE ----------------'
                )
                self.auction_document['stages'][stage_index]['time']\
                    = run_time
                if stage_index == 1:
                    self.auction_document['current_phase'] = DUTCH
                    self.audit['timeline'][DUTCH]['timeline']['start']\
                        = run_time

                old = self.auction_document['stages'][stage_index - 1].get(
                    'amount', ''
                ) or self.auction_document['initial_value']

                LOGGER.info('Switched dutch phase value from {} to {}'.format(
                    old, stage['amount'])
                )
                turn = 'turn_{}'.format(stage_index)
                self.audit['timeline'][DUTCH][turn] = {
                    'amount': stage['amount'],
                    'time': run_time,
                }

            else:
                self.end_dutch()

    def approve_dutch_winner(self, bid):
        try:
            bid['dutch_winner'] = True
            for lst in [
                    self.audit['timeline'][DUTCH]['bids'],
                    self._bids_data[bid['bidder_id']]
                    ]:
                lst.append(bid)
            return deepcopy(bid)
        except Exception as e:
            LOGGER.warn("Unable to post dutch winner. Error: {}".format(
                e
            ))
            return False

    def add_dutch_winner(self, bid):
        with utils.update_auction_document(self):
            LOGGER.info(
                '---------------- Adding dutch winner  ----------------',
                extra={
                    "JOURNAL_REQUEST_ID": self.request_id,
                    "MESSAGE_ID": AUCTION_WORKER_SERVICE_END_FIRST_PAUSE
                }
            )
            try:
                bid['bidder_name'] = self.mapping.get(bid['bidder_id'], False)
                current_stage = bid['current_stage']
                del bid['current_stage']
                if current_stage != self.auction_document['current_stage']:
                    raise Exception(
                        u"Your bid is not submitted since the previous "
                        "step has already ended.")
                bid = self.approve_dutch_winner(bid)
                if bid:
                    result = utils.prepare_results_stage(**bid)
                    self.auction_document['stages'][current_stage].update(
                        result
                    )
                    self.auction_document['results'].append(
                        result
                    )
                    LOGGER.info('Approved dutch winner')
                    self.end_dutch()
                    return True
            except Exception as e:
                LOGGER.fatal(
                    "Exception during initialization dutch winner. "
                    "Error: {}".format(e)
                )
                return e

    def end_dutch(self, stage=""):
        LOGGER.info(
            '---------------- End dutch phase ----------------',
        )
        self.audit['timeline'][DUTCH]['timeline']['end']\
            = datetime.now(tzlocal()).isoformat()
        stage_index = self.auction_document['current_stage']

        if self.auction_document['stages'][stage_index]['type'].startswith('dutch'):
            self.auction_document['stages'][stage_index].update({
                'passed': True
            })

        spawn(self.clean_up_preplanned_jobs)
        if not self.auction_document['results']:
            LOGGER.info("No bids on dutch phase. End auction now.")
            self.end_auction()
            return
        self.auction_document['current_phase'] = PRESEALEDBID
        for index, stage in enumerate(self.auction_document['stages']):
            if stage['type'] == 'pre-sealedbid':
                self.auction_document['current_stage'] = index
                break


class SealedBidAuctionPhase(object):

    def add_bid(self):
        LOGGER.info("Started bids worker")
        while True:
            if self.bids_queue.empty() and self._end_sealedbid.is_set():
                break
            bid = self.bids_queue.get()
            if bid:
                LOGGER.info(
                    "Adding bid {bidder_id} with value {amount}"
                    " on {time}".format(**bid)
                )
                if bid['amount'] == -1:
                    LOGGER.info(
                        "Bid {bidder_id} marked for cancellation"
                        " on {time}".format(**bid)
                    )
                    if self._bids_data.get(bid['bidder_id'], False):
                        del self._bids_data[bid['bidder_id']]
                    self.audit['timeline'][SEALEDBID]['bids'] = \
                        [Bid for Bid in self.audit['timeline'][SEALEDBID]['bids'] if bid['bidder_id'] != Bid['bidder_id']]
                else:
                    for lst in [self._bids_data[bid['bidder_id']], self.audit['timeline'][SEALEDBID]['bids']]:
                        lst.append(bid)
            sleep(0.1)
        LOGGER.info("Bids queue done. Breaking worker")

    def switch_to_sealedbid(self, stage):
        with utils.lock_bids(self), utils.update_auction_document(self):
            self._end_sealedbid = Event()
            run_time = utils.update_stage(self)
            if not self.debug:
                utils.update_auction_status(self, 'active.auction.{}'.format(SEALEDBID))
            self.auction_document['current_phase'] = SEALEDBID
            self.get_auction_info()
            self.audit['timeline'][SEALEDBID]['timeline']['start'] =\
                run_time
            spawn(self.add_bid)
            LOGGER.info("Swithed auction to {} phase".format(SEALEDBID))

    def approve_audit_info_on_sealedbid(self, run_time):
        self.audit['timeline'][SEALEDBID]['timeline']['end']\
            = run_time

    def end_sealedbid(self, stage):
        with utils.update_auction_document(self):
            self._end_sealedbid.set()
            while not self.bids_queue.empty():
                LOGGER.info(
                    "Waiting for bids to process"
                )
                sleep(0.1)
            LOGGER.info("Done processing bids queue")
            self.auction_document['results'] = utils.prepare_auction_results(self, self._bids_data)
            if len([bid for bid in self.auction_document['results'] if str(bid['amount']) != '-1']) < 2:
                LOGGER.info("No bids on sealedbid phase. End auction now!")
                self.end_auction()
                return
            # find sealedbid winner in auction_document
            max_bid = self.auction_document['results'][0]
            for bid in self.auction_document['results']:
                if bid['amount'] > max_bid['amount'] or \
                  (bid['amount'] == max_bid['amount'] and
                   parser.parse(bid['time']) < parser.parse(max_bid['time'])) or \
                  max_bid.get('dutch_winner', False):
                    max_bid = bid
            LOGGER.info("Approved sealedbid winner {bidder_id} with amount {amount}".format(
                **max_bid
                ))
            if not max_bid.get('dutch_winner', False):
                max_bid['sealedbid_winner'] = True
            self.auction_document['stages'][self.auction_document['current_stage']].update(
                max_bid
            )
            self.approve_audit_info_on_sealedbid(utils.update_stage(self))
            self.auction_document['current_phase'] = PREBESTBID
            if not self.debug:
                utils.update_auction_status(self, 'active.auction.{}'.format(BESTBID))


class BestBidAuctionPhase(object):

    def approve_bid_on_bestbid(self, bid):
        if bid:
            LOGGER.info(
                "Updating dutch winner {bidder_id} with value {amount}"
                " on {time}".format(**bid)
            )
            bid['dutch_winner'] = True
            # Handle cancel of bid set previous bid from dutch phase
            if bid['amount'] == -1:
                # Get bid from dutch phase
                bid['amount'] = self._bids_data[bid['bidder_id']][0]['amount']  # First dutch winner bid
                LOGGER.info(
                    "Dutch winner id={bidder_id} cancel bid on {time} back to amount from dutch phase {amount}".format(**bid)
                )
            for lst in [
                self._bids_data[bid['bidder_id']],
                self.audit['timeline'][BESTBID]['bids']
            ]:
                lst.append(bid)
            return True
        return False

    def approve_audit_info_on_bestbid(self, run_time):
        self.audit['timeline'][BESTBID]['timeline']['end'] = run_time

    def add_bestbid(self, bid):
        try:
            if self.approve_bid_on_bestbid(bid):
                LOGGER.info(
                    "Dutch winner id={bidder_id} placed bid {amount}"
                    " on {time}".format(**bid)
                )
                return True
        except Exception as e:
            LOGGER.fatal(
                "Falied to update dutch winner. Error: {}".format(
                    e
                )
            )
            return e
        return False

    def switch_to_bestbid(self, stage):
        with utils.lock_bids(self), utils.update_auction_document(self):
            self.auction_document['current_phase'] = BESTBID
            self.audit['timeline'][BESTBID]['timeline']['start'] = utils.update_stage(self)

    def end_bestbid(self, stage):
        with utils.update_auction_document(self):
            self.auction_document['results'] = utils.prepare_auction_results(self, self._bids_data)
            self.approve_audit_info_on_bestbid(utils.update_stage(self))
        self.end_auction()
