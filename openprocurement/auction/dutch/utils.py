# -*- coding: utf-8 -*-
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP

from openprocurement.auction.utils import generate_request_id as _request_id
from openprocurement.auction.worker.utils import prepare_service_stage
from openprocurement.auction.dutch.constants import DUTCH_TIMEDELTA,\
    DUTCH_ROUNDS, MULTILINGUAL_FIELDS, ADDITIONAL_LANGUAGES,\
    DUTCH_DOWN_STEP, FIRST_PAUSE, FIRST_PAUSE_SECONDS, LAST_PAUSE_SECONDS,\
    DUTCH, SEALEDBID, BESTBID


def prepare_sealedbid_stage(auction):
    """TODO: """
    return []


def prepare_bestbid_stage(auction):
    """TODO: """
    return []


def calculate_dutch_value(value):
    if not isinstance(value, Decimal):
        value = Decimal(value)
    return value * DUTCH_DOWN_STEP

# def prepare_stages(auction):
#     stages = {
#         DUTCH: [],
#         SEALEDBID: [],
#         BESTBID: []
#     }
#     next_stage_date = auction.startDate
#     stages[DUTCH].append({
#         'type': 'pause',
#         'start': next_stage_date.isoformat()
#     })
#     next_stage_date += FIRST_PAUSE_SECONDS
#     value = auction.initial_value
#     for _ in range(DUTCH_ROUNDS):
#         dutch_stage = {
#             'start': next_stage_date.isoformat(),
#             'amount': value,
#             'bidder_id': '',
#             'time': '',
#             'type': 'round'
#         }
#         value = calculate_dutch_value(value)
#         next_stage_date += DUTCH_TIMEDELTA
#     next_stage_date += LAST_PAUSE_SECONDS
#     stages[DUTCH].append({
#         'type': 'pause',
#         'start': next_stage_date.isoformat(),
#     })

#     stages[SEALEDBID].extend(
#         prepare_sealedbid_stage(auction)
#     )
#     stages[BESTBID].extend(
#         prepare_bestbid_stage(auction)
#     )
#     return stages


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
    return (value - (value * DUTCH_DOWN_STEP)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)



def prepare_dutch_stages(auction):
    dutch_step_duration = DUTCH_TIMEDELTA / DUTCH_ROUNDS
    next_stage_timedelta = auction.startDate
    amount = auction.auction_document['value']['amount']
    stages = [prepare_service_stage(
            start=auction.startDate.isoformat(),
            type="pause"
    )]
    next_stage_timedelta += FIRST_PAUSE
    for index in range(DUTCH_ROUNDS):
        stage = {
            'start': next_stage_timedelta.isoformat(),
            'amount': amount,
            'type': 'dutch_{}'.format(index),
            'time': ''
        }
        stages.append(stage)
        amount = calculate_next_amount(amount)
        next_stage_timedelta += dutch_step_duration
    stages.append({
        'start': next_stage_timedelta.isoformat(),
        'type': 'pre-sealed',
    })
    return stages


def prepare_best_bid_stage(auction):
    """TODO:"""


def preapre_sealed_bid_stage(auction):
    """TODO: """


def prepare_audit(auction):
    auction_data = auction._auction_data
    audit = {
        "id": auction.auction_doc_id,
        "auctionId": auction_data["data"].get("auctionID", ""),
        "auction_id": auction.tender_id,
        "items": auction_data["data"].get("items", []),
        "results": {
            DUTCH: {},
            SEALEDBID: {},
            BESTBID: {},
        },
        "timeline": {
            "auction_start": {},
            'stages': {
                DUTCH: {
                    'timeline': {
                        'start': '',
                        'end': ''
                    }
                },
                SEALEDBID: {},
                BESTBID: {},
            }
        }
    }

    return audit


@contextmanager
def update_auction_document(auction):
    yield auction.get_auction_document()
    auction.save_auction_document()


@contextmanager
def lock_bids(auction):
    auction.bids_actions.acquire()
    yield
    auction.bids_actions.release()

    
def prepare_auction_document(auction):
    auction.auction_document.update({
        "_id": auction.auction_doc_id,
        "stages": [],
        "tenderID": auction._auction_data["data"].get("tenderID", ""),
        "procurementMethodType": auction._auction_data["data"].get(
            "procurementMethodType", "default"),
        "TENDERS_API_VERSION": auction.worker_defaults["TENDERS_API_VERSION"],
        "current_stage": -1,
        "current_phase": 'pre-staring',
        "results": {
            DUTCH: {},
            SEALEDBID: {},
            BESTBID: {}
        },
        "procuringEntity": auction._auction_data["data"].get("procuringEntity", {}),
        "items": auction._auction_data["data"].get("items", []),
        "value": auction._auction_data["data"].get("value", {}),
        "initial_value": auction._auction_data["data"].get("value", {}).get('amount'),
        "auction_type": "dutch",
    })
    for key in MULTILINGUAL_FIELDS:
        for lang in ADDITIONAL_LANGUAGES:
            lang_key = "{}_{}".format(key, lang)
            if lang_key in auction._auction_data["data"]:
                auction.auction_document[lang_key] = auction._auction_data["data"][lang_key]
        auction.auction_document[key] = auction._auction_data["data"].get(key, "")

    auction.auction_document['stages'].extend(
        prepare_dutch_stages(auction)
    )
    return auction.auction_document
