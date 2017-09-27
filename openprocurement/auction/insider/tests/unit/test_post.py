# -*- coding: utf-8 -*-


def test_put_auction_data(auction, logger, mocker):

    mock_post_results_data = mocker.MagicMock()
    mock_announce_results_data = mocker.MagicMock()
    mock_post_results_data.return_value = True
    mocker.patch('openprocurement.auction.insider.mixins.utils.post_results_data', mock_post_results_data)
    mocker.patch('openprocurement.auction.insider.mixins.utils.announce_results_data', mock_announce_results_data)

    result = auction.put_auction_data()

    assert result is True

    mock_post_results_data.return_value = False
    auction.generate_request_id()
    auction.put_auction_data()

    assert mock_post_results_data.call_count == 2
    assert mock_announce_results_data.call_count == 1

    auction.debug = False
    mock_approve_audit_info_on_announcement = mocker.patch.object(auction, 'approve_audit_info_on_announcement', autospec=True)
    mock_upload_audit_file_without_document_service = mocker.patch.object(
        auction,
        'upload_audit_file_without_document_service',
        autospec=True
    )
    mock_upload_audit_file_without_document_service.return_value = 'test_doc_id'
    mock_post_results_data.return_value = True
    mock_announce_results_data.return_value = ['bid_1', 'bid_2']
    # with_document_service == False

    auction.put_auction_data()

    mock_approve_audit_info_on_announcement.assert_called_once_with(approved=['bid_1', 'bid_2'])
    assert mock_upload_audit_file_without_document_service.call_count == 2
    assert mock_upload_audit_file_without_document_service.call_args_list[0] == ()
    assert mock_upload_audit_file_without_document_service.call_args_list[1][0] == ('test_doc_id', )
    assert mock_announce_results_data.call_count == 2
    assert mock_post_results_data.call_count == 3

    auction.worker_defaults['with_document_service'] = True
    mock_upload_audit_file_with_document_service = mocker.patch.object(
        auction,
        'upload_audit_file_with_document_service',
        autospec=True
    )
    mock_upload_audit_file_with_document_service.return_value = 'test_doc_id'

    auction.put_auction_data()

    assert mock_upload_audit_file_with_document_service.call_count == 2
    assert mock_upload_audit_file_with_document_service.call_args_list[0] == ()
    assert mock_upload_audit_file_with_document_service.call_args_list[1][0] == ('test_doc_id',)
    assert mock_announce_results_data.call_count == 3
    assert mock_post_results_data.call_count == 4


def test_post_announce(auction, mocker):
    mock_generate_request_id = mocker.patch.object(auction, 'generate_request_id')
    mock_update_auction_document = mocker.MagicMock()
    mock_announce_results_data = mocker.MagicMock()
    mocker.patch('openprocurement.auction.insider.mixins.utils.update_auction_document', mock_update_auction_document)
    mocker.patch('openprocurement.auction.insider.mixins.utils.announce_results_data', mock_announce_results_data)

    auction.post_announce()

    assert mock_generate_request_id.call_count == 1
    assert mock_generate_request_id.call_args == ()

    assert mock_update_auction_document.call_count == 1
    assert mock_update_auction_document.call_args[0] == (auction, )

    assert mock_announce_results_data.call_count == 1
    assert mock_announce_results_data.call_args[0] == (auction, None)
