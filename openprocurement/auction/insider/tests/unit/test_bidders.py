# -*- coding: utf-8 -*-
import pytest
import json
from mock import patch, call
from openprocurement.auction.insider.constants import (
    DUTCH, PRESEALEDBID, SEALEDBID, PREBESTBID
)
from openprocurement.auction.insider.tests.data.data import \
    parametrize_on_dutch_test, parametrize_on_sealbid_test, new_bid_from_cdb


@pytest.mark.parametrize("bidder, expected", parametrize_on_dutch_test)
def test_new_bidders_on_dutch(auction_app, bidder, expected):
    headers = {'Content-Type': 'application/json'}
    session = {
        'remote_oauth': None,
        'client_id': 'b3a000cdd006b4176cc9fafb46be0273'
    }
    config = auction_app.application.config
    config['auction']._auction_data['data']['bids'].append(new_bid_from_cdb)

    # Phase: DUTCH
    # Switch auction to 'dutch_5' stage
    stage = config['auction'].auction_document['stages'][1]
    for i in xrange(0, 6):
        config['auction'].next_stage(stage)
    assert config['auction'].auction_document['current_stage'] == 6
    assert config['auction'].auction_document['current_phase'] == DUTCH
    assert len(config['auction'].mapping) == 5
    # Place bid by new bidder which exist in CDB but not present in auction_doc
    data = {
        'bidder_id': bidder['bidder_id'],
        'bid': 33250
    }
    session['remote_oauth'] = bidder['remote_oauth']
    with patch('openprocurement.auction.insider.server.session', session), \
         patch('openprocurement.auction.insider.forms.session', session):
        res = auction_app.post('/postbid', data=json.dumps(data),
                               headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == expected


@pytest.mark.parametrize("bidder, expected", parametrize_on_sealbid_test)
def test_new_bidders_on_sealedbid(sealedbid_app, bidder, expected):
    headers = {'Content-Type': 'application/json'}
    session = {
        'remote_oauth': None,
        'client_id': 'b3a000cdd006b4176cc9fafb46be0273'
    }
    config = sealedbid_app.application.config
    assert config['auction'].auction_document['current_phase'] == PRESEALEDBID
    assert config['auction'].auction_document['current_stage'] == 11

    # Prepare context for next phase
    config['auction']._auction_data['data']['bids'].append(new_bid_from_cdb)
    assert len(config['auction'].mapping) == 5

    # Switch auction to SEALEDBID
    current_stage = config['auction'].auction_document['current_stage'] + 1
    stage = config['auction'].auction_document['stages'][current_stage]
    config['auction'].switch_to_sealedbid(stage)

    # Phase: SEALEDBID
    assert len(config['auction'].mapping) == 6
    assert config['auction'].auction_document['current_phase'] == SEALEDBID
    assert config['auction'].auction_document['current_stage'] == 12

    data = {
        'bidder_id': bidder['bidder_id'],
        'bid': 33350
    }
    session['remote_oauth'] = bidder['remote_oauth']

    with patch('openprocurement.auction.insider.server.session', session), \
         patch('openprocurement.auction.insider.forms.session', session):
        res = sealedbid_app.post('/postbid', data=json.dumps(data),
                                 headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == expected

    # Switch to PREBESTBID
    current_stage = config['auction'].auction_document['current_stage']
    stage = config['auction'].auction_document['stages'][current_stage]
    if bidder['bidder_id'] != '2' * 32:
        config['auction'].end_sealedbid(stage)

        assert config['auction'].auction_document['current_phase'] == PREBESTBID
        assert config['auction'].auction_document['current_stage'] == 13
        win_bidder = False
        for result in config['auction'].auction_document['results']:
            if bidder['bidder_id'] == result['bidder_id'] and \
                    result['sealedbid_winner']:
                win_bidder = True
                break
        assert win_bidder is True
    else:
        with pytest.raises(KeyError) as e:
            config['auction'].end_sealedbid(stage)
        assert isinstance(e.type(), KeyError) is True
        assert e.value.message == u'22222222222222222222222222222222'
        assert config['auction'].auction_document['current_phase'] == SEALEDBID
        assert config['auction'].auction_document['current_stage'] == 12
