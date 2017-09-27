# -*- coding: utf-8 -*-
from collections import namedtuple
from decimal import Decimal

import pytest

from openprocurement.auction.insider.constants import DUTCH, SEALEDBID, BESTBID
from openprocurement.auction.insider.forms import form_handler


def test_default_data_required_validators(bids_form):
    valid = bids_form.validate()
    assert valid is False
    assert len(bids_form.errors) == 2
    assert ('bid', [u'Bid amount is required']) in bids_form.errors.items()
    assert ('bidder_id', [u'No bidder id']) in bids_form.errors.items()


def test_bid_value_validator_key_error(bids_form):
    with pytest.raises(KeyError) as e_info:
        bids_form.document['current_phase'] = DUTCH
        del bids_form.document['current_stage']
        bids_form.bid.data = 15.0
        bids_form.validate()

    assert e_info.type is KeyError
    assert e_info.value.message == 'current_stage'
    assert len(bids_form.errors) == 2
    assert ('bid', ['current_stage']) in bids_form.errors.items()


@pytest.mark.parametrize("phase,test_input,expected,dutch_winner", [
    (DUTCH, -0.5, "Passed value doesn't match current amount=350000", False),
    (DUTCH, 'some_value', "Passed value doesn't match current amount=350000", False),
    (DUTCH, 350001, "Passed value doesn't match current amount=350000", False),
    (SEALEDBID, -0.5, u'Too low value', False),
    (SEALEDBID, 349999, u'Bid value can\'t be less or equal current amount', True),
    (BESTBID, 349999, u'Bid value can\'t be less or equal current amount', True),
    ('invalid_phase', 350000, u'Not allowed to post bid on current (invalid_phase) phase', False),
])
def test_bid_value_validator_fail(bids_form, phase, test_input, expected, dutch_winner):
    if dutch_winner:
        bids_form.document['results'] = [
            {'dutch_winner': True, "bidder_id": "dutch_winner_id", "amount": 350000}
        ]
    current_stage = bids_form.document['current_stage']
    bids_form.document['stages'][current_stage]['amount'] = 350000
    bids_form.document['current_phase'] = phase
    bids_form.bid.data = test_input
    valid = bids_form.validate()
    assert valid is False
    assert len(bids_form.errors) == 2
    assert ('bid', [expected]) in bids_form.errors.items()


@pytest.mark.parametrize("stage,test_input,dutch_winner", [
    (DUTCH, 350000, False),
    (SEALEDBID, 350001, True),
    (BESTBID, 350001, True)
])
def test_bid_value_validator_success(bids_form, stage, test_input, dutch_winner):
    if dutch_winner:
        bids_form.document['results'] = [
            {'dutch_winner': True, "bidder_id": "dutch_winner_id", "amount": test_input}
        ]
        test_input += 1
    current_stage = bids_form.document['current_stage']
    bids_form.document['stages'][current_stage]['amount'] = 350000
    bids_form.document['current_phase'] = stage
    bids_form.bid.data = test_input
    valid = bids_form.validate()
    assert valid is False
    assert len(bids_form.errors) == 1
    assert [('bidder_id', ["No bidder id"])] == bids_form.errors.items()


@pytest.mark.parametrize("phase, field_data, expected", [
    (BESTBID,
     "dutch_winner_id", {
        "errors_count": 1,
        "extra_errors": None
     }),
    (BESTBID,
     "not_dutch_winner_id", {
        "errors_count": 2,
        "extra_errors": ('bidder_id', [u'bidder_id don\'t match with dutchWinner.bidder_id'])
     }),
    (SEALEDBID,
     "dutch_winner_id", {
        "errors_count": 2,
        "extra_errors": ('bidder_id', [u'Not allowed to post bid for dutch winner'])
     }),
    (SEALEDBID,
     "not_dutch_winner_id", {
        "errors_count": 1,
        "extra_errors": None
     }),
    (DUTCH,
     "some_random_id", {
         "errors_count": 1,
         "extra_errors": None
     }),
    (DUTCH,
     12345, {
         "errors_count": 1,
         "extra_errors": None
     }),
    ('invalid_phase',
     'some_random_id', {
         "errors_count": 2,
         "extra_errors": ('bidder_id', ['Not allowed to post bid on current (invalid_phase) phase'])
     })
])
def test_bidder_id_validator(bids_form, phase, field_data, expected):
    bids_form.document['current_phase'] = phase
    bids_form.document['results'] = [{'dutch_winner': True, "bidder_id": "dutch_winner_id"}]
    bids_form.bidder_id.data = field_data
    valid = bids_form.validate()
    assert valid is False
    assert len(bids_form.errors) == expected['errors_count']
    assert ('bid', [u'Bid amount is required']) in bids_form.errors.items()
    if expected['extra_errors']:
        assert expected['extra_errors'] in bids_form.errors.items()


def test_bidder_id_validator_dutch_winner_id_not_in_document(bids_form):
    bids_form.document['current_phase'] = BESTBID
    bids_form.document['results'] = [{'dutch_winner': True}]  # No 'bidder_id' key
    with pytest.raises(KeyError) as e_info:
        bids_form.bidder_id.data = 'some_id'
        bids_form.validate()

    assert e_info.type is KeyError
    assert e_info.value.message == 'bidder_id'
    assert len(bids_form.errors) == 1
    assert 'bidder_id' in bids_form.errors.items()[0]


def test_form_handler(app, auction, mocker, logger, db):
    Request = namedtuple('Request', 'json headers')
    json = {
        'bid': 350000,
        'bidder_id': 'some_id',
    }
    request = Request(json=json, headers={})
    auction.prepare_auction_document()
    mocker.patch('openprocurement.auction.insider.forms.app', app)
    mocker.patch('openprocurement.auction.insider.forms.request', request)
    mocker.patch('openprocurement.auction.insider.forms.session', {'client_id': 'client_id'})

    # Invalid auction phase

    auction.auction_document['current_phase'] = 'invalid_phase'
    app.config['auction'] = auction
    result = form_handler()
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert result['status'] == 'failed'
    assert len(result['errors']) == 2
    assert result['errors']['bid'] == ['Not allowed to post bid on current (invalid_phase) phase']
    assert result['errors']['bidder_id'] == ['Not allowed to post bid on current (invalid_phase) phase']
    assert "Bidder some_id with client_id client_id wants place bid 350000 in" in log_strings[-2]
    # Skipping assert of logging time
    assert "on phase invalid_phase with errors " in log_strings[-2]
    assert "{'bid': ['Not allowed to post bid on current (invalid_phase) phase']," in log_strings[-2]
    assert "'bidder_id': ['Not allowed to post bid on current (invalid_phase) phase']" in log_strings[-2]

    # Successful bid post during dutch phase

    auction.auction_document['current_phase'] = DUTCH
    auction.auction_document['stages'][-1]['amount'] = 350000
    app.config['auction'] = auction
    result = form_handler()
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert result['status'] == 'ok'
    assert len(result['data']) == 2
    assert isinstance(result['data']['bid'], Decimal)
    assert result['data']['bid'] == 350000
    assert result['data']['bidder_id'] == 'some_id'
    assert log_strings[-2] == 'Bidder some_id with client client_id has won dutch on value 350000'

    # Failed bid post during dutch phase

    mocked_add_dutch_winner = mocker.patch.object(auction, 'add_dutch_winner', autospec=True)
    mocked_add_dutch_winner.return_value = Exception('unexpected exception, tho')
    app.config['auction'] = auction

    result = form_handler()
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert result['status'] == 'failed'
    assert len(result['errors']) == 1
    assert result['errors'] == ["Exception('unexpected exception, tho',)"]
    assert 'Bidder some_id with client_id client_id wants place bid 350000 in ' in log_strings[-2]
    # Skipping assert of logging time
    assert " on dutch with errors Exception('unexpected exception, tho',)" in log_strings[-2]

    # Successful bid post during sealedbid phase

    auction.auction_document['current_phase'] = SEALEDBID
    auction.auction_document['results'] = [
        {'dutch_winner': True, "bidder_id": "dutch_winner_id", "amount": 35000}
    ]
    app.config['auction'] = auction
    json = {
        'bid': 350001,
        'bidder_id': 'some_id',
    }
    request = Request(json=json, headers={})
    mocker.patch('openprocurement.auction.insider.forms.request', request)

    result = form_handler()

    assert result['status'] == 'ok'
    assert len(result['data']) == 2
    assert isinstance(result['data']['bid'], Decimal)
    assert result['data']['bid'] == 350001
    assert result['data']['bidder_id'] == 'some_id'

    # Failed bid post during sealedbid phase

    mocked_bids_queue_put = mocker.patch.object(auction.bids_queue, 'put', autospec=True)
    mocked_bids_queue_put.side_effect = Exception('unexpected exception, tho')
    app.config['auction'] = auction

    result = form_handler()

    assert result['status'] == 'failed'
    assert len(result['errors']) == 1
    assert result['errors'] == ["Exception('unexpected exception, tho',)"]

    # Successful bid post during bestbid phase

    auction.auction_document['current_phase'] = BESTBID
    auction.audit = {'timeline': {BESTBID: {'bids': []}}}
    json = {
        'bid': 350001,
        'bidder_id': 'dutch_winner_id',
    }
    request = Request(json=json, headers={})
    mocker.patch('openprocurement.auction.insider.forms.request', request)

    result = form_handler()
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert result['status'] == 'ok'
    assert len(result['data']) == 2
    assert isinstance(result['data']['bid'], Decimal)
    assert result['data']['bid'] == 350001
    assert result['data']['bidder_id'] == 'dutch_winner_id'
    assert log_strings[-2] == 'Bidder dutch_winner_id with client client_id has won dutch on value 350001'

    # Failed bid post during bestbid phase

    mocked_add_bestbid = mocker.patch.object(auction, 'add_bestbid', autospec=True)
    mocked_add_bestbid.return_value = Exception('unexpected exception, tho')
    app.config['auction'] = auction

    result = form_handler()
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert result['status'] == 'failed'
    assert len(result['errors']) == 1
    assert result['errors'] == ["Exception('unexpected exception, tho',)"]
    assert 'Bidder dutch_winner_id with client_id client_id wants place bid 350001 in ' in log_strings[-2]
    # Skipping assert of logging time
    assert " on dutch with errors Exception('unexpected exception, tho',)" in log_strings[-2]

    # Bids period expired

    mocked_from_json = mocker.patch.object(app.bids_form, 'from_json', autospec=True)
    mocked_form = mocker.MagicMock()
    mocked_from_json.return_value = mocked_form
    mocked_form.validate.return_value = True

    auction.auction_document['current_phase'] = 'invalid_phase'
    app.config['auction'] = auction
    result = form_handler()

    assert result['status'] == 'failed'
    assert len(result['errors']) == 1
    assert result['errors']['form'] == ['Bids period expired.']
