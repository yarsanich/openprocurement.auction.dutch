# -*- coding: utf-8 -*-
import logging
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta

from dateutil.tz import tzlocal
from openprocurement.auction.utils import get_latest_bid_for_bidder
from openprocurement.auction.worker.journal import AUCTION_WORKER_API_APPROVED_DATA
from openprocurement.auction.worker.utils import prepare_service_stage
from openprocurement.auction.insider.constants import PRESTARTED, DUTCH,\
    PRESEALEDBID, SEALEDBID, PREBESTBID, BESTBID, END
from openprocurement.auction.insider.constants import MULTILINGUAL_FIELDS,\
    ADDITIONAL_LANGUAGES, DUTCH_DOWN_STEP, FIRST_PAUSE, SEALEDBID_TIMEDELTA,\
    BESTBID_TIMEDELTA, END_PHASE_PAUSE


LOGGER = logging.getLogger("Auction Worker")


def prepare_results_stage(
        bidder_id="",
        bidder_name="",
        amount="",
        time="",
        dutch_winner=""):
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
    return stage


prepare_bids_stage = prepare_results_stage

def post_results_data(auction, with_auctions_results=True):
    """TODO: make me work"""
    if with_auctions_results:
        for index, bid_info in enumerate(auction._auction_data["data"]["bids"]):
            if bid_info.get('status', 'active') == 'active':
                bidder_id = bid_info.get('bidder_id', bid_info.get('id', ''))
                if bidder_id:
                    try:
                        bid = get_latest_bid_for_bidder(auction.auction_document['results'], bidder_id)
                    except IndexError:
                        bid = ''
                    if bid:
                        auction._auction_data["data"]["bids"][index]["value"]["amount"] = bid['amount']
                        auction._auction_data["data"]["bids"][index]["date"] = bid['time']
    data = {'data': {'bids': auction._auction_data["data"]['bids']}}
    LOGGER.info(
        "Approved data: {}".format(data),
        extra={"JOURNAL_REQUEST_ID": auction.request_id,
               "MESSAGE_ID": AUCTION_WORKER_API_APPROVED_DATA}
    )
    if not auction.debug:
        return make_request(
            auction.tender_url + '/auction', data=data,
            user=auction.worker_defaults["TENDERS_API_TOKEN"],
            method='post',
            request_id=auction.request_id,
            session=auction.session
        )
    else:
        LOGGER.info(
            "Making request to api with params {}".format(
                dict(
                    method="post",
                    url=auction.tender_url + '/auction',
                    data=data
                )
        ))
        return data


def announce_results_data(auction, results=None):
    """TODO: make me work"""
    if not results:
        results = get_tender_data(
            auction.tender_url,
            user=auction.worker_defaults["resource_api_token"],
            request_id=auction.request_id,
            session=auction.session
        )
    bids_information = dict([
        (bid["id"], bid["tenderers"])
        for bid in results["data"]["bids"]
        if bid.get("status", "active") == "active"
    ])
    for index, stage in enumerate(auction.auction_document['results']):
        if 'bidder_id' in stage and stage['bidder_id'] in bids_information:
            auction.auction_document['results'][index].update({
                "label": {
                    'uk':bids_information[stage['bidder_id']][0]["name"],
                    'en': bids_information[stage['bidder_id']][0]["name"],
                    'ru': bids_information[stage['bidder_id']][0]["name"],
                }
            })
    return bids_information


def calculate_next_amount(initial_value, current_value):
    if not isinstance(current_value, Decimal):
        current_value = Decimal(str(current_value))
    if not isinstance(initial_value, Decimal):
        initial_value = Decimal(str(initial_value))
    return (current_value - (initial_value * DUTCH_DOWN_STEP)).quantize(
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
        "results": [],
        "timeline": {
            "auction_start": {},
        }
    }
    for phase in (DUTCH, SEALEDBID, BESTBID):
        audit['timeline'][phase] = prepare_timeline_stage()
    return audit


def get_dutch_winner(auction_document):
    try:
        return filter(
            lambda bid: bid.get('dutch_winner', False),
            auction_document['results']
        )[0]
    except Exception:
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
            DUTCH_ROUNDS, FIRST_PAUSE
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
        amount = calculate_next_amount(
            auction.auction_document['initial_value'],
            amount
        )
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


def get_auction_info(auction, prepare=False):
    if not auction.debug:
        if prepare:
            auction._auction_data = get_tender_data(
                auction.tender_url,
                request_id=auction.request_id,
                session=auction.session
            )
        else:
            auction._auction_data = {'data': {}}

        auction_data = get_tender_data(
            auction.tender_url + '/auction',
            user=auction.worker_defaults["resource_api_token"],
            request_id=auction.request_id,
            session=auction.session
        )
        if auction_data:
            auction._auction_data['data'].update(auction_data['data'])
            auction.startDate = auction.convert_datetime(auction._auction_data['data']['auctionPeriod']['startDate'])
            del auction_data
        else:
            auction.get_auction_document()
            if auction.auction_document:
                auction.auction_document["current_stage"] = -100
                auction.save_auction_document()
                LOGGER.warning(
                    "Cancel auction: {}".format(auction.auction_doc_id),
                    extra={
                        "JOURNAL_REQUEST_ID": auction.request_id,
                        "MESSAGE_ID": AUCTION_WORKER_API_AUCTION_CANCEL
                    }
                )
            else:
                LOGGER.error(
                    "Auction {} not exists".format(auction.auction_doc_id),
                    extra={
                        "JOURNAL_REQUEST_ID": auction.request_id,
                        "MESSAGE_ID": AUCTION_WORKER_API_AUCTION_NOT_EXIST
                    }
                )
            auction._end_auction_event.set()
            sys.exit(1)
    if 'bids' in auction._auction_data['data']:
        pass
    LOGGER.info(
        "Bidders count: {}".format(auction.bidders_count),
        extra={
            "JOURNAL_REQUEST_ID": auction.request_id,
            "MESSAGE_ID": AUCTION_WORKER_SERVICE_NUMBER_OF_BIDS
        }
    )

    auction.startDate = auction.convert_datetime(
        auction._auction_data['data']['auctionPeriod']['startDate']
    )

    if not prepare:
        auction.bidders_data = []

        for bid in auction._auction_data['data']['bids']:
            if bid.get('status', 'active') == 'active':
                auction.bidders_data.append({
                    'id': bid['id'],
                    'date': bid['date'],
                    'value': bid['value'],
                    'owner': bid.get('owner', '')
                })
        for index, uid in enumerate(auction.bidders_data):
            auction.mapping[auction.bidders_data[index]['id']] = str(index + 1)
