# -*- coding: utf-8 -*-
from gevent.queue import Queue
from gevent.event import Event

import pytest

from openprocurement.auction.insider.constants import SEALEDBID, PREBESTBID


def test_add_bid(auction, logger, mocker):
    auction.bids_queue = Queue()
    auction._end_sealedbid = Event()

    mock_bids_queue = mocker.patch.object(auction, 'bids_queue', autospec=True)
    mock_end_sealedbid = mocker.patch.object(auction, '_end_sealedbid', autospec=True)

    mock_bids_queue.empty.side_effect = (_ for _ in range(4))
    mock_end_sealedbid.is_set.side_effect = [False, False, True]

    mock_bids_queue.get.return_value = {  # TODO: change to side_effect!!!!
        'bidder_id': 'test_bid_id',
        'amount': 440000.0,
        'time': 'test_time_value'
    }

    auction.audit = {
        'timeline':
            {
                SEALEDBID: {
                    'timeline': {},
                    'bids': []
                }
            }
    }

    mock_sleep = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.sleep', mock_sleep)

    auction.add_bid()
    log_strings = logger.log_capture_string.getvalue().split('\n')

    """
        ['Started bids worker',
         'Adding bid test_bid_id with value 440000.0 on test_time_value',
         'Adding bid test_bid_id with value 440000.0 on test_time_value',
         'Adding bid test_bid_id with value 440000.0 on test_time_value',
         'Bids queue done. Breaking worker',
         '']
    """

    assert log_strings[0] == 'Started bids worker'
    assert mock_bids_queue.get.call_count == 3
    assert log_strings[1:4] == [
        'Adding bid test_bid_id with value 440000.0 on test_time_value',
        'Adding bid test_bid_id with value 440000.0 on test_time_value',
        'Adding bid test_bid_id with value 440000.0 on test_time_value'
    ]
    assert mock_bids_queue.empty.call_count == 4
    assert mock_end_sealedbid.is_set.call_count == 3
    assert auction._bids_data == {
        'test_bid_id': [
            {'bidder_id': 'test_bid_id', 'amount': 440000.0, 'time': 'test_time_value'},
            {'bidder_id': 'test_bid_id', 'amount': 440000.0, 'time': 'test_time_value'},
            {'bidder_id': 'test_bid_id', 'amount': 440000.0, 'time': 'test_time_value'}
        ]
    }
    assert len(auction.audit['timeline'][SEALEDBID]['bids']) == 3
    assert auction.audit['timeline'][SEALEDBID]['bids'] == [
        {'bidder_id': 'test_bid_id', 'amount': 440000.0, 'time': 'test_time_value'},
        {'bidder_id': 'test_bid_id', 'amount': 440000.0, 'time': 'test_time_value'},
        {'bidder_id': 'test_bid_id', 'amount': 440000.0, 'time': 'test_time_value'}
    ]

    assert mock_sleep.call_count == 3
    assert mock_sleep.call_args_list[0][0] == (0.1,)
    assert mock_sleep.call_args_list[1][0] == (0.1,)
    assert mock_sleep.call_args_list[2][0] == (0.1,)
    assert log_strings[-2] == "Bids queue done. Breaking worker"

    mock_bids_queue.get.return_value['amount'] = -1
    mock_bids_queue.empty.side_effect = (_ for _ in range(4))
    mock_end_sealedbid.is_set.side_effect = [False, False, True]
    auction.add_bid()
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert log_strings[-9:-1] == [
        'Started bids worker',
        'Adding bid test_bid_id with value -1 on test_time_value',
        'Bid test_bid_id marked for cancellation on test_time_value',
        'Adding bid test_bid_id with value -1 on test_time_value',
        'Bid test_bid_id marked for cancellation on test_time_value',
        'Adding bid test_bid_id with value -1 on test_time_value',
        'Bid test_bid_id marked for cancellation on test_time_value',
        'Bids queue done. Breaking worker'
    ]
    assert mock_bids_queue.empty.call_count == 8
    assert mock_end_sealedbid.is_set.call_count == 6

    assert auction._bids_data == {
        'test_bid_id': [
            {'bidder_id': 'test_bid_id', 'amount': -1, 'time': 'test_time_value'},
            {'bidder_id': 'test_bid_id', 'amount': -1, 'time': 'test_time_value'},
            {'bidder_id': 'test_bid_id', 'amount': -1, 'time': 'test_time_value'},
            {'bidder_id': 'test_bid_id', 'amount': -1, 'time': 'test_time_value'},
            {'bidder_id': 'test_bid_id', 'amount': -1, 'time': 'test_time_value'},
            {'bidder_id': 'test_bid_id', 'amount': -1, 'time': 'test_time_value'}
        ]
    }

    assert len(auction.audit['timeline'][SEALEDBID]['bids']) == 6

    assert auction.audit['timeline'][SEALEDBID]['bids'] == [
        {'amount': -1, 'bidder_id': 'test_bid_id', 'time': 'test_time_value'},
        {'amount': -1, 'bidder_id': 'test_bid_id', 'time': 'test_time_value'},
        {'amount': -1, 'bidder_id': 'test_bid_id', 'time': 'test_time_value'},
        {'amount': -1, 'bidder_id': 'test_bid_id', 'time': 'test_time_value'},
        {'amount': -1, 'bidder_id': 'test_bid_id', 'time': 'test_time_value'},
        {'amount': -1, 'bidder_id': 'test_bid_id', 'time': 'test_time_value'}
    ]

    assert mock_sleep.call_count == 6
    assert mock_sleep.call_args_list[3][0] == (0.1,)
    assert mock_sleep.call_args_list[4][0] == (0.1,)
    assert mock_sleep.call_args_list[5][0] == (0.1,)


def test_switch_to_sealedbid(auction, logger, mocker):
    mock_lock_bids = mocker.MagicMock()
    mock_update_auction_document = mocker.MagicMock()
    mock_update_stage = mocker.MagicMock()
    mock_update_stage.return_value = 'run_time_value'
    mock_spawn = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.utils.lock_bids', mock_lock_bids)
    mocker.patch('openprocurement.auction.insider.mixins.utils.update_auction_document', mock_update_auction_document)
    mocker.patch('openprocurement.auction.insider.mixins.utils.update_stage', mock_update_stage)
    mocker.patch('openprocurement.auction.insider.mixins.spawn', mock_spawn)

    auction.audit = {
        'timeline':
            {
                SEALEDBID: {
                    'timeline': {},
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

    auction.switch_to_sealedbid(2)
    log_strings = logger.log_capture_string.getvalue().split('\n')

    mock_update_auction_document.assert_called_once_with(auction)
    mock_lock_bids.assert_called_once_with(auction)
    assert isinstance(auction._end_sealedbid, Event)
    mock_update_stage.assert_called_once_with(auction)
    assert auction.auction_document['current_phase'] == SEALEDBID
    assert auction.audit['timeline'][SEALEDBID]['timeline']['start'] == 'run_time_value'
    mock_spawn.assert_called_once_with(auction.add_bid)
    assert log_strings[-2] == "Swithed auction to sealedbid phase"


@pytest.mark.parametrize("run_time", [15, 22, 42, 18, 'value'])
def test_approve_audit_info_on_sealedbid(auction, run_time):

    auction.audit = {
        'timeline':
            {
                SEALEDBID: {
                    'timeline': {},
                    'bids': []
                }
            }
    }

    auction.approve_audit_info_on_sealedbid(run_time)

    assert auction.audit['timeline'][SEALEDBID]['timeline']['end'] == run_time


def test_end_sealedbid(auction, mocker, logger):
    mock_update_auction_document = mocker.MagicMock()
    mock_sleep = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.utils.update_auction_document', mock_update_auction_document)
    mocker.patch('openprocurement.auction.insider.mixins.sleep', mock_sleep)

    auction._end_sealedbid = Event()
    mock_end_sealedbid = mocker.patch.object(auction, '_end_sealedbid', autospec=True)
    mock_end_sealedbid.set = mocker.MagicMock()

    auction.bids_queue = Queue()
    mock_bids_queue = mocker.patch.object(auction, 'bids_queue', autospec=True)
    mock_bids_queue.empty = mocker.MagicMock()
    mock_bids_queue.empty.side_effect = [False, True]

    auction._bids_data = {'test_bidder_id': [{
            'bidder_name': 'test_bid',
            'bidder_id': 'test_bidder_id',
            'time': 0,
            'amount': 450000.0,
            'dutch_winner': True}]
    }
    mock_end_auction = mocker.patch.object(auction, 'end_auction', autospec=True)

    # No bids on sealedbid phase
    result = auction.end_sealedbid(1)
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert result is None
    mock_update_auction_document.assert_called_once_with(auction)
    assert mock_end_sealedbid.set.call_count == 1
    assert mock_bids_queue.empty.call_count == 2
    assert log_strings[-4] == "Waiting for bids to process"
    mock_sleep.assert_called_once_with(0.1)
    assert log_strings[-3] == "Done processing bids queue"
    assert log_strings[-2] == "No bids on sealedbid phase. end auction"
    assert mock_end_auction.call_count == 1

    auction._bids_data.update({'test_bidder_id_2': [{
        'bidder_name': 'test_bid_2',
        'bidder_id': 'test_bidder_id_2',
        'time': 0,
        'amount': 500001.0}
    ]})

    auction._bids_data.update({'test_bidder_id_3': [{
        'bidder_name': 'test_bid_3',
        'bidder_id': 'test_bidder_id_3',
        'time': 0,
        'amount': 500000.0}
    ]})

    auction.auction_document = {
        'initial_value': 'initial_value',
        'current_stage': 1,
        'stages': [
            {'test_key': 'test_value'},
            {'test_key': 'test_value'}
        ]
    }

    auction.mapping['test_bidder_id'] = ['bidder_name_from_mapping']
    auction.mapping['test_bidder_id_2'] = ['bidder_name_from_mapping_2']
    auction.mapping['test_bidder_id_3'] = ['bidder_name_from_mapping_3']

    mock_bids_queue.empty.side_effect = [True, True]

    mock_update_stage = mocker.MagicMock()
    mock_update_stage.return_value = 'run_time_value'
    mocker.patch('openprocurement.auction.insider.mixins.utils.update_stage', mock_update_stage)
    mock_approve_audit_info_on_sealedbid = mocker.patch.object(auction, 'approve_audit_info_on_sealedbid', autospec=True)

    auction.end_sealedbid(1)
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert log_strings[-2] == "Done processing bids queue"
    assert auction.auction_document['current_phase'] == PREBESTBID

    assert len(auction.auction_document['stages']) == 2
    assert auction.auction_document['stages'][1]['amount'] == 500001.0
    assert auction.auction_document['stages'][1]['bidder_id'] == 'test_bidder_id_2'
    assert auction.auction_document['stages'][1]['label']['en'] == "Bidder #['bidder_name_from_mapping_2']"
    assert auction.auction_document['stages'][1]['sealedbid_winner'] is True
    assert auction.auction_document['stages'][1]['time'] == '0'

    assert len(auction.auction_document['results']) == 3
    assert auction.auction_document['results'][0]['amount'] == 450000.0
    assert auction.auction_document['results'][0]['bidder_id'] == 'test_bidder_id'
    assert auction.auction_document['results'][0]['dutch_winner'] is True
    assert auction.auction_document['results'][0]['label']['en'] == "Bidder #['bidder_name_from_mapping']"
    assert auction.auction_document['results'][1]['amount'] == 500000.0
    assert auction.auction_document['results'][1]['bidder_id'] == 'test_bidder_id_3'
    assert auction.auction_document['results'][1]['label']['en'] == "Bidder #['bidder_name_from_mapping_3']"
    assert auction.auction_document['results'][2]['amount'] == 500001.0
    assert auction.auction_document['results'][2]['bidder_id'] == 'test_bidder_id_2'
    assert auction.auction_document['results'][2]['label']['en'] == "Bidder #['bidder_name_from_mapping_2']"

    mock_update_stage.assert_called_once_with(auction)
    mock_approve_audit_info_on_sealedbid.assert_called_once_with('run_time_value')
