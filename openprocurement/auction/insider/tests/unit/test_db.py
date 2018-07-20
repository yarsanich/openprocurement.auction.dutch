import datetime
import pytest

from openprocurement.auction.insider.tests.data.data import tender_data


def test_get_auction_info(auction, logger, mocker):

    with pytest.raises(AttributeError):
        assert auction.startDate

    with pytest.raises(AttributeError):
        assert auction.auctionParameters

    auction.get_auction_info(prepare=False)

    assert isinstance(auction.startDate, datetime.datetime)
    assert isinstance(auction.parameters['dutchSteps'], int)
    assert isinstance(auction.parameters['type'], str)

    # test default auctionParameters values if such was not provided by API
    auction_parameters = auction._auction_data['data']['auctionParameters']
    del auction._auction_data['data']['auctionParameters']
    auction.parameters = None

    auction.get_auction_info(prepare=False)

    assert auction.parameters['dutchSteps'] == 80
    assert auction.parameters['type'] == 'insider'
    auction._auction_data['data']['auctionParameters'] = auction_parameters

    auction.debug = False
    mock_get_tender_data = mocker.MagicMock()
    mock_get_tender_data.return_value = {
        'data': {
            'updated_from_get_tender_data': True,
            'auctionPeriod': {
                'startDate': '2017-12-12'
            },
            'auctionParameters': {
                'type': 'insider',
                'dutchSteps': 80
            }
        }
    }
    mocker.patch('openprocurement.auction.insider.mixins.get_tender_data', mock_get_tender_data)
    auction.generate_request_id()
    auction.startDate = None
    auction.parameters = None

    auction.get_auction_info()

    assert isinstance(auction.startDate, datetime.datetime)
    assert isinstance(auction.parameters['dutchSteps'], int)
    assert isinstance(auction.parameters['type'], str)
    assert auction._auction_data['data']['updated_from_get_tender_data']
    mock_get_tender_data.assert_called_once_with(
        auction.tender_url + '/auction',
        user=auction.worker_defaults["resource_api_token"],
        request_id=auction.request_id,
        session=auction.session
    )

    mock_get_tender_data.side_effect = [{
        'data': {
            'updated_from_get_tender_data': True,
            'auctionPeriod': {
                'startDate': '2017-12-12'
            },
            'auctionParameters': {
                'type': 'dutch',
                'steps': 80
            }
        }
    }, None]
    auction.auction_document = None
    mock_sys_exit = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.sys.exit', mock_sys_exit)
    mock_end_auction_event = mocker.patch.object(auction, '_end_auction_event', autospec=True)
    mock_get_auction_document = mocker.patch.object(auction, 'get_auction_document', autospec=True)

    auction.get_auction_info(prepare=True)

    assert mock_get_tender_data.call_count == 3
    assert mock_get_tender_data.call_args_list[-2] == (
        (auction.tender_url, ),
        {
            'request_id': auction.request_id,
            'session': auction.session
        }
    )
    assert mock_get_tender_data.call_args_list[-1] == (
        (auction.tender_url + '/auction',),
        {
            'user': auction.worker_defaults["resource_api_token"],
            'request_id': auction.request_id,
            'session': auction.session
        }
    )
    assert mock_end_auction_event.set.call_count == 1
    assert mock_sys_exit.call_count == 1
    assert mock_get_auction_document.call_count == 1
    log_strings = logger.log_capture_string.getvalue().split('\n')
    assert log_strings[-2] == 'Auction UA-11111 not exists'

    mock_get_tender_data.side_effect = [{
        'data': {
            'updated_from_get_tender_data': True,
            'auctionPeriod': {
                'startDate': '2017-12-12'
            },
            'auctionParameters': {
                'type': 'dutch',
                'steps': 80
            }
        }
    }, None]
    mock_save_document = mocker.patch.object(auction, 'save_auction_document', autospec=True)
    auction.auction_document = {1: 1}

    auction.get_auction_info(prepare=True)

    assert mock_get_tender_data.call_count == 5
    assert mock_get_tender_data.call_args_list[-2] == (
        (auction.tender_url,),
        {
            'request_id': auction.request_id,
            'session': auction.session
        }
    )
    assert mock_get_tender_data.call_args_list[-1] == (
        (auction.tender_url + '/auction',),
        {
            'user': auction.worker_defaults["resource_api_token"],
            'request_id': auction.request_id,
            'session': auction.session
        }
    )
    assert mock_save_document.call_count == 1
    assert mock_get_auction_document.call_count == 2
    assert auction.auction_document['current_stage'] == -100
    log_strings = logger.log_capture_string.getvalue().split('\n')
    assert log_strings[-2] == 'Cancel auction: UA-11111'


def test_prepare_public_document(auction):

    with pytest.raises(AttributeError):
        auction.prepare_public_document()

    auction.auction_document = {}

    result = auction.prepare_public_document()
    assert result == {}

    auction.auction_document = {'test_key': 'test_value'}
    result = auction.prepare_public_document()
    assert result is not auction.auction_document
    assert result == auction.auction_document


def test_prepare_auction_document(auction, mocker):

    mock_generate_request_id = mocker.patch.object(auction, 'generate_request_id', autospec=True)
    mock_get_auction_document = mocker.patch.object(auction, 'get_auction_document', autospec=True)
    mock_get_auction_document.return_value = True
    mock_save_auction_document = mocker.patch.object(auction, 'save_auction_document', autospec=True)
    mock_get_auction_info = mocker.patch.object(auction, 'get_auction_info', autospec=True)
    mock_get_auction_document.return_value = {'_rev': 'test_rev'}
    auction.startDate = datetime.datetime(2017, 12, 12)

    # sandbox_mode == True
    auction.prepare_auction_document()

    assert auction.auction_document['_rev'] == 'test_rev'
    assert auction.auction_document['mode'] == 'test'
    assert auction.auction_document['test_auction_data'] == tender_data
    assert auction.auction_document['test_auction_data'] is not tender_data
    assert mock_generate_request_id.call_count == 1
    assert mock_get_auction_document.call_count == 1
    assert mock_save_auction_document.call_count == 1
    assert mock_get_auction_info.call_count == 1
    assert len(auction.auction_document['stages']) == 16
    assert auction.auction_document['current_stage'] == -1

    mock_get_fastforward_data = mocker.patch('openprocurement.auction.insider.utils.get_fast_forward_data')
    mock_run_auction_fast_forward = mocker.patch('openprocurement.auction.insider.utils.run_auction_fast_forward')
    mock_post_audit = mocker.patch.object(auction, 'post_audit', autospec=True)
    auction._auction_data['data']['submissionMethodDetails'] = 'fast-forward'
    auction._auction_data['data']['status'] = 'active.auction'

    auction.prepare_auction_document()

    assert mock_get_fastforward_data.call_count == 1
    assert mock_run_auction_fast_forward.call_count == 1
    assert mock_post_audit.call_count == 1

    del auction._auction_data['data']['submissionMethodDetails']
    auction.worker_defaults['sandbox_mode'] = False
    auction.parameters = auction.auction_document['test_auction_data']['data']['auctionParameters']
    auction.prepare_auction_document()

    assert auction.auction_document['_rev'] == 'test_rev'
    assert auction.auction_document['mode'] == 'test'
    assert auction.auction_document['test_auction_data'] == tender_data
    assert auction.auction_document['test_auction_data'] is not tender_data
    assert mock_generate_request_id.call_count == 3
    assert mock_get_auction_document.call_count == 3
    assert mock_get_auction_document.call_count == 3
    assert mock_save_auction_document.call_count == 3
    assert mock_get_auction_info.call_count == 3
    assert len(auction.auction_document['stages']) == 87

    # max dutch stages duration
    timedeltas = [auction.convert_datetime(auction.auction_document['stages'][i]['start']) -
                  auction.convert_datetime(auction.auction_document['stages'][i - 1]['start']) for i in range(2, 82)]
    for timedelta in timedeltas:
        assert timedelta.seconds == 300

    auction.parameters['dutchSteps'] = 99

    auction.prepare_auction_document()
    assert len(auction.auction_document['stages']) == 106

    # last dutch stage amount for 99 steps
    assert auction.auction_document['stages'][100]['amount'] == auction.auction_document['value']['amount'] * 0.01

    # min dutch stage duration
    timedeltas = [auction.convert_datetime(auction.auction_document['stages'][i]['start']) -
                  auction.convert_datetime(auction.auction_document['stages'][i-1]['start']) for i in range(2, 101)]
    for timedelta in timedeltas:
        assert timedelta.seconds == 243
