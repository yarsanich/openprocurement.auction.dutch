# -*- coding: utf-8 -*-
import datetime
import dateutil.parser

from openprocurement.auction.insider.constants import DUTCH


def test_end_stage(auction, logger, mocker):
    auction.audit = {
        'timeline':
            {
                DUTCH: {
                    'timeline': {}
                }
            }
    }

    mock_update_stage = mocker.MagicMock()
    mock_update_stage.return_value = 'run_time_value'
    mocker.patch('openprocurement.auction.insider.mixins.utils.update_stage', mock_update_stage)

    mock_lock_bids = mocker.MagicMock()
    mock_update_auction_document = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.utils.lock_bids', mock_lock_bids)
    mocker.patch('openprocurement.auction.insider.mixins.utils.update_auction_document', mock_update_auction_document)

    stage = {
        'amount': 500000.0,
        'start': '2017-12-12T00:00:30',
        'time': '',
        'type': 'dutch_0'
    }

    auction.auction_document = {
        'initial_value': 'initial_value',
        'current_stage': 1,
        'stages': [
            {'test_key': 'test_value'},
            {'test_key': 'test_value'}
        ]
    }

    auction.next_stage(stage)
    log_strings = logger.log_capture_string.getvalue().split('\n')

    mock_lock_bids.assert_called_once_with(auction)
    mock_update_auction_document.assert_called_once_with(auction)
    mock_update_stage.assert_called_once_with(auction)
    assert auction.auction_document['stages'][0]['passed'] is True
    assert log_strings[-3] == '---------------- SWITCH DUTCH VALUE ----------------'
    assert auction.auction_document['stages'][1]['time'] == 'run_time_value'
    assert auction.auction_document['current_phase'] == DUTCH
    assert auction.audit['timeline'][DUTCH]['timeline']['start'] == 'run_time_value'
    assert log_strings[-2] == 'Switched dutch phase value from initial_value to 500000.0'
    assert auction.audit['timeline'][DUTCH]['turn_1'] == {
        'amount': 500000.0,
        'time': 'run_time_value'
    }

    stage['type'] = 'not_dutch_type'
    mock_end_dutch = mocker.patch.object(auction, 'end_dutch', autospec=True)
    auction.auction_document['stages'][0]['passed'] = False
    auction.next_stage(stage)

    assert mock_lock_bids.call_count == 2
    assert mock_update_auction_document.call_count == 2
    assert mock_update_stage.call_count == 2
    assert mock_end_dutch.call_count == 1
    assert auction.auction_document['stages'][0]['passed'] is True


def test_approve_dutch_winner(auction, logger, mocker):
    auction.audit = {
        'timeline':
            {
                DUTCH: {
                    'bids': []
                }
            }
    }

    auction.auction_document = {
        'initial_value': 'initial_value',
        'current_stage': 1,
        'stages': [
            {'test_key': 'test_value'},
            {'test_key': 'test_value'}
        ]
    }

    bid = {'bidder_id': 'test_bidder_id'}

    result_bid = auction.approve_dutch_winner(bid)

    assert result_bid == {
        'bidder_id': 'test_bidder_id',
        'dutch_winner': True
    }

    assert len(auction.audit['timeline'][DUTCH]['bids']) == 1
    assert auction.audit['timeline'][DUTCH]['bids'][0] == result_bid
    assert auction._bids_data['test_bidder_id'][0] == result_bid

    result = auction.approve_dutch_winner('bid')
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert result is False
    assert log_strings[-2] == "Unable to post dutch winner. Error: 'str' object does not support item assignment"


def test_add_dutch_winner(auction, logger, mocker):
    auction.audit = {
        'timeline':
            {
                DUTCH: {
                    'bids': []
                }
            }
    }

    mock_update_auction_document = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.utils.update_auction_document', mock_update_auction_document)

    auction.mapping['test_bidder_id'] = 'test_bid'
    auction.request_id = 'auction_request_id'

    auction.auction_document = {
        'initial_value': 'initial_value',
        'current_stage': 1,
        'stages': [
            {'test_key': 'test_value'},
            {'test_key': 'test_value'}
        ],
        'results': []
    }

    bid = {'bidder_id': 'test_bidder_id',
           'current_stage': 1}

    mock_prepare_results_stage = mocker.MagicMock()
    mock_prepare_results_stage.return_value = {
        'stage_results': 'result_from_prepare_results_stage'
    }
    mocker.patch('openprocurement.auction.insider.mixins.utils.prepare_results_stage', mock_prepare_results_stage)
    mock_end_dutch = mocker.patch.object(auction, 'end_dutch', autospec=True)

    spied_approve_dutch_winner = mocker.spy(auction, 'approve_dutch_winner')

    result = auction.add_dutch_winner(bid)
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert log_strings[-3] == '---------------- Adding dutch winner  ----------------'
    spied_approve_dutch_winner.assert_called_once_with(bid)
    mock_prepare_results_stage.assert_called_once_with(
        **{
            'bidder_name': 'test_bid',
            'bidder_id': 'test_bidder_id',
            'dutch_winner': True
        }
    )
    assert auction.auction_document['stages'][auction.auction_document['current_stage']]['stage_results'] == \
        'result_from_prepare_results_stage'
    assert len(auction.auction_document['results']) == 1
    assert auction.auction_document['results'][0] == {'stage_results': 'result_from_prepare_results_stage'}
    assert log_strings[-2] == 'Approved dutch winner'
    assert mock_end_dutch.call_count == 1
    assert result is True

    auction.mapping = None
    result = auction.add_dutch_winner(bid)
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert log_strings[-3] == '---------------- Adding dutch winner  ----------------'
    assert log_strings[-2] == "Exception during initialization dutch winner. Error: 'NoneType' object has no attribute 'get'"
    assert isinstance(result, AttributeError)


def test_end_dutch(auction, logger, mocker):

    auction.audit = {
        'timeline':
            {
                DUTCH: {
                    'timeline': {},
                    'bids': []
                }
            }
    }

    auction.auction_document = {
        'initial_value': 'initial_value',
        'current_stage': 1,
        'stages': [
            {
                'test_key': 'test_value',
                'type': 'dutch_0'
            },
            {
                'test_key': 'test_value',
                'type': 'dutch_1'
            },
            {
                'test_key': 'test_value',
                'type': 'pre-sealedbid'
            }
        ],
        'results': []
    }

    mock_spawn = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.spawn', mock_spawn)

    mock_end_auction = mocker.patch.object(auction, 'end_auction', autospec=True)

    result = auction.end_dutch()
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert log_strings[-3] == '---------------- End dutch phase ----------------'
    assert isinstance(dateutil.parser.parse(auction.audit['timeline'][DUTCH]['timeline']['end']), datetime.datetime)
    assert len(auction.auction_document['stages'][1]) == 3
    assert auction.auction_document['stages'][1]['passed'] is True
    mock_spawn.assert_called_once_with(auction.clean_up_preplanned_jobs)
    assert log_strings[-2] == "No bids on dutch phase. End auction now."
    assert mock_end_auction.call_count == 1
    assert result is None

    auction.auction_document['results'].append({'test_key': 'test_value'})
    auction.end_dutch()
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert log_strings[-2] == '---------------- End dutch phase ----------------'
    assert isinstance(dateutil.parser.parse(auction.audit['timeline'][DUTCH]['timeline']['end']), datetime.datetime)
    assert len(auction.auction_document['stages'][1]) == 3
    assert auction.auction_document['stages'][1]['passed'] is True
    assert mock_spawn.call_count == 2

    assert auction.auction_document['current_phase'] == 'pre-sealedbid'
    assert auction.auction_document['current_stage'] == 2
