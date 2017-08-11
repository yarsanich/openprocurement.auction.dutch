import logging
from requests import Session as RequestsSession
from urlparse import urljoin
from gevent import spawn
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
from openprocurement.auction.dutch.server import run_server
from openprocurement.auction.worker.mixins import (
    RequestIDServiceMixin, AuditServiceMixin,
    DateTimeServiceMixin, TIMEZONE
)
from openprocurement.auction.dutch.server import send_event
from openprocurement.auction.dutch.mixins import DutchDBServiceMixin,\
    DutchPostAuctionMixin, DutchAuctionPhase, SealedBidAuctionPhase,\
    BestBidAuctionPhase
from openprocurement.auction.dutch.constants import (
    REQUEST_QUEUE_SIZE,
    REQUEST_QUEUE_TIMEOUT,
    DUTCH_ROUNDS,
    PRESTARTED,
    DUTCH,
    PRESEALEDBID,
    SEALEDBID,
    PREBESTBID,
    BESTBID,
    END
)
from openprocurement.auction.dutch.journal import (
    AUCTION_WORKER_SERVICE_END_AUCTION,
    AUCTION_WORKER_SERVICE_STOP_AUCTION_WORKER,
    AUCTION_WORKER_SERVICE_PREPARE_SERVER,
    AUCTION_WORKER_SERVICE_END_FIRST_PAUSE
)
from openprocurement.auction.dutch.utils import prepare_audit,\
    update_auction_document, lock_bids
from openprocurement.auction.utils import delete_mapping


LOGGER = logging.getLogger('Auction Worker')
SCHEDULER = GeventScheduler(job_defaults={"misfire_grace_time": 100},
                            executors={'default': AuctionsExecutor()},
                            logger=LOGGER)

SCHEDULER.timezone = TIMEZONE
END_DUTCH_PAUSE = 20


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
            worker_defaults["TENDERS_API_URL"],
            '/api/{0}/auctions/{1}'.format(
                worker_defaults["TENDERS_API_VERSION"], tender_id
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
        self.worker_defaults = worker_defaults
        if self.worker_defaults.get('with_document_service', False):
            self.session_ds = RequestsSession()
        self._bids_data = {}
        self.db = Database(str(self.worker_defaults["COUCH_DATABASE"]),
                           session=Session(retry_delays=range(10)))
        self.audit = {}
        self.retries = 10
        self.bidders_data = []
        self.mapping = {}
        self.ends = {
            DUTCH: Event()
        }
        self._bids_data = {}
        LOGGER.info(self.debug)
        # auction phases controllers

        # Configuration for SealedBids phase
        self.has_critical_error = False
        if REQUEST_QUEUE_SIZE == -1:
            self.bids_queue = Queue()
        else:
            self.bids_queue = Queue(REQUEST_QUEUE_SIZE)

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
            LOGGER.info("Switched current stage to {}".format(self.auction_document['current_stage']))
            self.current_value = self.auction_document['initial_value']
            LOGGER.info("Initial value {}".format(self.current_value))

    @property
    def bidders_count(self):
        return len(self.bidders_data)

    def schedule_auction(self):
        self.generate_request_id()
        with update_auction_document(self):

            if self.debug:
                LOGGER.info("Get _auction_data from auction_document")
                self._auction_data = self.auction_document.get('test_auction_data', {})
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
                name = 'End of dutch stage: [{} -> {}]'.format(index - 1, index)
                id = 'auction:{}-{}'.format(DUTCH, index)
                func = self.next_stage
            elif stage['type'] == PRESEALEDBID:
                name = 'End of dutch phase'
                id = 'auction:{}'.format(PRESEALEDBID)
                func = self.finish_dutch
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
        self.server = run_server(self, self.convert_datetime(self.auction_document['stages'][-2]['start']), LOGGER)

    def wait_to_end(self):
        self._end_auction_event.wait()
        LOGGER.info("Stop auction worker", extra={
            "JOURNAL_REQUEST_ID": self.request_id,
            "MESSAGE_ID": AUCTION_WORKER_SERVICE_STOP_AUCTION_WORKER
        })
                
    def clean_up_preplanned_jobs(self):
        jobs = SCHEDULER.get_jobs()

        _f = lambda j: (j.id.startswith('auction:{}'.format(DUTCH)) or j.id.startswith('auction:{}'.format(PRESEALEDBID)))
        for job in filter(_f, jobs):
            job.remove()

    def finish_dutch(self, stage):
        self.end_dutch()

    def end_auction(self):
        LOGGER.info(
            '---------------- End auction ----------------',
            extra={"JOURNAL_REQUEST_ID": self.request_id,
                   "MESSAGE_ID": AUCTION_WORKER_SERVICE_END_AUCTION}
        )
        LOGGER.debug("Stop server", extra={"JOURNAL_REQUEST_ID": self.request_id})
        if self.server:
            self.server.stop()
        LOGGER.debug(
            "Clear mapping", extra={"JOURNAL_REQUEST_ID": self.request_id}
        )
        delete_mapping(self.worker_defaults,
                       self.auction_doc_id)

        # start_stage, end_stage = self.get_round_stages(ROUNDS)
        # minimal_bids = deepcopy(
        #     self.auction_document["stages"][start_stage:end_stage]
        # )
        # minimal_bids = self.filter_bids_keys(sorting_by_amount(minimal_bids))
        # self.auction_document["results"] = []
        # for item in minimal_bids:
        #     self.auction_document["results"].append(prepare_results_stage(**item))
        self.auction_document["current_stage"] = (len(self.auction_document["stages"]) - 1)
        LOGGER.debug(' '.join((
            'Document in end_stage: \n', yaml_dump(dict(self.auction_document))
        )), extra={"JOURNAL_REQUEST_ID": self.request_id})
        # self.approve_audit_info_on_announcement()
        LOGGER.info('Audit data: \n {}'.format(yaml_dump(self.audit)), extra={"JOURNAL_REQUEST_ID": self.request_id})
        if self.debug:
            LOGGER.debug(
                'Debug: put_auction_data disabled !!!',
                extra={"JOURNAL_REQUEST_ID": self.request_id}
            )
            sleep(10)
            self.save_auction_document()
        else:
            if self.put_auction_data():
                self.save_auction_document()
        LOGGER.debug(
            "Fire 'stop auction worker' event",
            extra={"JOURNAL_REQUEST_ID": self.request_id}
        )
        self._end_auction_event.set()

    # def cancel_auction(self):
    #     self.generate_request_id()
    #     if self.get_auction_document():
    #         LOGGER.info("Auction {} canceled".format(self.auction_doc_id),
    #                     extra={'MESSAGE_ID': AUCTION_WORKER_SERVICE_AUCTION_CANCELED})
    #         self.auction_document["current_stage"] = -100
    #         self.auction_document["endDate"] = datetime.now(tzlocal()).isoformat()
    #         LOGGER.info("Change auction {} status to 'canceled'".format(self.auction_doc_id),
    #                     extra={'MESSAGE_ID': AUCTION_WORKER_SERVICE_AUCTION_STATUS_CANCELED})
    #         self.save_auction_document()
    #     else:
    #         LOGGER.info("Auction {} not found".format(self.auction_doc_id),
    #                     extra={'MESSAGE_ID': AUCTION_WORKER_SERVICE_AUCTION_NOT_FOUND})

    # def reschedule_auction(self):
    #     self.generate_request_id()
    #     if self.get_auction_document():
    #         LOGGER.info("Auction {} has not started and will be rescheduled".format(self.auction_doc_id),
    #                     extra={'MESSAGE_ID': AUCTION_WORKER_SERVICE_AUCTION_RESCHEDULE})
    #         self.auction_document["current_stage"] = -101
    #         self.save_auction_document()
    #     else:
    #         LOGGER.info("Auction {} not found".format(self.auction_doc_id),
    #                     extra={'MESSAGE_ID': AUCTION_WORKER_SERVICE_AUCTION_NOT_FOUND})
