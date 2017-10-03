# -*- coding: utf-8 -*-
import pytest
from munch import munchify
from openprocurement.auction.insider.constants import (
    DUTCH, SEALEDBID, BESTBID
)
from openprocurement.auction.insider.forms import form_handler


def test_default_data_required_validators(bids_form):
    valid = bids_form.validate()
    assert valid is False
    assert len(bids_form.errors) == 2
    assert ('bid', [u'Bid amount is required']) in bids_form.errors.items()
    assert ('bidder_id', [u'No bidder id']) in bids_form.errors.items()


def test_bid_value_validator_amount_error(bids_form):
    bids_form.document['current_phase'] = DUTCH
    del bids_form.document['current_stage']
    with pytest.raises(KeyError) as e_info:
        bids_form.bid.data = '15.0'
        bids_form.validate()

    assert e_info.type is KeyError
    assert e_info.value.message == 'current_stage'
    assert len(bids_form.errors) == 2
    assert ('bid', ['current_stage']) in bids_form.errors.items()


def test_bid_value_validator_on_dutch(bids_form):
    bids_form.document['current_phase'] = DUTCH
    bids_form.document['current_stage'] = 1
    bids_form.bid.data = '10'
    valid = bids_form.validate()
    assert valid is False
    assert len(bids_form.errors) == 2
    assert ('bid', ["Passed value doesn't match current amount=35000"]) in \
        bids_form.errors.items()


def test_validate_bidder_id_error_on_bestbid(bids_form):
    bids_form.document['current_phase'] = BESTBID
    del bids_form.document['results']
    bids_form.bidder_id.data = '123'
    with pytest.raises(KeyError) as e:
        bids_form.validate()
    assert e.value.message == 'results'
    assert len(bids_form.errors) == 1


def test_form_handler_error_on_sealedbid(app, mocker):
    app.application.form_handler = form_handler
    app.application.config['auction'].auction_document['current_phase'] = \
        SEALEDBID
    app.application.config['auction'].bids_queue.put = mocker.MagicMock(
        side_effect=[Exception('Something went wrong :(')]
    )
    magic_form = mocker.MagicMock()
    magic_form.validate.return_value = True
    app.application.bids_form = mocker.MagicMock()
    app.application.bids_form.from_json.return_value = magic_form
    mocker.patch('openprocurement.auction.insider.forms.request', munchify({'json': {}, 'headers': {}}))
    with app.application.test_request_context():
        res = app.application.form_handler()
    assert res == {
        'status': 'failed',
        'errors': ["Exception('Something went wrong :(',)"]
    }


def test_form_handler_error_on_bestbid(app, mocker):
    app.application.form_handler = form_handler
    app.application.config['auction'].auction_document['current_phase'] = \
        BESTBID
    app.application.config['auction'].add_bestbid = mocker.MagicMock(
        return_value=Exception('Something went wrong :(')
    )
    magic_form = mocker.MagicMock()
    magic_form.validate.return_value = True
    app.application.bids_form = mocker.MagicMock()
    app.application.bids_form.from_json.return_value = magic_form
    mocker.patch('openprocurement.auction.insider.forms.request', munchify({'json': {}, 'headers': {}}))
    mocker.patch('openprocurement.auction.insider.forms.session', {})
    with app.application.test_request_context():
        res = app.application.form_handler()
    assert res == {
        'status': 'failed',
        'errors': ["Exception('Something went wrong :(',)"]
    }


def test_form_handler_error_on_invalid_stage(app, mocker):
    app.application.form_handler = form_handler
    app.application.config['auction'].auction_document['current_phase'] = \
        'invalid_stage'
    magic_form = mocker.MagicMock()
    magic_form.validate.return_value = True
    app.application.bids_form = mocker.MagicMock()
    app.application.bids_form.from_json.return_value = magic_form
    mocker.patch('openprocurement.auction.insider.forms.request', munchify({'json': {}, 'headers': {}}))
    with app.application.test_request_context():
        res = app.application.form_handler()
    assert res == {
        'status': 'failed',
        'errors': {
            'form': ['Bids period expired.']
        }
    }
