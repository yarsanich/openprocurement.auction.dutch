import logging
from copy import deepcopy
from decimal import Decimal
from requests import Session as RequestsSession
from urlparse import urljoin
from collections import defaultdict
from gevent.queue import Queue
from gevent.event import Event
from gevent.lock import BoundedSemaphore
from gevent import sleep
from apscheduler.schedulers.gevent import GeventScheduler
from couchdb import Database, Session
from yaml import safe_dump as yaml_dump
from datetime import datetime
from dateutil.tz import tzlocal
from openprocurement.auction.executor import AuctionsExecutor
from openprocurement.auction.insider.server import run_server
from openprocurement.auction.worker.mixins import RequestIDServiceMixin,\
    AuditServiceMixin, DateTimeServiceMixin, TIMEZONE
from openprocurement.auction.insider.mixins import DutchDBServiceMixin,\
    DutchPostAuctionMixin, DutchAuctionPhase, SealedBidAuctionPhase,\
    BestBidAuctionPhase
from openprocurement.auction.insider.constants import REQUEST_QUEUE_SIZE,\
    REQUEST_QUEUE_TIMEOUT, DUTCH, PRESEALEDBID, SEALEDBID, PREBESTBID,\
    BESTBID, END, PRESTARTED, BIDS_KEYS_FOR_COPY
from openprocurement.auction.insider.journal import\
    AUCTION_WORKER_SERVICE_END_AUCTION,\
    AUCTION_WORKER_SERVICE_STOP_AUCTION_WORKER,\
    AUCTION_WORKER_SERVICE_PREPARE_SERVER,\
    AUCTION_WORKER_SERVICE_END_FIRST_PAUSE
from openprocurement.auction.insider.utils import prepare_audit,\
    update_auction_document, lock_bids, prepare_results_stage
from openprocurement.auction.utils import delete_mapping, sorting_by_amount


LOGGER = logging.getLogger('Auction Worker Insider')
SCHEDULER = GeventScheduler(job_defaults={"misfire_grace_time": 100},
                            executors={'default': AuctionsExecutor()},
                            logger=LOGGER)

SCHEDULER.timezone = TIMEZONE



class Auction(DutchDBServiceMixin,
              AuditServiceMixin,
              DateTimeServiceMixin,
              RequestIDServiceMixin,
              DutchAuctionPhase,
              SealedBidAuctionPhase,
              BestBidAuctionPhase,
              DutchPostAuctionMixin):
    """ Dutch Auction Worker Class """

    def __init__(self, tender_id,
                 worker_defaults={},
                 auction_data={}):
        self.tender_id = tender_id
        self.auction_doc_id = tender_id
        self._end_auction_event = Event()
        self.tender_url = urljoin(
            worker_defaults["resource_api_server"],
            '/api/{0}/auctions/{1}'.format(
                worker_defaults["resource_api_version"], tender_id
            )
        )
        if auction_data:
            self.debug = True
            LOGGER.setLevel(logging.DEBUG)
            self._auction_data = auction_data
        else:
            self.debug = False
        self.bids_actions = BoundedSemaphore()
        self.session = RequestsSession()
        self.features = {}  # bw
        self.worker_defaults = worker_defaults
        if self.worker_defaults.get('with_document_service', False):
            self.session_ds = RequestsSession()
        self._bids_data = {}
        self.db = Database(str(self.worker_defaults["COUCH_DATABASE"]),
                           session=Session(retry_delays=range(10)))
        self.audit = {}
        self.retries = 10
        self.mapping = {}
        self._bids_data = defaultdict(list)
        self.has_critical_error = False
        if REQUEST_QUEUE_SIZE == -1:
            self.bids_queue = Queue()
        else:
            self.bids_queue = Queue(REQUEST_QUEUE_SIZE)

        self.bidders_data = []

    def start_auction(self):
        self.generate_request_id()
        self.audit['timeline']['auction_start']['time']\
            = datetime.now(tzlocal()).isoformat()
        LOGGER.info(
            '---------------- Start auction  ----------------',
            extra={"JOURNAL_REQUEST_ID": self.request_id,
                   "MESSAGE_ID": AUCTION_WORKER_SERVICE_END_FIRST_PAUSE}
        )
        self.get_auction_info()
        with lock_bids(self), update_auction_document(self):
            self.auction_document["current_stage"] = 0
            self.auction_document['current_phase'] = PRESTARTED
            LOGGER.info("Switched current stage to {}".format(
                self.auction_document['current_stage']
            ))

    @property
    def bidders_count(self):
        return len(self._bids_data.values())

    def schedule_auction(self):
        self.generate_request_id()
        with update_auction_document(self):

            if self.debug:
                LOGGER.info("Get _auction_data from auction_document")
                self._auction_data = self.auction_document.get(
                    'test_auction_data', {}
                )
            self.get_auction_info()
            self.audit = prepare_audit(self)

        round_number = 0
        SCHEDULER.add_job(
            self.start_auction,
            'date',
            run_date=self.convert_datetime(
                self.auction_document['stages'][0]['start']
            ),
            name="Start of Auction",
            id="auction:start"
        )
        round_number += 1

        for index, stage in enumerate(self.auction_document['stages'][1:], 1):
            if stage['type'].startswith(DUTCH):
                name = 'End of dutch stage: [{} -> {}]'.format(
                    index - 1, index
                )
                id = 'auction:{}-{}'.format(DUTCH, index)
                func = self.next_stage
            elif stage['type'] == PRESEALEDBID:
                name = 'End of dutch phase'
                id = 'auction:{}'.format(PRESEALEDBID)
                func = self.end_dutch
            elif stage['type'] == SEALEDBID:
                name = "Sealedbid phase"
                func = self.switch_to_sealedbid
                id = "auction:{}".format(SEALEDBID)
            elif stage['type'] == PREBESTBID:
                id = 'auction:{}'.format(PREBESTBID)
                name = "End of sealedbid phase"
                func = self.end_sealedbid
            elif stage['type'] == BESTBID:
                id = 'auction:{}'.format(BESTBID)
                name = 'BestBid phase'
                func = self.switch_to_bestbid
            elif stage['type'] == END:
                id = 'auction:{}'.format(END)
                name = 'End of bestbid phase'
                func = self.end_bestbid

            SCHEDULER.add_job(
                func,
                'date',
                args=(stage,),
                run_date=self.convert_datetime(
                    self.auction_document['stages'][index]['start']
                ),
                name=name,
                id=id
            )

            round_number += 1

        LOGGER.info(
            "Prepare server ...",
            extra={"JOURNAL_REQUEST_ID": self.request_id,
                   "MESSAGE_ID": AUCTION_WORKER_SERVICE_PREPARE_SERVER}
        )
        self.server = run_server(
            self,
            self.convert_datetime(
                self.auction_document['stages'][-2]['start']
            ),
            LOGGER
        )

    def wait_to_end(self):
        self._end_auction_event.wait()
        LOGGER.info("Stop auction worker", extra={
            "JOURNAL_REQUEST_ID": self.request_id,
            "MESSAGE_ID": AUCTION_WORKER_SERVICE_STOP_AUCTION_WORKER
        })

    def clean_up_preplanned_jobs(self):
        def filter_job(job):
            return (
                job.id.startswith('auction:{}'.format(DUTCH)) or
                job.id.startswith('auction:{}'.format(PRESEALEDBID))
            )
        jobs = SCHEDULER.get_jobs()
        for job in filter(filter_job, jobs):
            job.remove()

    def approve_audit_info_on_announcement(self, approved={}):
        self.audit['results'] = {
            "time": datetime.now(tzlocal()).isoformat(),
            "bids": []
        }
        for bid in self.auction_document['results']:
            bid_result_audit = {
                'bidder': bid['bidder_id'],
                'amount': bid['amount'],
                'time': bid['time']
            }
            if bid.get('dutch_winner', False):
                bid_result_audit['dutch_winner'] = True
            if bid.get('sealedbid_winner', False):
                bid_result_audit['sealedbid_winner'] = True
            if approved:
                bid_result_audit["identification"] = approved.get(
                    bid['bidder_id'],
                    [{
                        "name": self.mapping[bid['bidder_id']]
                    }]
                )[0]['name']
            self.audit['results']['bids'].append(bid_result_audit)

    def end_auction(self):
        LOGGER.info(
            '---------------- End auction ----------------',
            extra={"JOURNAL_REQUEST_ID": self.request_id,
                   "MESSAGE_ID": AUCTION_WORKER_SERVICE_END_AUCTION}
        )
        LOGGER.debug(
            "Stop server", extra={"JOURNAL_REQUEST_ID": self.request_id}
        )
        if self.server:
            self.server.stop()
        delete_mapping(self.worker_defaults,
                       self.auction_doc_id)

        LOGGER.debug(
            "Clear mapping", extra={"JOURNAL_REQUEST_ID": self.request_id}
        )

        self.auction_document["current_stage"] = (len(
            self.auction_document["stages"]) - 1)
        self.auction_document['current_phase'] = END
        normalized_document = deepcopy(self.auction_document)
        for s in normalized_document['stages']:
            if isinstance(s.get('amount'), Decimal):
                s['amount'] = str(s['amount'])
        LOGGER.debug(' '.join((
            'Document in end_stage: \n', yaml_dump(dict(normalized_document))
        )), extra={"JOURNAL_REQUEST_ID": self.request_id})
        self.approve_audit_info_on_announcement()
        LOGGER.info(
            'Audit data: \n {}'.format(yaml_dump(self.audit)),
            extra={"JOURNAL_REQUEST_ID": self.request_id}
        )
        if self.put_auction_data():
            self.save_auction_document()
        LOGGER.debug(
            "Fire 'stop auction worker' event",
            extra={"JOURNAL_REQUEST_ID": self.request_id}
        )

        self._end_auction_event.set()

    def cancel_auction(self):
        self.generate_request_id()
        if self.get_auction_document():
            LOGGER.info(
                "Auction {} canceled".format(self.auction_doc_id),
                extra={
                    'MESSAGE_ID': AUCTION_WORKER_SERVICE_AUCTION_CANCELED
                }
            )
            self.auction_document["current_stage"] = -100
            self.auction_document["endDate"] = datetime.now(tzlocal()).isoformat()
            LOGGER.info(
                "Change auction {} status to 'canceled'".format(self.auction_doc_id),
                extra={
                    'MESSAGE_ID': AUCTION_WORKER_SERVICE_AUCTION_STATUS_CANCELED
                }
            )
            self.save_auction_document()
        else:
            LOGGER.info(
                "Auction {} not found".format(self.auction_doc_id),
                extra={
                    'MESSAGE_ID': AUCTION_WORKER_SERVICE_AUCTION_NOT_FOUND
                }
            )

    def reschedule_auction(self):
        self.generate_request_id()
        if self.get_auction_document():
            LOGGER.info(
                "Auction {} has not started and will be rescheduled".format(self.auction_doc_id),
                extra={
                    'MESSAGE_ID': AUCTION_WORKER_SERVICE_AUCTION_RESCHEDULE
                }
            )
            self.auction_document["current_stage"] = -101
            self.save_auction_document()
        else:
            LOGGER.info(
                "Auction {} not found".format(self.auction_doc_id),
                extra={
                    'MESSAGE_ID': AUCTION_WORKER_SERVICE_AUCTION_NOT_FOUND
                }
            )
