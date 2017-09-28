# -*- coding: utf-8 -*-
import pytest

from openprocurement.auction.insider.constants import BESTBID


@pytest.mark.parametrize("id,amount,time", [
    ('test_id_1', 25.0, 12345679),
    (42, 650000.0, 'time_value'),
])
def test_approve_bid_on_bestbid(auction, logger, id, amount, time):

    result = auction.approve_bid_on_bestbid(bid=None)

    assert result is False

    bid = {
        "bidder_id": id,
        "amount": amount,
        "time": time
    }

    auction.audit = {
        'timeline':
            {
                BESTBID: {
                    'bids': []
                }
            }
    }

    result = auction.approve_bid_on_bestbid(bid=bid)
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert log_strings[-2] == "Updating dutch winner {0} with value {1} on {2}".format(
        id, amount, time
    )
    assert len(auction.audit['timeline'][BESTBID]['bids']) == 1
    assert auction.audit['timeline'][BESTBID]['bids'] == [{
        "bidder_id": id,
        "amount": amount,
        "time": time,
        "dutch_winner": True
    }]
    assert auction._bids_data[id] == [{
        "bidder_id": id,
        "amount": amount,
        "time": time,
        "dutch_winner": True
    }]
    assert result is True


@pytest.mark.parametrize('run_time', [125, '56', 'run_time_value', 45.567, '123,678'])
def test_approve_audit_info_on_bestbid(auction, run_time):

    auction.audit = {
        'timeline':
            {
                BESTBID: {
                    'timeline': {}
                }
            }
    }

    auction.approve_audit_info_on_bestbid(run_time)

    assert auction.audit['timeline'][BESTBID]['timeline']['end'] == run_time


@pytest.mark.parametrize("id,amount,time", [
    ('test_id_1', 25.0, 12345679),
    ('test_id_2', 250.0, '12345'),
    (42, 650000.0, 'time_value'),
])
def test_add_bestbid(auction, mocker, logger, id, amount, time):

    bid = {
        "bidder_id": id,
        "amount": amount,
        "time": time
    }

    mock_approve_bid_on_bestbid = mocker.patch.object(auction, 'approve_bid_on_bestbid', autospec=True)
    mock_approve_bid_on_bestbid.return_value = True

    result = auction.add_bestbid(bid)
    log_strings = logger.log_capture_string.getvalue().split('\n')

    assert log_strings[-2] == "Dutch winner id={0} placed bid {1} on {2}".format(
        id, amount, time
    )
    assert result is True

    mock_approve_bid_on_bestbid.return_value = False

    result = auction.add_bestbid(bid)

    assert result is False

    mock_approve_bid_on_bestbid.side_effect = Exception('Unexpected error.')
    with pytest.raises(Exception):
        result = auction.add_bestbid(bid)
        log_strings = logger.log_capture_string.getvalue().split('\n')
        assert log_strings[-2] == "Falied to update dutch winner. Error: Unexpected error."
        assert result is Exception('Unexpected error')


def test_switch_to_bestbid(auction, mocker):
    mock_lock_bids = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.utils.lock_bids', mock_lock_bids)
    mock_update_auction_document = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.utils.update_auction_document', mock_update_auction_document)
    mock_update_stage = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.utils.update_stage', mock_update_stage)
    mock_update_stage.return_value = 'run_time_value'

    auction.auction_document = {
        'initial_value': 'initial_value',
        'current_stage': 1,
        'stages': [
            {'test_key': 'test_value'},
            {'test_key': 'test_value'}
        ]
    }

    auction.audit = {
        'timeline':
            {
                BESTBID: {
                    'timeline': {}
                }
            }
    }

    auction.switch_to_bestbid(1)

    mock_lock_bids.asset_called_once_with(auction)
    mock_update_stage.asset_called_once_with(auction)

    assert auction.auction_document['current_phase'] == BESTBID
    mock_update_auction_document.asset_called_once_with(auction)
    assert auction.audit['timeline'][BESTBID]['timeline']['start'] == 'run_time_value'


def test_end_bestbid(auction, mocker):

    mock_update_auction_document = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.utils.update_auction_document', mock_update_auction_document)

    mock_update_stage = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.utils.update_stage', mock_update_stage)
    mock_update_stage.return_value = 'run_time_value'

    mock_approve_audit_info_on_bestbid = mocker.patch.object(auction, 'approve_audit_info_on_bestbid' ,autospec=True)

    mock_end_auction = mocker.patch.object(auction, 'end_auction', autospec=True)

    auction.mapping['test_bidder_id'] = ['bidder_name_from_mapping']
    auction.mapping['test_bidder_id_2'] = ['bidder_name_from_mapping_2']

    auction.auction_document = {
        'initial_value': 'initial_value',
        'current_stage': 1,
        'stages': [
            {'test_key': 'test_value'},
            {'test_key': 'test_value'}
        ]
    }

    auction._bids_data = {
        'test_bidder_id': [{
            'bidder_id': 'test_bidder_id',
            'time': '',
            'amount': 450000.0,
        }],
        'test_bidder_id_2': [{
            'bidder_id': 'test_bidder_id_2',
            'time': '',
            'amount': 480000.0,
        }],
    }

    auction.end_bestbid(1)

    mock_update_auction_document.asset_called_once_with(auction)
    mock_approve_audit_info_on_bestbid.assert_called_once_with('run_time_value')
    mock_update_stage.assert_called_once_with(auction)

    assert len(auction.auction_document['results']) == 2
    assert auction.auction_document['results'][0]['amount'] == 450000.0
    assert auction.auction_document['results'][0]['bidder_id'] == "test_bidder_id"
    assert auction.auction_document['results'][0]['label']['en'] == "Bidder #['bidder_name_from_mapping']"
    assert auction.auction_document['results'][1]['amount'] == 480000.0
    assert auction.auction_document['results'][1]['bidder_id'] == "test_bidder_id_2"
    assert auction.auction_document['results'][1]['label']['en'] == "Bidder #['bidder_name_from_mapping_2']"

    assert mock_end_auction.call_count == 1
