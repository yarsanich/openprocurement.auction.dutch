# -*- coding: utf-8 -*-
import logging
from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta

from dateutil.tz import tzlocal
from openprocurement.auction.utils import (
    get_latest_bid_for_bidder,
    make_request, get_tender_data,
    sorting_by_amount
)
from openprocurement.auction.worker.journal import AUCTION_WORKER_API_APPROVED_DATA
from openprocurement.auction.worker.utils import prepare_service_stage
from openprocurement.auction.insider.constants import (
    DUTCH, PERCENT_FROM_INITIAL_VALUE,
    PRESEALEDBID, SEALEDBID, PREBESTBID, BESTBID,
    END
)
from openprocurement.auction.insider.constants import (
    MULTILINGUAL_FIELDS,
    ADDITIONAL_LANGUAGES, SEALEDBID_TIMEDELTA,
    BESTBID_TIMEDELTA, END_PHASE_PAUSE
)


LOGGER = logging.getLogger("Auction Worker Insider")


def prepare_results_stage(
        bidder_id="",
        bidder_name="",
        amount="",
        time="",
        dutch_winner="",
        sealedbid_winner=""):
    stage = dict(
        bidder_id=bidder_id,
        time=str(time),
        amount=amount or 0,
        label=dict(
            en="Bidder #{}".format(bidder_name),
            uk="Учасник №{}".format(bidder_name),
            ru="Участник №{}".format(bidder_name)
        )
    )
    if dutch_winner:
        stage['dutch_winner'] = True
    elif sealedbid_winner:
        stage['sealedbid_winner'] = True
    return stage


prepare_bids_stage = prepare_results_stage


def post_results_data(auction, with_auctions_results=True):
    def generate_value(bid_info):
        auction_bid = bid_info['amount'] if str(bid_info['amount']) != '-1'\
                else None
        value = auction.auction_document['value']
        return {
            "amount": str(auction_bid) if auction_bid else None,
            "currency": value.get('currency'),
            "valueAddedTaxIncluded": value.get('valueAddedTaxIncluded')
        }

    info = auction.get_auction_info()
    bids = info['data'].get("bids", [])
    if with_auctions_results:
        for bid_info in bids:
            if bid_info.get('status', 'active') == 'active':
                bidder_id = bid_info.get('bidder_id', bid_info.get('id', ''))
                if bidder_id:
                    try:
                        bid = get_latest_bid_for_bidder(
                            auction.auction_document['results'],
                            bidder_id
                        )
                    except IndexError:
                        bid = ''
                    if bid:
                        new_value = generate_value(bid)
                        if new_value.get('amount', None) is not None:
                            bid_info['value'] = new_value
                        bid_info['date'] = bid['time']
    data = {'data': {'bids': bids}}
    LOGGER.info(
        "Approved data: {}".format(data),
        extra={"JOURNAL_REQUEST_ID": auction.request_id,
               "MESSAGE_ID": AUCTION_WORKER_API_APPROVED_DATA}
    )
    if not auction.debug:
        return make_request(
            auction.tender_url + '/auction', data=data,
            user=auction.worker_defaults["resource_api_token"],
            method='post',
            request_id=auction.request_id,
            session=auction.session
        )
    LOGGER.info(
        "Making request to api with params {}".format(
        dict(method="post",
             url=auction.tender_url + '/auction',
             data=data)))
    return data


def announce_results_data(auction, results=None):
    if not results:
        results = get_tender_data(
            auction.tender_url,
            user=auction.worker_defaults["resource_api_token"],
            request_id=auction.request_id,
            session=auction.session
        )
    bids_information = dict([
        (bid["id"], bid.get("tenderers"))
        for bid in results["data"].get("bids", [])
        if bid.get("status", "active") == "active"
    ])
    for field in ['results', 'stages']:
        for index, stage in enumerate(auction.auction_document[field]):
            if 'bidder_id' in stage and stage['bidder_id'] in bids_information:
                auction.auction_document[field][index].update({
                    "label": {
                        'uk': bids_information[stage['bidder_id']][0]["name"],
                        'en': bids_information[stage['bidder_id']][0]["name"],
                        'ru': bids_information[stage['bidder_id']][0]["name"],
                    }
                })
    return bids_information


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
        "auctionParameters": auction.parameters,
        "items": auction_data["data"].get("items", []),
        "results": prepare_timeline_stage(),
        "timeline": {
            "auction_start": {},
        }
    }
    for phase in (DUTCH, SEALEDBID, BESTBID):
        audit['timeline'][phase] = prepare_timeline_stage()
    return audit


def get_dutch_winner(auction_document):
    try:
        return [bid for bid in auction_document['results']
                if bid.get('dutch_winner', False)][0]
    except IndexError:
        return {}


def get_sealed_bid_winner(auction_document):
    """
    :param auction_document:
    :return: sealedbid_winner bid info if it exists else empty dict
    """
    try:
        return [bid for bid in auction_document['results']
                if bid.get('sealedbid_winner', False)][0]
    except IndexError:
        return {}

@contextmanager
def update_auction_document(auction):
    yield auction.get_auction_document()
    if auction.auction_document:
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


def prepare_auction_data(data):
    return {
        "_id":  data['data'].get('id'),
        "auctionID": data["data"].get("auctionID", ""),
        "procurementMethodType": data["data"].get(
            "procurementMethodType", "default"),
        "current_stage": -1,
        "current_phase": "",
        "procuringEntity": data["data"].get(
            "procuringEntity", {}
        ),
        "items": data["data"].get("items", []),
        "value": data["data"].get("value", {}),
        "auction_type": "dutch",
    }


def calculate_next_stage_amount(auction, index):
    return (Decimal(str(auction.auction_document['initial_value'])) *
            Decimal(str((PERCENT_FROM_INITIAL_VALUE - (index + 1)) * 0.01))).quantize(Decimal('0.01'),
                                                                                      rounding=ROUND_HALF_UP)


def prepare_auction_document(auction, fast_forward=False):
    auction.auction_document.update({
        "_id": auction.auction_doc_id,
        "stages": [],
        "auctionID": auction._auction_data["data"].get("auctionID", ""),
        "procurementMethodType": auction._auction_data["data"].get(
            "procurementMethodType", "default"),
        "TENDERS_API_VERSION": auction.worker_defaults["resource_api_version"],
        "current_stage": -1,
        "current_phase": "",
        "results": [],
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
    if fast_forward:
        DUTCH_TIMEDELTA = timedelta(minutes=10)
        DUTCH_ROUNDS = 10
        FIRST_PAUSE = timedelta(seconds=10)
    else:
        from openprocurement.auction.insider.constants import DUTCH_TIMEDELTA,\
            FIRST_PAUSE
        # Additional round is needed to provide set amount of steps (auction starts with initial price)
        DUTCH_ROUNDS = auction.parameters['steps'] + 1
    dutch_step_duration = DUTCH_TIMEDELTA / DUTCH_ROUNDS
    next_stage_timedelta = auction.startDate
    amount = auction.auction_document['value']['amount']
    auction.auction_document['stages'] = [prepare_service_stage(
        start=auction.startDate.isoformat(),
        type="pause"
    )]
    auction.auction_document['auctionParameters'] = auction.parameters
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

        # Calculate next stage amount by getting decreasing percentage from initial_value
        amount = calculate_next_stage_amount(auction, index)

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


def prepare_auction_results(auction, bids_data):
    all_bids = deepcopy(bids_data)
    max_bids = []
    for bid_id in all_bids.keys():
        bid = get_latest_bid_for_bidder(all_bids[bid_id], bid_id)
        bid['bidder_name'] = auction.mapping[bid['bidder_id']]
        max_bids.append(
            prepare_results_stage(**bid)
        )
    return sorting_by_amount(max_bids)


def normalize_audit(audit):
    def normalize_bid(bid):
        if 'amount' in bid:
            bid['amount'] = str(bid['amount'])
        return bid

    new = deepcopy(audit)
    audit['results']['bids'] = map(
        normalize_bid,
        audit.get('results', {}).get('bids', [])
    )
    for phase in [DUTCH, SEALEDBID, BESTBID]:
        bids = audit['timeline'][phase].get('bids', [])
        audit['timeline'][phase]['bids'] = map(
            normalize_bid,
            bids
        )
    for k in audit['timeline'][DUTCH].keys():
        if k.startswith('turn'):
            audit['timeline'][DUTCH][k]['amount'] = str(
                audit['timeline'][DUTCH][k]['amount']
            )
    return audit


def normalize_document(document):
    normalized = deepcopy(document)
    for field in ['results', 'stages']:
        for index, stage in enumerate(document[field]):
            if isinstance(stage.get('amount'), Decimal):
                normalized[field][index]['amount'] = str(stage['amount'])
    return normalized

