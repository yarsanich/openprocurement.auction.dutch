# -*- coding: utf-8 -*-
# import pytest

# DUTCH_BIDS_ARRAY_FIELD = 'TODO: Назва поля, поле масив'  # TODO: temporary field name
#
#
# def test_default_data_required_validators(bids_form):
#     valid = bids_form.validate()
#     assert valid is False
#     assert len(bids_form.errors) == 2
#     assert ('bid', [u'Bid amount is required']) in bids_form.errors.items()
#     assert ('bidder_id', [u'No bidder id']) in bids_form.errors.items()
#
#
# def test_bid_value_validator_amount_error(bids_form):
#     with pytest.raises(KeyError) as e_info:
#         bids_form.bid.data = 15.0
#         bids_form.validate()
#
#     assert e_info.type is KeyError
#     assert e_info.value.message == DUTCH_BIDS_ARRAY_FIELD
#     assert len(bids_form.errors) == 2
#     assert ('bid', [DUTCH_BIDS_ARRAY_FIELD]) in bids_form.errors.items()
#
#
# @pytest.mark.parametrize("stage,test_input,expected", [
#     ('dutch', -0.5, u'Too low value'),
#     ('dutch', 'some_value', "Invalid literal for Fraction: 'some_value'"),
#     ('dutch', 350001, u'applyAmount don\'t match with currentDutchAmount'),
#     ('sealedBids', 349999, u'Bid value can\'t be less or equal current amount'),
#     ('bestBid', 349999, u'Bid value can\'t be less or equal current amount'),
#     ('invalid_stage', 350000, u'Invalid auction phase'),
# ])
# def test_bid_value_validator(bids_form, stage, test_input, expected):
#     bids_form.document[DUTCH_BIDS_ARRAY_FIELD] = [350000]
#     bids_form.document['phase'] = stage
#     bids_form.bid.data = test_input
#     valid = bids_form.validate()
#     assert valid is False
#     assert len(bids_form.errors) == 2
#     assert ('bid', [expected]) in bids_form.errors.items()
#
#
# def test_bidder_id_validator_any_value_while_dutch_stage_lasts(bids_form):
#     bids_form.bidder_id.data = 'some_id'
#     valid = bids_form.validate()
#     assert valid is False
#     assert len(bids_form.errors) == 1
#     assert ('bid', [u'Bid amount is required']) in bids_form.errors.items()
#
#
# def test_bidder_id_validator_dutch_winner_id_not_in_document(bids_form):
#     bids_form.document['phase'] = 'any_but_not_dutch'
#
#     with pytest.raises(KeyError) as e_info:
#         bids_form.bidder_id.data = 'some_id'
#         bids_form.validate()
#
#     assert e_info.type is KeyError
#     assert e_info.value.message == 'dutchWinner'
#     assert len(bids_form.errors) == 1
#     assert 'bidder_id' in bids_form.errors.items()[0]
#
#
# @pytest.mark.parametrize("stage,test_input,expected", [
#     ('sealedBids', 'dutch_winner_id', u'bidder_id match with dutchWinner.bidder_id'),
#     ('bestBid', 'not_dutch_winner_id', u'bidder_id don\'t match with dutchWinner.bidder_id'),
#     ('invalid_stage', 'some_id', u'Invalid auction phase'),
# ])
# def test_bidder_id_validator_dutch_stage(bids_form, stage, test_input, expected):
#     bids_form.document['dutchWinner'] = {'bidder_id': 'dutch_winner_id'}
#     bids_form.document['phase'] = stage
#     bids_form.bidder_id.data = test_input
#     valid = bids_form.validate()
#     assert valid is False
#     assert len(bids_form.errors) == 2
#     assert ('bidder_id', [expected]) in bids_form.errors.items()
