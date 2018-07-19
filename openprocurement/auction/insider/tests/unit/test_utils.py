# -*- coding: utf-8 -*-
from copy import deepcopy
from datetime import timedelta, datetime
from decimal import Decimal

from dateutil.tz import tzlocal
from iso8601 import iso8601

import pytest

from openprocurement.auction.insider.constants import (
    DUTCH, SEALEDBID, BESTBID, DUTCH_TIMEDELTA
)
from openprocurement.auction.insider.tests.data.data import tender_data
from openprocurement.auction.insider.utils import (
    prepare_results_stage, prepare_timeline_stage, prepare_audit, get_dutch_winner,
    announce_results_data, post_results_data, update_auction_document,
    lock_bids, update_stage, prepare_auction_document, get_sealed_bid_winner,
    get_fast_forward_data, prepare_bid,
    update_stage_for_phase, run_auction_fast_forward)


@pytest.mark.parametrize(
    'bidder_id, bidder_name, amount, time, dutch_winner, sealedbid_winner, expected',
    [
        ('id_1', 'bidder_name_1', '', 12345, True, False, {
            "amount": 0,
            'bidder_id': 'id_1',
            'time': '12345',
            'dutch_winner': True
        }),
        ('id_121334', 'bidder_name_1', 5000.0, '25.67', False, False, {
            "amount": 5000.0,
            'bidder_id': 'id_121334',
            'time': '25.67',
        }),
        ('some_id', 'bidder_name_1', 50000.0, 'time_value', False, True, {
            "amount": 50000.0,
            'bidder_id': 'some_id',
            'time': 'time_value',
            'sealedbid_winner': True
        }),
    ]
)
def test_prepare_results_stage(bidder_id,
                               bidder_name,
                               amount,
                               time,
                               dutch_winner,
                               sealedbid_winner,
                               expected):
    expected.update(
        {"label": {
            "en": "Bidder #{}".format(bidder_name),
            "uk": "Учасник №{}".format(bidder_name),
            "ru": "Участник №{}".format(bidder_name)
        }}
    )
    result = prepare_results_stage(bidder_id, bidder_name, amount, time, dutch_winner, sealedbid_winner)
    assert result == expected


def test_prepare_timeline_stage():
    timeline_stage_object = {
        'timeline': {
            'start': '',
            'end': ''
        },
        'bids': []
    }

    result = prepare_timeline_stage()
    assert result == timeline_stage_object


def test_prepare_audit(auction, mocker):
    mock_prepare_timeline_stage = mocker.MagicMock()
    mock_prepare_timeline_stage.return_value = 'timeline_stage_object'
    mocker.patch('openprocurement.auction.insider.utils.prepare_timeline_stage', mock_prepare_timeline_stage)

    audit = {
        "id": u'UA-11111',
        "auctionId": '',
        "auction_id": u'UA-11111',
        "auctionParameters": {'type': 'insider', 'dutchSteps': 80},
        "items": tender_data['data']['items'],
        "results": 'timeline_stage_object',
        "timeline": {
            "auction_start": {},
            DUTCH: 'timeline_stage_object',
            SEALEDBID: 'timeline_stage_object',
            BESTBID: 'timeline_stage_object'
        }
    }

    auction.get_auction_info()
    result = prepare_audit(auction)
    assert result == audit


def test_get_dutch_winner():
    auction_document = {
        'results': [
            {
                'bidder_id': '1'
            },
            {
                'bidder_id': '2',
                'dutch_winner': True
            },
            {
                'bidder_id': '3',
                'dutch_winner': True
            },
        ]
    }

    result = get_dutch_winner(auction_document)
    assert result == {'bidder_id': '2', 'dutch_winner': True}

    result = get_dutch_winner({'results': []})
    assert result == {}


def test_get_sealed_bid_winner():
    auction_document = {
        'results': [
            {
                'bidder_id': '1'
            },
            {
                'bidder_id': '2',
                'sealedbid_winner': True
            },
            {
                'bidder_id': '3',
                'sealedbid_winner': True
            },
        ]
    }

    result = get_sealed_bid_winner(auction_document)
    assert result == {'bidder_id': '2', 'sealedbid_winner': True}

    result = get_sealed_bid_winner({'results': []})
    assert result == {}


def test_announce_results_data(auction, mocker):
    tender_data_copy = deepcopy(tender_data)
    mock_get_tender_data = mocker.MagicMock()
    mock_get_tender_data.return_value = tender_data_copy
    mocker.patch('openprocurement.auction.insider.utils.get_tender_data', mock_get_tender_data)

    test_document = {
        'results': [
            {'bidder_id': 'c26d9eed99624c338ce0fca58a0aac32'},
            {'test_key': 'test_value'}
        ],
        'stages': [
            {'amount': 'test_amount',
             'start': '2014-11-19T12:00:30+00:00',
             'type': 'test',
             'bidder_id': 'c26d9eed99624c338ce0fca58a0aac32'}
        ]
    }
    auction.auction_document = test_document
    auction.generate_request_id()

    # results=None
    result = announce_results_data(auction)

    assert result == {u'c26d9eed99624c338ce0fca58a0aac32': tender_data_copy['data']['bids'][0]['tenderers'],
                      u'e4456d02263441ffb2f00ceafa661bb2': tender_data_copy['data']['bids'][1]['tenderers']}
    assert auction.auction_document['results'][1] == {'test_key': 'test_value'}
    assert len(auction.auction_document['results'][0]['label']) == 3
    assert auction.auction_document['results'][0]['label'].keys() == ['ru', 'en', 'uk']
    assert len(auction.auction_document['stages'][0]['label']) == 3
    assert auction.auction_document['stages'][0]['label'].keys() == ['ru', 'en', 'uk']

    auction.auction_document = test_document
    result = announce_results_data(auction, tender_data_copy)

    assert result == {u'c26d9eed99624c338ce0fca58a0aac32': tender_data_copy['data']['bids'][0]['tenderers'],
                      u'e4456d02263441ffb2f00ceafa661bb2': tender_data_copy['data']['bids'][1]['tenderers']}
    assert auction.auction_document['results'][1] == {'test_key': 'test_value'}
    assert len(auction.auction_document['results'][0]['label']) == 3
    assert auction.auction_document['results'][0]['label'].keys() == ['ru', 'en', 'uk']
    assert len(auction.auction_document['stages'][0]['label']) == 3
    assert auction.auction_document['stages'][0]['label'].keys() == ['ru', 'en', 'uk']


def test_post_results_data(auction, logger, mocker):
    from openprocurement.auction.insider.tests.data.data import tender_data
    tender_data_copy = deepcopy(tender_data)
    auction._auction_data = tender_data_copy

    mock_get_auction_info = mocker.patch.object(auction, 'get_auction_info', autospec=True)
    mock_get_auction_info.return_value = tender_data_copy

    auction.generate_request_id()

    # auction.debug is True
    result = post_results_data(auction=auction, with_auctions_results=False)
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert log_strings[0] == 'Approved data: {\'data\': {\'bids\': [{\'date\': \'2014-11-19T08:22:21.726234+00:00\', ' \
                             '\'id\': \'c26d9eed99624c338ce0fca58a0aac32\', \'value\': {\'currency\': None, ' \
                             '\'amount\': 0, \'valueAddedTaxIncluded\': True}, \'tenderers\': [{\'contactPoint\': {' \
                             '\'email\': \'automation+4077486456@smartweb.com.ua\', \'name\': ' \
                             '\'\\xd0\\xad\\xd0\\xbc\\xd0\\xbc\\xd0\\xb0\\xd0\\xbd\\xd1\\x83\\xd0\\xb8\\xd0\\xbb ' \
                             '\\xd0\\x9a\\xd0\\xb0\\xd0\\xbf\\xd1\\x83\\xd1\\x81\\xd1\\x82\\xd0\\xb8\\xd0\\xbd\\xd0' \
                             '\\xb0\', \'telephone\': \'+380139815286\'}, \'identifier\': {\'scheme\': \'UA-EDR\', ' \
                             '\'id\': \'46171\', \'uri\': \'http://9665642342.promtest.ua\', \'legalName\': ' \
                             '\'\\xd0\\xa4\\xd0\\xbe\\xd0\\xbc\\xd0\\xb8\\xd0\\xbd-\\xd0\\x90\\xd0\\xbb\\xd0\\xb5' \
                             '\\xd0\\xba\\xd1\\x81\\xd0\\xb0\\xd0\\xbd\\xd0\\xb4\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0' \
                             '\\xb0\'}, \'name\': ' \
                             '"\\xd0\\x9a\\xd0\\xbe\\xd0\\xbd\\xd1\\x86\\xd0\\xb5\\xd1\\x80\\xd1\\x82\\xd0\\xbd\\xd0' \
                             '\\xb8\\xd0\\xb9 \\xd0\\xb7\\xd0\\xb0\\xd0\\xba\\xd0\\xbb\\xd0\\xb0\\xd0\\xb4 ' \
                             '\\xd0\\xba\\xd1\\x83\\xd0\\xbb\\xd1\\x8c\\xd1\\x82\\xd1\\x83\\xd1\\x80\\xd0\\xb8 ' \
                             '\'\\xd0\\x9c\\xd1\\x83\\xd0\\xbd\\xd1\\x96\\xd1\\x86\\xd0\\xb8\\xd0\\xbf\\xd0\\xb0\\xd0' \
                             '\\xbb\\xd1\\x8c\\xd0\\xbd\\xd0\\xb0 ' \
                             '\\xd0\\xb0\\xd0\\xba\\xd0\\xb0\\xd0\\xb4\\xd0\\xb5\\xd0\\xbc\\xd1\\x96\\xd1\\x87\\xd0' \
                             '\\xbd\\xd0\\xb0 \\xd1\\x87\\xd0\\xbe\\xd0\\xbb\\xd0\\xbe\\xd0\\xb2\\xd1\\x96\\xd1\\x87' \
                             '\\xd0\\xb0 \\xd1\\x85\\xd0\\xbe\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0\\xb0 ' \
                             '\\xd0\\xba\\xd0\\xb0\\xd0\\xbf\\xd0\\xb5\\xd0\\xbb\\xd0\\xb0 \\xd1\\x96\\xd0\\xbc. ' \
                             '\\xd0\\x9b.\\xd0\\x9c. ' \
                             '\\xd0\\xa0\\xd0\\xb5\\xd0\\xb2\\xd1\\x83\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xbe\\xd0' \
                             '\\xb3\\xd0\\xbe\'", \'address\': {\'postalCode\': \'849999\', \'countryName\': ' \
                             '\'\\xd0\\xa3\\xd0\\xba\\xd1\\x80\\xd0\\xb0\\xd1\\x97\\xd0\\xbd\\xd0\\xb0\', ' \
                             '\'streetAddress\': \'6973 ' \
                             '\\xd0\\x90\\xd1\\x84\\xd0\\xb0\\xd0\\xbd\\xd0\\xb0\\xd1\\x81\\xd1\\x8c\\xd0\\xb5\\xd0' \
                             '\\xb2\\xd0\\xb0 Mountain Apt. 965\', \'region\': ' \
                             '\'\\xd0\\x94\\xd0\\xbe\\xd0\\xbd\\xd0\\xb5\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xb0 ' \
                             '\\xd0\\xbe\\xd0\\xb1\\xd0\\xbb\\xd0\\xb0\\xd1\\x81\\xd1\\x82\\xd1\\x8c\', \'locality\': ' \
                             '\'Donetsk\'}}]}, {\'date\': \'2014-11-19T08:22:24.038426+00:00\', ' \
                             '\'id\': \'e4456d02263441ffb2f00ceafa661bb2\', \'value\': {\'currency\': None, ' \
                             '\'amount\': 0, \'valueAddedTaxIncluded\': True}, \'tenderers\': [{\'contactPoint\': {' \
                             '\'email\': \'automation+4077486456@smartweb.com.ua\', \'name\': ' \
                             '\'\\xd0\\xad\\xd0\\xbc\\xd0\\xbc\\xd0\\xb0\\xd0\\xbd\\xd1\\x83\\xd0\\xb8\\xd0\\xbb ' \
                             '\\xd0\\x9a\\xd0\\xb0\\xd0\\xbf\\xd1\\x83\\xd1\\x81\\xd1\\x82\\xd0\\xb8\\xd0\\xbd\\xd0' \
                             '\\xb0\', \'telephone\': \'+380139815286\'}, \'identifier\': {\'scheme\': \'UA-EDR\', ' \
                             '\'id\': \'46171\', \'uri\': \'http://9665642342.promtest.ua\', \'legalName\': ' \
                             '\'\\xd0\\xa4\\xd0\\xbe\\xd0\\xbc\\xd0\\xb8\\xd0\\xbd-\\xd0\\x90\\xd0\\xbb\\xd0\\xb5' \
                             '\\xd0\\xba\\xd1\\x81\\xd0\\xb0\\xd0\\xbd\\xd0\\xb4\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0' \
                             '\\xb0\'}, \'name\': ' \
                             '"\\xd0\\x9a\\xd0\\x9e\\xd0\\x9c\\xd0\\xa3\\xd0\\x9d\\xd0\\x90\\xd0\\x9b\\xd0\\xac\\xd0' \
                             '\\x9d\\xd0\\x95 \\xd0\\x9f\\xd0\\x86\\xd0\\x94\\xd0\\x9f\\xd0\\xa0\\xd0\\x98\\xd0\\x84' \
                             '\\xd0\\x9c\\xd0\\xa1\\xd0\\xa2\\xd0\\x92\\xd0\\x9e ' \
                             '\'\\xd0\\x9a\\xd0\\x98\\xd0\\x87\\xd0\\x92\\xd0\\x9f\\xd0\\x90\\xd0\\xa1\\xd0\\xa2\\xd0' \
                             '\\xa0\\xd0\\x90\\xd0\\x9d\\xd0\\xa1\'", \'address\': {\'postalCode\': \'849999\', ' \
                             '\'countryName\': ' \
                             '\'\\xd0\\xa3\\xd0\\xba\\xd1\\x80\\xd0\\xb0\\xd1\\x97\\xd0\\xbd\\xd0\\xb0\', ' \
                             '\'streetAddress\': \'6973 ' \
                             '\\xd0\\x90\\xd1\\x84\\xd0\\xb0\\xd0\\xbd\\xd0\\xb0\\xd1\\x81\\xd1\\x8c\\xd0\\xb5\\xd0' \
                             '\\xb2\\xd0\\xb0 Mountain Apt. 965\', \'region\': ' \
                             '\'\\xd0\\x94\\xd0\\xbe\\xd0\\xbd\\xd0\\xb5\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xb0 ' \
                             '\\xd0\\xbe\\xd0\\xb1\\xd0\\xbb\\xd0\\xb0\\xd1\\x81\\xd1\\x82\\xd1\\x8c\', \'locality\': ' \
                             '\'Donetsk\'}}]}]}}'

    assert log_strings[1] == 'Making request to api with params {\'url\': ' \
                             '\'http://127.0.0.1:6543/api/2.3/auctions/UA-11111/auction\', \'data\': {\'data\': {' \
                             '\'bids\': [{\'date\': \'2014-11-19T08:22:21.726234+00:00\', ' \
                             '\'id\': \'c26d9eed99624c338ce0fca58a0aac32\', \'value\': {\'currency\': None, ' \
                             '\'amount\': 0, \'valueAddedTaxIncluded\': True}, \'tenderers\': [{\'contactPoint\': {' \
                             '\'email\': \'automation+4077486456@smartweb.com.ua\', \'name\': ' \
                             '\'\\xd0\\xad\\xd0\\xbc\\xd0\\xbc\\xd0\\xb0\\xd0\\xbd\\xd1\\x83\\xd0\\xb8\\xd0\\xbb ' \
                             '\\xd0\\x9a\\xd0\\xb0\\xd0\\xbf\\xd1\\x83\\xd1\\x81\\xd1\\x82\\xd0\\xb8\\xd0\\xbd\\xd0' \
                             '\\xb0\', \'telephone\': \'+380139815286\'}, \'identifier\': {\'scheme\': \'UA-EDR\', ' \
                             '\'id\': \'46171\', \'uri\': \'http://9665642342.promtest.ua\', \'legalName\': ' \
                             '\'\\xd0\\xa4\\xd0\\xbe\\xd0\\xbc\\xd0\\xb8\\xd0\\xbd-\\xd0\\x90\\xd0\\xbb\\xd0\\xb5' \
                             '\\xd0\\xba\\xd1\\x81\\xd0\\xb0\\xd0\\xbd\\xd0\\xb4\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0' \
                             '\\xb0\'}, \'name\': ' \
                             '"\\xd0\\x9a\\xd0\\xbe\\xd0\\xbd\\xd1\\x86\\xd0\\xb5\\xd1\\x80\\xd1\\x82\\xd0\\xbd\\xd0' \
                             '\\xb8\\xd0\\xb9 \\xd0\\xb7\\xd0\\xb0\\xd0\\xba\\xd0\\xbb\\xd0\\xb0\\xd0\\xb4 ' \
                             '\\xd0\\xba\\xd1\\x83\\xd0\\xbb\\xd1\\x8c\\xd1\\x82\\xd1\\x83\\xd1\\x80\\xd0\\xb8 ' \
                             '\'\\xd0\\x9c\\xd1\\x83\\xd0\\xbd\\xd1\\x96\\xd1\\x86\\xd0\\xb8\\xd0\\xbf\\xd0\\xb0\\xd0' \
                             '\\xbb\\xd1\\x8c\\xd0\\xbd\\xd0\\xb0 ' \
                             '\\xd0\\xb0\\xd0\\xba\\xd0\\xb0\\xd0\\xb4\\xd0\\xb5\\xd0\\xbc\\xd1\\x96\\xd1\\x87\\xd0' \
                             '\\xbd\\xd0\\xb0 \\xd1\\x87\\xd0\\xbe\\xd0\\xbb\\xd0\\xbe\\xd0\\xb2\\xd1\\x96\\xd1\\x87' \
                             '\\xd0\\xb0 \\xd1\\x85\\xd0\\xbe\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0\\xb0 ' \
                             '\\xd0\\xba\\xd0\\xb0\\xd0\\xbf\\xd0\\xb5\\xd0\\xbb\\xd0\\xb0 \\xd1\\x96\\xd0\\xbc. ' \
                             '\\xd0\\x9b.\\xd0\\x9c. ' \
                             '\\xd0\\xa0\\xd0\\xb5\\xd0\\xb2\\xd1\\x83\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xbe\\xd0' \
                             '\\xb3\\xd0\\xbe\'", \'address\': {\'postalCode\': \'849999\', \'countryName\': ' \
                             '\'\\xd0\\xa3\\xd0\\xba\\xd1\\x80\\xd0\\xb0\\xd1\\x97\\xd0\\xbd\\xd0\\xb0\', ' \
                             '\'streetAddress\': \'6973 ' \
                             '\\xd0\\x90\\xd1\\x84\\xd0\\xb0\\xd0\\xbd\\xd0\\xb0\\xd1\\x81\\xd1\\x8c\\xd0\\xb5\\xd0' \
                             '\\xb2\\xd0\\xb0 Mountain Apt. 965\', \'region\': ' \
                             '\'\\xd0\\x94\\xd0\\xbe\\xd0\\xbd\\xd0\\xb5\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xb0 ' \
                             '\\xd0\\xbe\\xd0\\xb1\\xd0\\xbb\\xd0\\xb0\\xd1\\x81\\xd1\\x82\\xd1\\x8c\', \'locality\': ' \
                             '\'Donetsk\'}}]}, {\'date\': \'2014-11-19T08:22:24.038426+00:00\', ' \
                             '\'id\': \'e4456d02263441ffb2f00ceafa661bb2\', \'value\': {\'currency\': None, ' \
                             '\'amount\': 0, \'valueAddedTaxIncluded\': True}, \'tenderers\': [{\'contactPoint\': {' \
                             '\'email\': \'automation+4077486456@smartweb.com.ua\', \'name\': ' \
                             '\'\\xd0\\xad\\xd0\\xbc\\xd0\\xbc\\xd0\\xb0\\xd0\\xbd\\xd1\\x83\\xd0\\xb8\\xd0\\xbb ' \
                             '\\xd0\\x9a\\xd0\\xb0\\xd0\\xbf\\xd1\\x83\\xd1\\x81\\xd1\\x82\\xd0\\xb8\\xd0\\xbd\\xd0' \
                             '\\xb0\', \'telephone\': \'+380139815286\'}, \'identifier\': {\'scheme\': \'UA-EDR\', ' \
                             '\'id\': \'46171\', \'uri\': \'http://9665642342.promtest.ua\', \'legalName\': ' \
                             '\'\\xd0\\xa4\\xd0\\xbe\\xd0\\xbc\\xd0\\xb8\\xd0\\xbd-\\xd0\\x90\\xd0\\xbb\\xd0\\xb5' \
                             '\\xd0\\xba\\xd1\\x81\\xd0\\xb0\\xd0\\xbd\\xd0\\xb4\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0' \
                             '\\xb0\'}, \'name\': ' \
                             '"\\xd0\\x9a\\xd0\\x9e\\xd0\\x9c\\xd0\\xa3\\xd0\\x9d\\xd0\\x90\\xd0\\x9b\\xd0\\xac\\xd0' \
                             '\\x9d\\xd0\\x95 \\xd0\\x9f\\xd0\\x86\\xd0\\x94\\xd0\\x9f\\xd0\\xa0\\xd0\\x98\\xd0\\x84' \
                             '\\xd0\\x9c\\xd0\\xa1\\xd0\\xa2\\xd0\\x92\\xd0\\x9e ' \
                             '\'\\xd0\\x9a\\xd0\\x98\\xd0\\x87\\xd0\\x92\\xd0\\x9f\\xd0\\x90\\xd0\\xa1\\xd0\\xa2\\xd0' \
                             '\\xa0\\xd0\\x90\\xd0\\x9d\\xd0\\xa1\'", \'address\': {\'postalCode\': \'849999\', ' \
                             '\'countryName\': ' \
                             '\'\\xd0\\xa3\\xd0\\xba\\xd1\\x80\\xd0\\xb0\\xd1\\x97\\xd0\\xbd\\xd0\\xb0\', ' \
                             '\'streetAddress\': \'6973 ' \
                             '\\xd0\\x90\\xd1\\x84\\xd0\\xb0\\xd0\\xbd\\xd0\\xb0\\xd1\\x81\\xd1\\x8c\\xd0\\xb5\\xd0' \
                             '\\xb2\\xd0\\xb0 Mountain Apt. 965\', \'region\': ' \
                             '\'\\xd0\\x94\\xd0\\xbe\\xd0\\xbd\\xd0\\xb5\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xb0 ' \
                             '\\xd0\\xbe\\xd0\\xb1\\xd0\\xbb\\xd0\\xb0\\xd1\\x81\\xd1\\x82\\xd1\\x8c\', \'locality\': ' \
                             '\'Donetsk\'}}]}]}}, \'method\': \'post\'}'

    bids_data = {'data': {'bids': [
        {'date': '2014-11-19T08:22:21.726234+00:00',
         'id': 'c26d9eed99624c338ce0fca58a0aac32',
         'tenderers': [{'address': {'countryName': '\xd0\xa3\xd0\xba\xd1\x80\xd0\xb0\xd1\x97\xd0\xbd\xd0\xb0',
                                    'locality': 'Donetsk',
                                    'postalCode': '849999',
                                    'region': '\xd0\x94\xd0\xbe\xd0\xbd\xd0\xb5\xd1\x86\xd1\x8c\xd0\xba\xd0\xb0 \xd0\xbe\xd0\xb1\xd0\xbb\xd0\xb0\xd1\x81\xd1\x82\xd1\x8c',
                                    'streetAddress': '6973 \xd0\x90\xd1\x84\xd0\xb0\xd0\xbd\xd0\xb0\xd1\x81\xd1\x8c\xd0\xb5\xd0\xb2\xd0\xb0 Mountain Apt. 965'},
                        'contactPoint': {'email': 'automation+4077486456@smartweb.com.ua',
                                         'name': '\xd0\xad\xd0\xbc\xd0\xbc\xd0\xb0\xd0\xbd\xd1\x83\xd0\xb8\xd0\xbb \xd0\x9a\xd0\xb0\xd0\xbf\xd1\x83\xd1\x81\xd1\x82\xd0\xb8\xd0\xbd\xd0\xb0',
                                         'telephone': '+380139815286'},
                        'identifier': {'id': '46171',
                                       'legalName': '\xd0\xa4\xd0\xbe\xd0\xbc\xd0\xb8\xd0\xbd-\xd0\x90\xd0\xbb\xd0\xb5\xd0\xba\xd1\x81\xd0\xb0\xd0\xbd\xd0\xb4\xd1\x80\xd0\xbe\xd0\xb2\xd0\xb0',
                                       'scheme': 'UA-EDR',
                                       'uri': 'http://9665642342.promtest.ua'},
                        'name': "\xd0\x9a\xd0\xbe\xd0\xbd\xd1\x86\xd0\xb5\xd1\x80\xd1\x82\xd0\xbd\xd0\xb8\xd0\xb9 \xd0\xb7\xd0\xb0\xd0\xba\xd0\xbb\xd0\xb0\xd0\xb4 \xd0\xba\xd1\x83\xd0\xbb\xd1\x8c\xd1\x82\xd1\x83\xd1\x80\xd0\xb8 '\xd0\x9c\xd1\x83\xd0\xbd\xd1\x96\xd1\x86\xd0\xb8\xd0\xbf\xd0\xb0\xd0\xbb\xd1\x8c\xd0\xbd\xd0\xb0 \xd0\xb0\xd0\xba\xd0\xb0\xd0\xb4\xd0\xb5\xd0\xbc\xd1\x96\xd1\x87\xd0\xbd\xd0\xb0 \xd1\x87\xd0\xbe\xd0\xbb\xd0\xbe\xd0\xb2\xd1\x96\xd1\x87\xd0\xb0 \xd1\x85\xd0\xbe\xd1\x80\xd0\xbe\xd0\xb2\xd0\xb0 \xd0\xba\xd0\xb0\xd0\xbf\xd0\xb5\xd0\xbb\xd0\xb0 \xd1\x96\xd0\xbc. \xd0\x9b.\xd0\x9c. \xd0\xa0\xd0\xb5\xd0\xb2\xd1\x83\xd1\x86\xd1\x8c\xd0\xba\xd0\xbe\xd0\xb3\xd0\xbe'"}],
         'value': {'amount': 0,
                   'currency': None,
                   'valueAddedTaxIncluded': True}},
        {'date': '2014-11-19T08:22:24.038426+00:00',
         'id': 'e4456d02263441ffb2f00ceafa661bb2',
         'tenderers': [{'address': {'countryName': '\xd0\xa3\xd0\xba\xd1\x80\xd0\xb0\xd1\x97\xd0\xbd\xd0\xb0',
                                    'locality': 'Donetsk',
                                    'postalCode': '849999',
                                    'region': '\xd0\x94\xd0\xbe\xd0\xbd\xd0\xb5\xd1\x86\xd1\x8c\xd0\xba\xd0\xb0 \xd0\xbe\xd0\xb1\xd0\xbb\xd0\xb0\xd1\x81\xd1\x82\xd1\x8c',
                                    'streetAddress': '6973 \xd0\x90\xd1\x84\xd0\xb0\xd0\xbd\xd0\xb0\xd1\x81\xd1\x8c\xd0\xb5\xd0\xb2\xd0\xb0 Mountain Apt. 965'},
                        'contactPoint': {'email': 'automation+4077486456@smartweb.com.ua',
                                         'name': '\xd0\xad\xd0\xbc\xd0\xbc\xd0\xb0\xd0\xbd\xd1\x83\xd0\xb8\xd0\xbb \xd0\x9a\xd0\xb0\xd0\xbf\xd1\x83\xd1\x81\xd1\x82\xd0\xb8\xd0\xbd\xd0\xb0',
                                         'telephone': '+380139815286'},
                        'identifier': {'id': '46171',
                                       'legalName': '\xd0\xa4\xd0\xbe\xd0\xbc\xd0\xb8\xd0\xbd-\xd0\x90\xd0\xbb\xd0\xb5\xd0\xba\xd1\x81\xd0\xb0\xd0\xbd\xd0\xb4\xd1\x80\xd0\xbe\xd0\xb2\xd0\xb0',
                                       'scheme': 'UA-EDR',
                                       'uri': 'http://9665642342.promtest.ua'},
                        'name': "\xd0\x9a\xd0\x9e\xd0\x9c\xd0\xa3\xd0\x9d\xd0\x90\xd0\x9b\xd0\xac\xd0\x9d\xd0\x95 \xd0\x9f\xd0\x86\xd0\x94\xd0\x9f\xd0\xa0\xd0\x98\xd0\x84\xd0\x9c\xd0\xa1\xd0\xa2\xd0\x92\xd0\x9e '\xd0\x9a\xd0\x98\xd0\x87\xd0\x92\xd0\x9f\xd0\x90\xd0\xa1\xd0\xa2\xd0\xa0\xd0\x90\xd0\x9d\xd0\xa1'"}],
         'value': {'amount': 0,
                   'currency': None,
                   'valueAddedTaxIncluded': True}}
    ]}}
    assert result == bids_data

    mock_make_request = mocker.MagicMock()
    mock_make_request.return_value = 'make_request mocked response'
    mocker.patch('openprocurement.auction.insider.utils.make_request', mock_make_request)

    auction.debug = False
    result = post_results_data(auction=auction, with_auctions_results=False)
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert result == 'make_request mocked response'
    mock_make_request.assert_called_once_with(
        auction.tender_url + '/auction', data=bids_data,
        user=auction.worker_defaults["resource_api_token"],
        method='post',
        request_id=auction.request_id,
        session=auction.session
    )
    assert log_strings[-2] == 'Approved data: {\'data\': {\'bids\': [{\'date\': \'2014-11-19T08:22:21.726234+00:00\', ' \
                              '\'id\': \'c26d9eed99624c338ce0fca58a0aac32\', \'value\': {\'currency\': None, ' \
                              '\'amount\': 0, \'valueAddedTaxIncluded\': True}, \'tenderers\': [{\'contactPoint\': {' \
                              '\'email\': \'automation+4077486456@smartweb.com.ua\', \'name\': ' \
                              '\'\\xd0\\xad\\xd0\\xbc\\xd0\\xbc\\xd0\\xb0\\xd0\\xbd\\xd1\\x83\\xd0\\xb8\\xd0\\xbb ' \
                              '\\xd0\\x9a\\xd0\\xb0\\xd0\\xbf\\xd1\\x83\\xd1\\x81\\xd1\\x82\\xd0\\xb8\\xd0\\xbd\\xd0' \
                              '\\xb0\', \'telephone\': \'+380139815286\'}, \'identifier\': {\'scheme\': \'UA-EDR\', ' \
                              '\'id\': \'46171\', \'uri\': \'http://9665642342.promtest.ua\', \'legalName\': ' \
                              '\'\\xd0\\xa4\\xd0\\xbe\\xd0\\xbc\\xd0\\xb8\\xd0\\xbd-\\xd0\\x90\\xd0\\xbb\\xd0\\xb5' \
                              '\\xd0\\xba\\xd1\\x81\\xd0\\xb0\\xd0\\xbd\\xd0\\xb4\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0' \
                              '\\xb0\'}, \'name\': ' \
                              '"\\xd0\\x9a\\xd0\\xbe\\xd0\\xbd\\xd1\\x86\\xd0\\xb5\\xd1\\x80\\xd1\\x82\\xd0\\xbd\\xd0' \
                              '\\xb8\\xd0\\xb9 \\xd0\\xb7\\xd0\\xb0\\xd0\\xba\\xd0\\xbb\\xd0\\xb0\\xd0\\xb4 ' \
                              '\\xd0\\xba\\xd1\\x83\\xd0\\xbb\\xd1\\x8c\\xd1\\x82\\xd1\\x83\\xd1\\x80\\xd0\\xb8 ' \
                              '\'\\xd0\\x9c\\xd1\\x83\\xd0\\xbd\\xd1\\x96\\xd1\\x86\\xd0\\xb8\\xd0\\xbf\\xd0\\xb0' \
                              '\\xd0\\xbb\\xd1\\x8c\\xd0\\xbd\\xd0\\xb0 ' \
                              '\\xd0\\xb0\\xd0\\xba\\xd0\\xb0\\xd0\\xb4\\xd0\\xb5\\xd0\\xbc\\xd1\\x96\\xd1\\x87\\xd0' \
                              '\\xbd\\xd0\\xb0 ' \
                              '\\xd1\\x87\\xd0\\xbe\\xd0\\xbb\\xd0\\xbe\\xd0\\xb2\\xd1\\x96\\xd1\\x87\\xd0\\xb0 ' \
                              '\\xd1\\x85\\xd0\\xbe\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0\\xb0 ' \
                              '\\xd0\\xba\\xd0\\xb0\\xd0\\xbf\\xd0\\xb5\\xd0\\xbb\\xd0\\xb0 \\xd1\\x96\\xd0\\xbc. ' \
                              '\\xd0\\x9b.\\xd0\\x9c. ' \
                              '\\xd0\\xa0\\xd0\\xb5\\xd0\\xb2\\xd1\\x83\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xbe\\xd0' \
                              '\\xb3\\xd0\\xbe\'", \'address\': {\'postalCode\': \'849999\', \'countryName\': ' \
                              '\'\\xd0\\xa3\\xd0\\xba\\xd1\\x80\\xd0\\xb0\\xd1\\x97\\xd0\\xbd\\xd0\\xb0\', ' \
                              '\'streetAddress\': \'6973 ' \
                              '\\xd0\\x90\\xd1\\x84\\xd0\\xb0\\xd0\\xbd\\xd0\\xb0\\xd1\\x81\\xd1\\x8c\\xd0\\xb5\\xd0' \
                              '\\xb2\\xd0\\xb0 Mountain Apt. 965\', \'region\': ' \
                              '\'\\xd0\\x94\\xd0\\xbe\\xd0\\xbd\\xd0\\xb5\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xb0 ' \
                              '\\xd0\\xbe\\xd0\\xb1\\xd0\\xbb\\xd0\\xb0\\xd1\\x81\\xd1\\x82\\xd1\\x8c\', ' \
                              '\'locality\': \'Donetsk\'}}]}, {\'date\': \'2014-11-19T08:22:24.038426+00:00\', ' \
                              '\'id\': \'e4456d02263441ffb2f00ceafa661bb2\', \'value\': {\'currency\': None, ' \
                              '\'amount\': 0, \'valueAddedTaxIncluded\': True}, \'tenderers\': [{\'contactPoint\': {' \
                              '\'email\': \'automation+4077486456@smartweb.com.ua\', \'name\': ' \
                              '\'\\xd0\\xad\\xd0\\xbc\\xd0\\xbc\\xd0\\xb0\\xd0\\xbd\\xd1\\x83\\xd0\\xb8\\xd0\\xbb ' \
                              '\\xd0\\x9a\\xd0\\xb0\\xd0\\xbf\\xd1\\x83\\xd1\\x81\\xd1\\x82\\xd0\\xb8\\xd0\\xbd\\xd0' \
                              '\\xb0\', \'telephone\': \'+380139815286\'}, \'identifier\': {\'scheme\': \'UA-EDR\', ' \
                              '\'id\': \'46171\', \'uri\': \'http://9665642342.promtest.ua\', \'legalName\': ' \
                              '\'\\xd0\\xa4\\xd0\\xbe\\xd0\\xbc\\xd0\\xb8\\xd0\\xbd-\\xd0\\x90\\xd0\\xbb\\xd0\\xb5' \
                              '\\xd0\\xba\\xd1\\x81\\xd0\\xb0\\xd0\\xbd\\xd0\\xb4\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0' \
                              '\\xb0\'}, \'name\': ' \
                              '"\\xd0\\x9a\\xd0\\x9e\\xd0\\x9c\\xd0\\xa3\\xd0\\x9d\\xd0\\x90\\xd0\\x9b\\xd0\\xac\\xd0' \
                              '\\x9d\\xd0\\x95 ' \
                              '\\xd0\\x9f\\xd0\\x86\\xd0\\x94\\xd0\\x9f\\xd0\\xa0\\xd0\\x98\\xd0\\x84\\xd0\\x9c\\xd0' \
                              '\\xa1\\xd0\\xa2\\xd0\\x92\\xd0\\x9e ' \
                              '\'\\xd0\\x9a\\xd0\\x98\\xd0\\x87\\xd0\\x92\\xd0\\x9f\\xd0\\x90\\xd0\\xa1\\xd0\\xa2' \
                              '\\xd0\\xa0\\xd0\\x90\\xd0\\x9d\\xd0\\xa1\'", \'address\': {\'postalCode\': \'849999\', ' \
                              '\'countryName\': ' \
                              '\'\\xd0\\xa3\\xd0\\xba\\xd1\\x80\\xd0\\xb0\\xd1\\x97\\xd0\\xbd\\xd0\\xb0\', ' \
                              '\'streetAddress\': \'6973 ' \
                              '\\xd0\\x90\\xd1\\x84\\xd0\\xb0\\xd0\\xbd\\xd0\\xb0\\xd1\\x81\\xd1\\x8c\\xd0\\xb5\\xd0' \
                              '\\xb2\\xd0\\xb0 Mountain Apt. 965\', \'region\': ' \
                              '\'\\xd0\\x94\\xd0\\xbe\\xd0\\xbd\\xd0\\xb5\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xb0 ' \
                              '\\xd0\\xbe\\xd0\\xb1\\xd0\\xbb\\xd0\\xb0\\xd1\\x81\\xd1\\x82\\xd1\\x8c\', ' \
                              '\'locality\': \'Donetsk\'}}]}]}}'

    test_document = {
        'value': {
            'currency': 'UAH',
            'valueAddedTaxIncluded': True
        },
        'results': [
            {
                'bidder_id': 'e4456d02263441ffb2f00ceafa661bb2',
                'amount': 'amount from auction_doucument["results"]',
                'time': '2014-11-19T12:00:00+00:00'
            }
        ]
    }

    auction.auction_document = test_document

    auction.debug = True
    result = post_results_data(auction=auction, with_auctions_results=True)
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert log_strings[-3] == 'Approved data: {\'data\': {\'bids\': [{\'date\': \'2014-11-19T08:22:21.726234+00:00\', ' \
                              '\'id\': \'c26d9eed99624c338ce0fca58a0aac32\', \'value\': {\'currency\': None, ' \
                              '\'amount\': 0, \'valueAddedTaxIncluded\': True}, \'tenderers\': [{\'contactPoint\': {' \
                              '\'email\': \'automation+4077486456@smartweb.com.ua\', \'name\': ' \
                              '\'\\xd0\\xad\\xd0\\xbc\\xd0\\xbc\\xd0\\xb0\\xd0\\xbd\\xd1\\x83\\xd0\\xb8\\xd0\\xbb ' \
                              '\\xd0\\x9a\\xd0\\xb0\\xd0\\xbf\\xd1\\x83\\xd1\\x81\\xd1\\x82\\xd0\\xb8\\xd0\\xbd\\xd0' \
                              '\\xb0\', \'telephone\': \'+380139815286\'}, \'identifier\': {\'scheme\': \'UA-EDR\', ' \
                              '\'id\': \'46171\', \'uri\': \'http://9665642342.promtest.ua\', \'legalName\': ' \
                              '\'\\xd0\\xa4\\xd0\\xbe\\xd0\\xbc\\xd0\\xb8\\xd0\\xbd-\\xd0\\x90\\xd0\\xbb\\xd0\\xb5' \
                              '\\xd0\\xba\\xd1\\x81\\xd0\\xb0\\xd0\\xbd\\xd0\\xb4\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0' \
                              '\\xb0\'}, \'name\': ' \
                              '"\\xd0\\x9a\\xd0\\xbe\\xd0\\xbd\\xd1\\x86\\xd0\\xb5\\xd1\\x80\\xd1\\x82\\xd0\\xbd\\xd0' \
                              '\\xb8\\xd0\\xb9 \\xd0\\xb7\\xd0\\xb0\\xd0\\xba\\xd0\\xbb\\xd0\\xb0\\xd0\\xb4 ' \
                              '\\xd0\\xba\\xd1\\x83\\xd0\\xbb\\xd1\\x8c\\xd1\\x82\\xd1\\x83\\xd1\\x80\\xd0\\xb8 ' \
                              '\'\\xd0\\x9c\\xd1\\x83\\xd0\\xbd\\xd1\\x96\\xd1\\x86\\xd0\\xb8\\xd0\\xbf\\xd0\\xb0' \
                              '\\xd0\\xbb\\xd1\\x8c\\xd0\\xbd\\xd0\\xb0 ' \
                              '\\xd0\\xb0\\xd0\\xba\\xd0\\xb0\\xd0\\xb4\\xd0\\xb5\\xd0\\xbc\\xd1\\x96\\xd1\\x87\\xd0' \
                              '\\xbd\\xd0\\xb0 ' \
                              '\\xd1\\x87\\xd0\\xbe\\xd0\\xbb\\xd0\\xbe\\xd0\\xb2\\xd1\\x96\\xd1\\x87\\xd0\\xb0 ' \
                              '\\xd1\\x85\\xd0\\xbe\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0\\xb0 ' \
                              '\\xd0\\xba\\xd0\\xb0\\xd0\\xbf\\xd0\\xb5\\xd0\\xbb\\xd0\\xb0 \\xd1\\x96\\xd0\\xbc. ' \
                              '\\xd0\\x9b.\\xd0\\x9c. ' \
                              '\\xd0\\xa0\\xd0\\xb5\\xd0\\xb2\\xd1\\x83\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xbe\\xd0' \
                              '\\xb3\\xd0\\xbe\'", \'address\': {\'postalCode\': \'849999\', \'countryName\': ' \
                              '\'\\xd0\\xa3\\xd0\\xba\\xd1\\x80\\xd0\\xb0\\xd1\\x97\\xd0\\xbd\\xd0\\xb0\', ' \
                              '\'streetAddress\': \'6973 ' \
                              '\\xd0\\x90\\xd1\\x84\\xd0\\xb0\\xd0\\xbd\\xd0\\xb0\\xd1\\x81\\xd1\\x8c\\xd0\\xb5\\xd0' \
                              '\\xb2\\xd0\\xb0 Mountain Apt. 965\', \'region\': ' \
                              '\'\\xd0\\x94\\xd0\\xbe\\xd0\\xbd\\xd0\\xb5\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xb0 ' \
                              '\\xd0\\xbe\\xd0\\xb1\\xd0\\xbb\\xd0\\xb0\\xd1\\x81\\xd1\\x82\\xd1\\x8c\', ' \
                              '\'locality\': \'Donetsk\'}}]}, {\'date\': \'2014-11-19T12:00:00+00:00\', ' \
                              '\'id\': \'e4456d02263441ffb2f00ceafa661bb2\', \'value\': {\'currency\': \'UAH\', ' \
                              '\'amount\': \'amount from auction_doucument["results"]\', \'valueAddedTaxIncluded\': ' \
                              'True}, \'tenderers\': [{\'contactPoint\': {\'email\': ' \
                              '\'automation+4077486456@smartweb.com.ua\', \'name\': ' \
                              '\'\\xd0\\xad\\xd0\\xbc\\xd0\\xbc\\xd0\\xb0\\xd0\\xbd\\xd1\\x83\\xd0\\xb8\\xd0\\xbb ' \
                              '\\xd0\\x9a\\xd0\\xb0\\xd0\\xbf\\xd1\\x83\\xd1\\x81\\xd1\\x82\\xd0\\xb8\\xd0\\xbd\\xd0' \
                              '\\xb0\', \'telephone\': \'+380139815286\'}, \'identifier\': {\'scheme\': \'UA-EDR\', ' \
                              '\'id\': \'46171\', \'uri\': \'http://9665642342.promtest.ua\', \'legalName\': ' \
                              '\'\\xd0\\xa4\\xd0\\xbe\\xd0\\xbc\\xd0\\xb8\\xd0\\xbd-\\xd0\\x90\\xd0\\xbb\\xd0\\xb5' \
                              '\\xd0\\xba\\xd1\\x81\\xd0\\xb0\\xd0\\xbd\\xd0\\xb4\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0' \
                              '\\xb0\'}, \'name\': ' \
                              '"\\xd0\\x9a\\xd0\\x9e\\xd0\\x9c\\xd0\\xa3\\xd0\\x9d\\xd0\\x90\\xd0\\x9b\\xd0\\xac\\xd0' \
                              '\\x9d\\xd0\\x95 ' \
                              '\\xd0\\x9f\\xd0\\x86\\xd0\\x94\\xd0\\x9f\\xd0\\xa0\\xd0\\x98\\xd0\\x84\\xd0\\x9c\\xd0' \
                              '\\xa1\\xd0\\xa2\\xd0\\x92\\xd0\\x9e ' \
                              '\'\\xd0\\x9a\\xd0\\x98\\xd0\\x87\\xd0\\x92\\xd0\\x9f\\xd0\\x90\\xd0\\xa1\\xd0\\xa2' \
                              '\\xd0\\xa0\\xd0\\x90\\xd0\\x9d\\xd0\\xa1\'", \'address\': {\'postalCode\': \'849999\', ' \
                              '\'countryName\': ' \
                              '\'\\xd0\\xa3\\xd0\\xba\\xd1\\x80\\xd0\\xb0\\xd1\\x97\\xd0\\xbd\\xd0\\xb0\', ' \
                              '\'streetAddress\': \'6973 ' \
                              '\\xd0\\x90\\xd1\\x84\\xd0\\xb0\\xd0\\xbd\\xd0\\xb0\\xd1\\x81\\xd1\\x8c\\xd0\\xb5\\xd0' \
                              '\\xb2\\xd0\\xb0 Mountain Apt. 965\', \'region\': ' \
                              '\'\\xd0\\x94\\xd0\\xbe\\xd0\\xbd\\xd0\\xb5\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xb0 ' \
                              '\\xd0\\xbe\\xd0\\xb1\\xd0\\xbb\\xd0\\xb0\\xd1\\x81\\xd1\\x82\\xd1\\x8c\', ' \
                              '\'locality\': \'Donetsk\'}}]}]}}'

    assert log_strings[-2] == 'Making request to api with params {\'url\': ' \
                              '\'http://127.0.0.1:6543/api/2.3/auctions/UA-11111/auction\', \'data\': {\'data\': {' \
                              '\'bids\': [{\'date\': \'2014-11-19T08:22:21.726234+00:00\', ' \
                              '\'id\': \'c26d9eed99624c338ce0fca58a0aac32\', \'value\': {\'currency\': None, ' \
                              '\'amount\': 0, \'valueAddedTaxIncluded\': True}, \'tenderers\': [{\'contactPoint\': {' \
                              '\'email\': \'automation+4077486456@smartweb.com.ua\', \'name\': ' \
                              '\'\\xd0\\xad\\xd0\\xbc\\xd0\\xbc\\xd0\\xb0\\xd0\\xbd\\xd1\\x83\\xd0\\xb8\\xd0\\xbb ' \
                              '\\xd0\\x9a\\xd0\\xb0\\xd0\\xbf\\xd1\\x83\\xd1\\x81\\xd1\\x82\\xd0\\xb8\\xd0\\xbd\\xd0' \
                              '\\xb0\', \'telephone\': \'+380139815286\'}, \'identifier\': {\'scheme\': \'UA-EDR\', ' \
                              '\'id\': \'46171\', \'uri\': \'http://9665642342.promtest.ua\', \'legalName\': ' \
                              '\'\\xd0\\xa4\\xd0\\xbe\\xd0\\xbc\\xd0\\xb8\\xd0\\xbd-\\xd0\\x90\\xd0\\xbb\\xd0\\xb5' \
                              '\\xd0\\xba\\xd1\\x81\\xd0\\xb0\\xd0\\xbd\\xd0\\xb4\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0' \
                              '\\xb0\'}, \'name\': ' \
                              '"\\xd0\\x9a\\xd0\\xbe\\xd0\\xbd\\xd1\\x86\\xd0\\xb5\\xd1\\x80\\xd1\\x82\\xd0\\xbd\\xd0' \
                              '\\xb8\\xd0\\xb9 \\xd0\\xb7\\xd0\\xb0\\xd0\\xba\\xd0\\xbb\\xd0\\xb0\\xd0\\xb4 ' \
                              '\\xd0\\xba\\xd1\\x83\\xd0\\xbb\\xd1\\x8c\\xd1\\x82\\xd1\\x83\\xd1\\x80\\xd0\\xb8 ' \
                              '\'\\xd0\\x9c\\xd1\\x83\\xd0\\xbd\\xd1\\x96\\xd1\\x86\\xd0\\xb8\\xd0\\xbf\\xd0\\xb0' \
                              '\\xd0\\xbb\\xd1\\x8c\\xd0\\xbd\\xd0\\xb0 ' \
                              '\\xd0\\xb0\\xd0\\xba\\xd0\\xb0\\xd0\\xb4\\xd0\\xb5\\xd0\\xbc\\xd1\\x96\\xd1\\x87\\xd0' \
                              '\\xbd\\xd0\\xb0 ' \
                              '\\xd1\\x87\\xd0\\xbe\\xd0\\xbb\\xd0\\xbe\\xd0\\xb2\\xd1\\x96\\xd1\\x87\\xd0\\xb0 ' \
                              '\\xd1\\x85\\xd0\\xbe\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0\\xb0 ' \
                              '\\xd0\\xba\\xd0\\xb0\\xd0\\xbf\\xd0\\xb5\\xd0\\xbb\\xd0\\xb0 \\xd1\\x96\\xd0\\xbc. ' \
                              '\\xd0\\x9b.\\xd0\\x9c. ' \
                              '\\xd0\\xa0\\xd0\\xb5\\xd0\\xb2\\xd1\\x83\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xbe\\xd0' \
                              '\\xb3\\xd0\\xbe\'", \'address\': {\'postalCode\': \'849999\', \'countryName\': ' \
                              '\'\\xd0\\xa3\\xd0\\xba\\xd1\\x80\\xd0\\xb0\\xd1\\x97\\xd0\\xbd\\xd0\\xb0\', ' \
                              '\'streetAddress\': \'6973 ' \
                              '\\xd0\\x90\\xd1\\x84\\xd0\\xb0\\xd0\\xbd\\xd0\\xb0\\xd1\\x81\\xd1\\x8c\\xd0\\xb5\\xd0' \
                              '\\xb2\\xd0\\xb0 Mountain Apt. 965\', \'region\': ' \
                              '\'\\xd0\\x94\\xd0\\xbe\\xd0\\xbd\\xd0\\xb5\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xb0 ' \
                              '\\xd0\\xbe\\xd0\\xb1\\xd0\\xbb\\xd0\\xb0\\xd1\\x81\\xd1\\x82\\xd1\\x8c\', ' \
                              '\'locality\': \'Donetsk\'}}]}, {\'date\': \'2014-11-19T12:00:00+00:00\', ' \
                              '\'id\': \'e4456d02263441ffb2f00ceafa661bb2\', \'value\': {\'currency\': \'UAH\', ' \
                              '\'amount\': \'amount from auction_doucument["results"]\', \'valueAddedTaxIncluded\': ' \
                              'True}, \'tenderers\': [{\'contactPoint\': {\'email\': ' \
                              '\'automation+4077486456@smartweb.com.ua\', \'name\': ' \
                              '\'\\xd0\\xad\\xd0\\xbc\\xd0\\xbc\\xd0\\xb0\\xd0\\xbd\\xd1\\x83\\xd0\\xb8\\xd0\\xbb ' \
                              '\\xd0\\x9a\\xd0\\xb0\\xd0\\xbf\\xd1\\x83\\xd1\\x81\\xd1\\x82\\xd0\\xb8\\xd0\\xbd\\xd0' \
                              '\\xb0\', \'telephone\': \'+380139815286\'}, \'identifier\': {\'scheme\': \'UA-EDR\', ' \
                              '\'id\': \'46171\', \'uri\': \'http://9665642342.promtest.ua\', \'legalName\': ' \
                              '\'\\xd0\\xa4\\xd0\\xbe\\xd0\\xbc\\xd0\\xb8\\xd0\\xbd-\\xd0\\x90\\xd0\\xbb\\xd0\\xb5' \
                              '\\xd0\\xba\\xd1\\x81\\xd0\\xb0\\xd0\\xbd\\xd0\\xb4\\xd1\\x80\\xd0\\xbe\\xd0\\xb2\\xd0' \
                              '\\xb0\'}, \'name\': ' \
                              '"\\xd0\\x9a\\xd0\\x9e\\xd0\\x9c\\xd0\\xa3\\xd0\\x9d\\xd0\\x90\\xd0\\x9b\\xd0\\xac\\xd0' \
                              '\\x9d\\xd0\\x95 ' \
                              '\\xd0\\x9f\\xd0\\x86\\xd0\\x94\\xd0\\x9f\\xd0\\xa0\\xd0\\x98\\xd0\\x84\\xd0\\x9c\\xd0' \
                              '\\xa1\\xd0\\xa2\\xd0\\x92\\xd0\\x9e ' \
                              '\'\\xd0\\x9a\\xd0\\x98\\xd0\\x87\\xd0\\x92\\xd0\\x9f\\xd0\\x90\\xd0\\xa1\\xd0\\xa2' \
                              '\\xd0\\xa0\\xd0\\x90\\xd0\\x9d\\xd0\\xa1\'", \'address\': {\'postalCode\': \'849999\', ' \
                              '\'countryName\': ' \
                              '\'\\xd0\\xa3\\xd0\\xba\\xd1\\x80\\xd0\\xb0\\xd1\\x97\\xd0\\xbd\\xd0\\xb0\', ' \
                              '\'streetAddress\': \'6973 ' \
                              '\\xd0\\x90\\xd1\\x84\\xd0\\xb0\\xd0\\xbd\\xd0\\xb0\\xd1\\x81\\xd1\\x8c\\xd0\\xb5\\xd0' \
                              '\\xb2\\xd0\\xb0 Mountain Apt. 965\', \'region\': ' \
                              '\'\\xd0\\x94\\xd0\\xbe\\xd0\\xbd\\xd0\\xb5\\xd1\\x86\\xd1\\x8c\\xd0\\xba\\xd0\\xb0 ' \
                              '\\xd0\\xbe\\xd0\\xb1\\xd0\\xbb\\xd0\\xb0\\xd1\\x81\\xd1\\x82\\xd1\\x8c\', ' \
                              '\'locality\': \'Donetsk\'}}]}]}}, \'method\': \'post\'}'

    bids_data = {'data': {'bids': [
        {'date': '2014-11-19T08:22:21.726234+00:00',
         'id': 'c26d9eed99624c338ce0fca58a0aac32',
         'tenderers': [{'address': {'countryName': '\xd0\xa3\xd0\xba\xd1\x80\xd0\xb0\xd1\x97\xd0\xbd\xd0\xb0',
                                    'locality': 'Donetsk',
                                    'postalCode': '849999',
                                    'region': '\xd0\x94\xd0\xbe\xd0\xbd\xd0\xb5\xd1\x86\xd1\x8c\xd0\xba\xd0\xb0 \xd0\xbe\xd0\xb1\xd0\xbb\xd0\xb0\xd1\x81\xd1\x82\xd1\x8c',
                                    'streetAddress': '6973 \xd0\x90\xd1\x84\xd0\xb0\xd0\xbd\xd0\xb0\xd1\x81\xd1\x8c\xd0\xb5\xd0\xb2\xd0\xb0 Mountain Apt. 965'},
                        'contactPoint': {'email': 'automation+4077486456@smartweb.com.ua',
                                         'name': '\xd0\xad\xd0\xbc\xd0\xbc\xd0\xb0\xd0\xbd\xd1\x83\xd0\xb8\xd0\xbb \xd0\x9a\xd0\xb0\xd0\xbf\xd1\x83\xd1\x81\xd1\x82\xd0\xb8\xd0\xbd\xd0\xb0',
                                         'telephone': '+380139815286'},
                        'identifier': {'id': '46171',
                                       'legalName': '\xd0\xa4\xd0\xbe\xd0\xbc\xd0\xb8\xd0\xbd-\xd0\x90\xd0\xbb\xd0\xb5\xd0\xba\xd1\x81\xd0\xb0\xd0\xbd\xd0\xb4\xd1\x80\xd0\xbe\xd0\xb2\xd0\xb0',
                                       'scheme': 'UA-EDR',
                                       'uri': 'http://9665642342.promtest.ua'},
                        'name': "\xd0\x9a\xd0\xbe\xd0\xbd\xd1\x86\xd0\xb5\xd1\x80\xd1\x82\xd0\xbd\xd0\xb8\xd0\xb9 \xd0\xb7\xd0\xb0\xd0\xba\xd0\xbb\xd0\xb0\xd0\xb4 \xd0\xba\xd1\x83\xd0\xbb\xd1\x8c\xd1\x82\xd1\x83\xd1\x80\xd0\xb8 '\xd0\x9c\xd1\x83\xd0\xbd\xd1\x96\xd1\x86\xd0\xb8\xd0\xbf\xd0\xb0\xd0\xbb\xd1\x8c\xd0\xbd\xd0\xb0 \xd0\xb0\xd0\xba\xd0\xb0\xd0\xb4\xd0\xb5\xd0\xbc\xd1\x96\xd1\x87\xd0\xbd\xd0\xb0 \xd1\x87\xd0\xbe\xd0\xbb\xd0\xbe\xd0\xb2\xd1\x96\xd1\x87\xd0\xb0 \xd1\x85\xd0\xbe\xd1\x80\xd0\xbe\xd0\xb2\xd0\xb0 \xd0\xba\xd0\xb0\xd0\xbf\xd0\xb5\xd0\xbb\xd0\xb0 \xd1\x96\xd0\xbc. \xd0\x9b.\xd0\x9c. \xd0\xa0\xd0\xb5\xd0\xb2\xd1\x83\xd1\x86\xd1\x8c\xd0\xba\xd0\xbe\xd0\xb3\xd0\xbe'"}],
         'value': {'amount': 0,
                   'currency': None,
                   'valueAddedTaxIncluded': True}},
        {'date': '2014-11-19T12:00:00+00:00',
         'id': 'e4456d02263441ffb2f00ceafa661bb2',
         'tenderers': [{'address': {'countryName': '\xd0\xa3\xd0\xba\xd1\x80\xd0\xb0\xd1\x97\xd0\xbd\xd0\xb0',
                                    'locality': 'Donetsk',
                                    'postalCode': '849999',
                                    'region': '\xd0\x94\xd0\xbe\xd0\xbd\xd0\xb5\xd1\x86\xd1\x8c\xd0\xba\xd0\xb0 \xd0\xbe\xd0\xb1\xd0\xbb\xd0\xb0\xd1\x81\xd1\x82\xd1\x8c',
                                    'streetAddress': '6973 \xd0\x90\xd1\x84\xd0\xb0\xd0\xbd\xd0\xb0\xd1\x81\xd1\x8c\xd0\xb5\xd0\xb2\xd0\xb0 Mountain Apt. 965'},
                        'contactPoint': {'email': 'automation+4077486456@smartweb.com.ua',
                                         'name': '\xd0\xad\xd0\xbc\xd0\xbc\xd0\xb0\xd0\xbd\xd1\x83\xd0\xb8\xd0\xbb \xd0\x9a\xd0\xb0\xd0\xbf\xd1\x83\xd1\x81\xd1\x82\xd0\xb8\xd0\xbd\xd0\xb0',
                                         'telephone': '+380139815286'},
                        'identifier': {'id': '46171',
                                       'legalName': '\xd0\xa4\xd0\xbe\xd0\xbc\xd0\xb8\xd0\xbd-\xd0\x90\xd0\xbb\xd0\xb5\xd0\xba\xd1\x81\xd0\xb0\xd0\xbd\xd0\xb4\xd1\x80\xd0\xbe\xd0\xb2\xd0\xb0',
                                       'scheme': 'UA-EDR',
                                       'uri': 'http://9665642342.promtest.ua'},
                        'name': "\xd0\x9a\xd0\x9e\xd0\x9c\xd0\xa3\xd0\x9d\xd0\x90\xd0\x9b\xd0\xac\xd0\x9d\xd0\x95 \xd0\x9f\xd0\x86\xd0\x94\xd0\x9f\xd0\xa0\xd0\x98\xd0\x84\xd0\x9c\xd0\xa1\xd0\xa2\xd0\x92\xd0\x9e '\xd0\x9a\xd0\x98\xd0\x87\xd0\x92\xd0\x9f\xd0\x90\xd0\xa1\xd0\xa2\xd0\xa0\xd0\x90\xd0\x9d\xd0\xa1'"}],
         'value': {'amount': 'amount from auction_doucument["results"]',
                   'currency': 'UAH',
                   'valueAddedTaxIncluded': True}}
    ]}}
    assert result == bids_data
    assert auction._auction_data["data"]["bids"][1]["value"]["amount"] == 'amount from auction_doucument["results"]'
    assert auction._auction_data["data"]["bids"][1]["date"] == '2014-11-19T12:00:00+00:00'


def test_update_auction_document(auction, mocker):
    mock_get_auction_document = mocker.patch.object(auction, 'get_auction_document', autospec=True)
    mock_save_auction_document = mocker.patch.object(auction, 'save_auction_document', autospec=True)

    auction.auction_document = {}
    with update_auction_document(auction):
        assert mock_get_auction_document.call_count == 1
        update_auction_document(auction)
        assert mock_save_auction_document.call_count == 0

    auction.auction_document = {'test_key': 'test_value'}
    with update_auction_document(auction):
        assert mock_get_auction_document.call_count == 2

    assert mock_save_auction_document.call_count == 1


def test_lock_bids(auction, mocker):
    # test_semaphore = BoundedSemaphore()
    # mock_bids_actions_acquire = mocker.patch.object(auction.bids_actions, 'acquire', autospec=True)
    # mock_bids_actions_release = mocker.patch.object(auction.release, 'release', autospec=True)

    # mock_bids_actions.acquire = test_semaphore.acquire
    # mock_bids_actions.release = test_semaphore.release

    # spied_acquire = mocker.spy(auction.bids_actions, 'acquire')
    # spied_release = mocker.spy(auction.bids_actions, 'release')

    with lock_bids(auction):
        pass

        # assert spied_acquire.call_count == 1
        # assert spied_release.call_count == 1

        # assert mock_bids_actions_acquire.call_count == 1
        # assert mock_bids_actions_release.call_count == 1

        # TODO: write proper asserts


@pytest.mark.parametrize('run_time', ['run_time_value', 12345, '12345', '2014-11-19T12:00:00+00:00'])
def test_update_stage(auction, mocker, run_time):
    auction.auction_document = {
        'initial_value': 'initial_value',
        'current_stage': 1,
        'stages': [
            {'test_key': 'test_value'},
            {'test_key': 'test_value'},
            {}
        ]
    }

    mock_datetime = mocker.MagicMock()
    mock_datetime.now = mocker.MagicMock()
    mock_datetime_now = mocker.MagicMock()
    mock_datetime.now.return_value = mock_datetime_now
    mock_isoformat = mocker.MagicMock()
    mock_datetime_now.isoformat = mock_isoformat
    mock_isoformat.return_value = run_time

    mocker.patch('openprocurement.auction.insider.utils.datetime', mock_datetime)

    result = update_stage(auction)

    assert result == run_time
    assert auction.auction_document['current_stage'] == 2
    assert auction.auction_document['stages'][2]['time'] == run_time

    mock_datetime.now.assert_called_once_with(tzlocal())
    assert mock_isoformat.call_count == 1


@pytest.mark.parametrize(
    'steps', [10, 20, 30, 40, 50, 60, 70, 80, 90, 99],
    ids=('10 steps', '20 steps', '30 steps', '40 steps', '50 steps',
         '60 steps', '70 steps', '80 steps', '90 steps', '99 steps')
)
def test_prepare_auction_document(auction, steps):
    with pytest.raises(AttributeError):
        prepare_auction_document(auction)

    tender_data_copy = deepcopy(tender_data)
    tender_data_copy['data']['title_ru'] = u'Описание Тендера'
    auction._auction_data = tender_data_copy

    auction.startDate = iso8601.parse_date('2014-11-19T12:00:00+00:00')
    auction.auction_document = {}

    auction._auction_data['data']['auctionParameters']['dutchSteps'] = steps
    auction.get_auction_info()
    assert auction.parameters['dutchSteps'] == steps

    dutch_rounds = auction.parameters['dutchSteps'] + 1
    dutch_step_duration = DUTCH_TIMEDELTA / dutch_rounds
    prepare_auction_document(auction)

    assert auction.auction_document['title'] == 'Tender Title'
    assert auction.auction_document['title_ru'] == u'Описание Тендера'
    assert auction.auction_document['description'] == 'Tender Description'

    auction.auction_document['stages'][0] = {
        "type": "pause",
        "start": "2014-11-19T12:00:00+00:00"
    }

    assert len(auction.auction_document['stages']) == dutch_rounds + 6

    # dutch phase final stage value
    assert auction.auction_document['stages'][1+steps]['amount'] == \
           Decimal(str(auction.auction_document['value']['amount'] -
                       auction.auction_document['value']['amount'] * 0.01 * steps))

    # dutch stages duration
    for index, stage in enumerate(auction.auction_document['stages']):
        if 1 < index <= dutch_rounds + 1:
            delta = iso8601.parse_date(stage['start']) - \
                    iso8601.parse_date(auction.auction_document['stages'][index - 1]['start'])
            assert delta == dutch_step_duration

    dutch_timedelta_fast_forward = timedelta(minutes=10)
    dutch_rounds_fast_forward = 10
    dutch_step_duration = dutch_timedelta_fast_forward / dutch_rounds_fast_forward

    prepare_auction_document(auction, fast_forward=True)

    assert auction.auction_document['title'] == 'Tender Title'
    assert auction.auction_document['title_ru'] == u'Описание Тендера'
    assert auction.auction_document['description'] == 'Tender Description'

    auction.auction_document['stages'][0] = {
        "type": "pause",
        "start": "2014-11-19T12:00:00+00:00"
    }

    assert len(auction.auction_document['stages']) == dutch_rounds_fast_forward + 6

    # dutch stages duration fast_forward
    for index, stage in enumerate(auction.auction_document['stages']):
        if 1 < index <= dutch_rounds_fast_forward + 1:
            delta = iso8601.parse_date(stage['start']) - \
                    iso8601.parse_date(auction.auction_document['stages'][index - 1]['start'])
            assert delta == dutch_step_duration == timedelta(0, 60)


def test_prepare_auction_document_100_steps(auction):
    tender_data_copy = deepcopy(tender_data)
    tender_data_copy['data']['title_ru'] = u'Описание Тендера'
    auction._auction_data = tender_data_copy

    auction.startDate = iso8601.parse_date('2014-11-19T12:00:00+00:00')
    auction.auction_document = {}

    auction._auction_data['data']['auctionParameters']['dutchSteps'] = 100
    auction.get_auction_info()
    assert auction.parameters['dutchSteps'] == 100

    prepare_auction_document(auction)

    # dutch phase final stage value
    assert auction.auction_document['stages'][101]['amount'] == Decimal('1.00')


@pytest.mark.parametrize(
    'submission_method_details, expected',
    [
        ('fastforward,dutch=1:6,sealedbid=3:32000/2:34567,bestbid=1:38254', {
            DUTCH: 'prepared_bid',
            SEALEDBID: 'prepared_bid',
            BESTBID: 'prepared_bid'
        }),
        ('fastforward,dutch=1:6,sealedbid=3:32000/2:34567', {
            DUTCH: 'prepared_bid',
            SEALEDBID: 'prepared_bid',
        }),
        ('fastforward,dutch=1:6', {
            DUTCH: 'prepared_bid',
        }),
        ('fastforward', {}),
    ], ids=('dutch sealedbid bestbid', 'dutch sealedbid', 'dutch', 'no bids')
)
def test_get_fast_forward_data(auction, mocker, submission_method_details, expected):
    mock_prepare_bid = mocker.patch('openprocurement.auction.insider.utils.prepare_bid', autospec=True)
    mock_prepare_bid.return_value = 'prepared_bid'
    result = get_fast_forward_data(auction, submission_method_details)
    assert result == expected


@pytest.mark.parametrize(
    'bid, phase, expected',
    [
        ('dutch=1:6', DUTCH, {
            'amount': Decimal(20000),
            'time': 'test-time',
            'bidder_id': 'bidder_id_1',
            'current_stage': 7
        }),
        ('sealedbid=3:32000/2:34567', SEALEDBID, [{
            'amount': Decimal(32000),
            'time': 'test-time',
            'bidder_id': 'bidder_id_3',
        },
        {
            'amount': Decimal(34567),
            'time': 'test-time',
            'bidder_id': 'bidder_id_2',
        }]),
        ('bestbid=1:38254', BESTBID, {
            'amount': Decimal(38254),
            'time': 'test-time',
            'bidder_id': 'bidder_id_1',
        }),

    ], ids=('dutch', 'sealedbid(2 bids)', 'bestbid')
)
def test_prepare_bid(auction, mocker, bid, phase, expected):
    auction.auction_document = {'stages': [{} for _ in range(16)]}
    auction.auction_document['stages'][7] = {
        'amount': Decimal(20000),
        'start': 'test-time'
    }
    auction.auction_document['stages'][12] = {
        'start': 'test-time'
    }
    auction.auction_document['stages'][14] = {
        'start': 'test-time'
    }
    auction.mapping = {'bidder_id_{}'.format(num): num for num in range(1, 4)}
    assert prepare_bid(auction, bid, phase) == expected


def test_update_stage_for_phase(auction):
    phases = (DUTCH, SEALEDBID, BESTBID)
    auction.auction_document = {
        'stages': [{} for _ in range(3)],
        'current_phase': None,
        'current_stage': None
    }
    for i, phase in enumerate(phases):
        auction.auction_document['stages'][i] = {
            'type': phase,
            'start': 'test-time'
        }

    for i, phase in enumerate(phases):
        update_stage_for_phase(auction, phase)
        assert auction.auction_document['current_stage'] == i
        assert auction.auction_document['current_phase'] == phase
        assert auction.auction_document['stages'][i]['time'] == 'test-time'


def test_run_auction_fast_forward(auction, mocker):
    mocker.patch.object(auction, 'generate_request_id', autospec=True)
    mock_get_auction_document = mocker.patch.object(auction, 'get_auction_document', autospec=True)
    mock_get_auction_document.return_value = True
    mocker.patch.object(auction, 'save_auction_document', autospec=True)
    mocker.patch.object(auction, 'get_auction_info', autospec=True)
    mock_get_auction_document.return_value = {'_rev': 'test_rev'}
    auction.startDate = datetime(2017, 12, 12)

    # sandbox_mode == True
    auction.prepare_auction_document()
    auction.mapping = {'bidder_id_{}'.format(num): num for num in range(1, 4)}

    ff_data = get_fast_forward_data(auction, 'fastforward,dutch=1:6,sealedbid=3:32000/2:34567,bestbid=1:38254')
    run_auction_fast_forward(auction, ff_data)

    assert auction.auction_document['current_stage'] == 15
    assert 'dutch_winner' in auction.auction_document['stages'][7]
    assert 'sealedbid_winner' in auction.auction_document['stages'][12]
    assert auction.auction_document['stages'][12]['amount'] == Decimal('34567')
    assert auction.auction_document['submissionMethodDetails'] == 'fastforward'
