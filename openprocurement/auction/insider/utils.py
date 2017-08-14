# -*- coding: utf-8 -*-
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from dateutil.tz import tzlocal

from openprocurement.auction.utils import generate_request_id as _request_id
from openprocurement.auction.worker.utils import prepare_service_stage

from openprocurement.auction.insider.constants import PRESTARTED, DUTCH,\
    PRESEALEDBID, SEALEDBID, PREBESTBID, BESTBID, END

from openprocurement.auction.insider.constants import DUTCH_TIMEDELTA,\
    DUTCH_ROUNDS, MULTILINGUAL_FIELDS, ADDITIONAL_LANGUAGES,\
    DUTCH_DOWN_STEP, FIRST_PAUSE, SEALEDBID_TIMEDELTA,\
    BESTBID_TIMEDELTA, END_PHASE_PAUSE


def calculate_dutch_value(value):
    if not isinstance(value, Decimal):
        value = Decimal(value)
    return value * DUTCH_DOWN_STEP


@contextmanager
def generate_request_id(auction):
    auction.request_id = _request_id()


def post_results_data(self, with_auctions_results=True):
    """TODO: make me work"""


def announce_results_data(self, results=None):
    """TODO: make me work"""


def calculate_next_amount(value):
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return (value - (value * DUTCH_DOWN_STEP)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )


def prepare_timeline_stage():
    return {
        'timeline': {
            'start': '',
            'end': ''
        },
        'bids': []
    }


def prepare_audit(auction):
    auction_data = auction._auction_data
    audit = {
        "id": auction.auction_doc_id,
        "auctionId": auction_data["data"].get("auctionID", ""),
        "auction_id": auction.tender_id,
        "items": auction_data["data"].get("items", []),
        "results": {
            DUTCH: [],
            SEALEDBID: [],
            BESTBID: [],
        },
        "timeline": {
            "auction_start": {},
        }
    }
    for phase in (DUTCH, SEALEDBID, BESTBID):
        audit['timeline'][phase] = prepare_timeline_stage()
    return audit


def get_dutch_winner(auction_document):
    try:
        return auction_document['results'][DUTCH][0]
    except Exception:
        return {}


@contextmanager
def update_auction_document(auction):
    yield auction.get_auction_document()
    auction.save_auction_document()


@contextmanager
def lock_bids(auction):
    auction.bids_actions.acquire()
    yield
    auction.bids_actions.release()


def update_stage(auction):
    auction.auction_document['current_stage'] += 1
    current_stage = auction.auction_document['current_stage']
    run_time = datetime.now(tzlocal()).isoformat()
    auction.auction_document['stages'][current_stage]['time'] = run_time
    return run_time


def prepare_auction_document(auction):
    auction.auction_document.update({
        "_id": auction.auction_doc_id,
        "stages": [],
        "tenderID": auction._auction_data["data"].get("tenderID", ""),
        "procurementMethodType": auction._auction_data["data"].get(
            "procurementMethodType", "default"),
        "TENDERS_API_VERSION": auction.worker_defaults["TENDERS_API_VERSION"],
        "current_stage": -1,
        "current_phase": PRESTARTED,
        "results": {
            DUTCH: [],
            SEALEDBID: [],
            BESTBID: []
        },
        "procuringEntity": auction._auction_data["data"].get(
            "procuringEntity", {}
        ),
        "items": auction._auction_data["data"].get("items", []),
        "value": auction._auction_data["data"].get("value", {}),
        "initial_value": auction._auction_data["data"].get(
            "value", {}
        ).get('amount'),
        "auction_type": "dutch",
    })
    for key in MULTILINGUAL_FIELDS:
        for lang in ADDITIONAL_LANGUAGES:
            lang_key = "{}_{}".format(key, lang)
            if lang_key in auction._auction_data["data"]:
                auction.auction_document[lang_key]\
                    = auction._auction_data["data"][lang_key]
        auction.auction_document[key] = auction._auction_data["data"].get(
            key, ""
        )
    dutch_step_duration = DUTCH_TIMEDELTA / DUTCH_ROUNDS
    next_stage_timedelta = auction.startDate
    amount = auction.auction_document['value']['amount']
    auction.auction_document['stages'] = [prepare_service_stage(
            start=auction.startDate.isoformat(),
            type="pause"
    )]
    next_stage_timedelta += FIRST_PAUSE
    for index in range(DUTCH_ROUNDS + 1):
        if index == DUTCH_ROUNDS:
            stage = {
                'start': next_stage_timedelta.isoformat(),
                'type': PRESEALEDBID,
                'time': ''
            }
        else:
            stage = {
                'start': next_stage_timedelta.isoformat(),
                'amount': amount,
                'type': 'dutch_{}'.format(index),
                'time': ''
            }
        auction.auction_document['stages'].append(stage)
        amount = calculate_next_amount(amount)
        if index != DUTCH_ROUNDS:
            next_stage_timedelta += dutch_step_duration

    for delta, name in zip(
            [
                END_PHASE_PAUSE,
                SEALEDBID_TIMEDELTA,
                END_PHASE_PAUSE,
                BESTBID_TIMEDELTA,

            ],
            [
                SEALEDBID,
                PREBESTBID,
                BESTBID,
                END,
            ]):
        next_stage_timedelta += delta
        auction.auction_document['stages'].append({
            'start': next_stage_timedelta.isoformat(),
            'type': name,
            'time': ''
        })
    return auction.auction_document
