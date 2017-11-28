import json
from flask import session
from datetime import datetime, timedelta
from dateutil.tz import tzlocal
from mock import patch
from openprocurement.auction.insider.forms import form_handler


def test_server_login(app):
    headers = {
        'X-Forwarded-Path':
            'http://localhost:8090/auctions/11111111111111111111111111111111'
            '/authorized?code=HVRviZDxswGzM8AYN3rz0qMLrh6rhY'
    }
    res = app.post('/login', headers=headers)
    assert res.status == '405 METHOD NOT ALLOWED'
    assert res.status_code == 405

    res = app.get('/login')
    assert res.status == '401 UNAUTHORIZED'
    assert res.status_code == 401

    res = app.get('/login?bidder_id=5675acc9232942e8940a034994ad883e&'
                  'signature=bd4a790aac32b73e853c26424b032e5a29143d1f')
    assert res.status == '302 FOUND'
    assert res.status_code == 302
    assert res.location == 'https://my.test.url'

    with app.application.test_request_context():
        session['login_bidder_id'] = u'5675acc9232942e8940a034994ad883e'
        session['signature'] = u'bd4a790aac32b73e853c26424b032e5a29143d1f'
        session['login_callback'] = 'http://localhost/authorized'
        log_message = 'Session: {}'.format(repr(session))
        app.application.logger.debug.assert_called_with(log_message)

    res = app.get('/login?bidder_id=5675acc9232942e8940a034994ad883e&'
                  'signature=bd4a790aac32b73e853c26424b032e5a29143d1f',
                  headers=headers)
    assert res.status == '302 FOUND'
    assert res.status_code == 302
    assert res.location == 'https://my.test.url'
    with app.application.test_request_context():
        session[u'login_bidder_id'] = u'5675acc9232942e8940a034994ad883e'
        session[u'signature'] = u'bd4a790aac32b73e853c26424b032e5a29143d1f'
        session[u'login_callback'] = u'http://localhost:8090/auctions/' \
            '11111111111111111111111111111111/authorized'
        log_message = 'Session: {}'.format(repr(session))
        app.application.logger.debug.assert_called_with(log_message)

    res = app.get('/login?bidder_id=5675acc9232942e8940a034994ad883e&'
                  'signature=bd4a790aac32b73e853c26424b032e5a29143d1f&'
                  'return_url=https://my.secret.url/')
    assert res.status == '302 FOUND'
    assert res.status_code == 302
    assert res.location == 'https://my.test.url'
    with app.application.test_request_context():
        session['return_url'] = u'https://my.secret.url/'
        session['login_bidder_id'] = u'5675acc9232942e8940a034994ad883e'
        session['signature'] = u'bd4a790aac32b73e853c26424b032e5a29143d1f'
        session['login_callback'] = 'http://localhost/authorized'


def test_server_authorized(app):
    headers = {
        'X-Forwarded-Path':
            'http://localhost:8090/auctions/11111111111111111111111111111111'
            '/authorized?code=HVRviZDxswGzM8AYN3rz0qMLrh6rhY'
    }

    res = app.post('/authorized', headers=headers)
    assert res.status == '405 METHOD NOT ALLOWED'
    assert res.status_code == 405

    res = app.get('/authorized', headers=headers)
    assert res.status_code == 403
    assert res.status == '403 FORBIDDEN'

    res = app.get('/authorized?error=access_denied')
    assert res.status_code == 403
    assert res.status == '403 FORBIDDEN'

    app.application.config['auction'].mapping['f7c8cd1d56624477af8dc3aa9c4b3ea3'] = 1

    res = app.get('/authorized', headers=headers)
    assert res.status_code == 302
    assert res.status == '302 FOUND'
    assert res.location == \
        'http://localhost:8090/auctions/11111111111111111111111111111111'
    auctions_loggedin = False
    auction_session = False
    path = False
    for h in res.headers:
        if h[1].startswith('auctions_loggedin=1'):
            auctions_loggedin = True
            if h[1].index('Path=/auctions/UA-11111'):
                path = True
        if h[1].startswith('auction_session='):
            auction_session = True
    assert auction_session is True
    assert auctions_loggedin is True
    assert path is True


def test_server_relogin(app):
    headers = {
        'X-Forwarded-Path':
            'http://localhost:8090/auctions/11111111111111111111111111111111'
            '/authorized?code=HVRviZDxswGzM8AYN3rz0qMLrh6rhY'
    }

    res = app.post('/relogin', headers=headers)
    assert res.status == '405 METHOD NOT ALLOWED'
    assert res.status_code == 405

    res = app.get('/relogin', headers=headers)
    assert res.status_code == 302
    assert res.status == '302 FOUND'
    assert res.location == \
        'http://localhost:8090/auctions/11111111111111111111111111111111'
    s = {
        'login_callback': 'https://some.url/',
        'login_bidder_id': 'some_id',
        'signature': 'some_signature',
        'amount': 100
    }
    with patch('openprocurement.auction.insider.server.session', s):
        res = app.get('/relogin?amount=100', headers=headers)
    assert res.status_code == 302
    assert res.status == '302 FOUND'
    assert res.location == 'https://my.test.url'


def test_server_check_authorization(app):

    res = app.get('/check_authorization')
    assert res.status == '405 METHOD NOT ALLOWED'
    assert res.status_code == 405

    s = {
        'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', ''),
        'client_id': 'b3a000cdd006b4176cc9fafb46be0273'
    }

    res = app.post('/check_authorization')
    assert res.status == '401 UNAUTHORIZED'
    assert res.status_code == 401

    with patch('openprocurement.auction.insider.server.session', s):
        res = app.post('/check_authorization')
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data)['status'] == 'ok'

    with patch('openprocurement.auction.insider.server.session', s):
        app.application.logins_cache[
            (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', '')
        ]['expires'] = (
            (datetime.now(tzlocal()) - timedelta(0, 600)).isoformat()
        )
        res = app.post('/check_authorization')
    assert res.status == '401 UNAUTHORIZED'
    assert res.status_code == 401
    app.application.logger.info.assert_called_with(
        'Grant will end in a short time. Activate re-login functionality',
        extra={}
    )
    s['remote_oauth'] = 'invalid'

    with patch('openprocurement.auction.insider.server.session', s):
        res = app.post('/check_authorization')
    assert res.status == '401 UNAUTHORIZED'
    assert res.status_code == 401
    app.application.logger.warning.assert_called_with(
        "Client_id {} didn't passed check_authorization".format(
            s['client_id']), extra={})


def test_server_logout(app):
    s = {
        'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', ''),
        'client_id': 'b3a000cdd006b4176cc9fafb46be0273'
    }
    headers = {
        'X-Forwarded-Path':
            'http://localhost:8090/auctions/11111111111111111111111111111111'
            '/authorized?code=HVRviZDxswGzM8AYN3rz0qMLrh6rhY'
    }
    with patch('openprocurement.auction.insider.server.session', s):
        res = app.get('/logout', headers=headers)
    assert res.status_code == 302
    assert res.status == '302 FOUND'
    assert res.location == \
        'http://localhost:8090/auctions/11111111111111111111111111111111'


def test_server_postbid_and_form_handler(app):
    headers = {'Content-Type': 'application/json'}
    data = {'bidder_id': u'f7c8cd1d56624477af8dc3aa9c4b3ea3'}
    res = app.get('/postbid')
    assert res.status == '405 METHOD NOT ALLOWED'
    assert res.status_code == 405

    s = {
        'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', ''),
        'client_id': 'b3a000cdd006b4176cc9fafb46be0273'
    }
    with patch('openprocurement.auction.insider.server.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data)['data'] == 'ok'

    with patch('openprocurement.auction.insider.server.session', s):
        res = app.post('/postbid', data=json.dumps({'bidder_id': u'666'}),
                       headers=headers)
    mess_str = \
        'Client with client id: b3a000cdd006b4176cc9fafb46be0273 and ' \
        'bidder_id 666 wants post bid but response status from Oauth'
    app.application.logger.warning.assert_called_with(mess_str)
    assert res.status == '401 UNAUTHORIZED'
    assert res.status_code == 401

    # Test form_handler via /postbid
    app.application.form_handler = form_handler
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'failed',
        u'errors': {
            u'bid': [u'Bid amount is required'],
            u'bidder_id': [
                u'Not allowed to post bid on current (pre-started) phase']
        }
    }

    data['bid'] = 9010
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'failed',
        u'errors': {
            u'bid': [
                u'Not allowed to post bid on current (pre-started) phase'],
            u'bidder_id': [
                u'Not allowed to post bid on current (pre-started) phase']
        }
    }

    # Prepare auction
    stage = app.application.config['auction'].auction_document['stages'][1]
    app.application.config['auction'].next_stage(stage)  # stage 1
    app.application.config['auction'].next_stage(stage)  # stage 2

    data['bid'] = '9010'
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'failed',
        u'errors': {
            u'bid': [u"Passed value doesn't match current amount=34650.0000"]
        }
    }

    # Prepare auction
    stage = app.application.config['auction'].auction_document['stages'][1]
    app.application.config['auction'].next_stage(stage)  # stage 1
    data['bid'] = 9010
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'failed',
        u'errors': {
            u'bid': [u"Passed value doesn't match current amount=34300.0000"]
        }
    }

    data['bid'] = 34300
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'failed',
        u'errors': [[u'Bad bidder!']]
    }

    # Prepare auction
    dutch_bidder_id = 'f7c8cd1d56624477af8dc3aa9c4b3ea3'
    sealedbid_bidder_id = 'f7c8cd1d56624477af8dc3aa9c4b3ea4'
    bestbid_bidder_id = 'f7c8cd1d56624477af8dc3aa9c4b3ea5'
    app.application.config['auction'].bidders_data.append(
        {'id': dutch_bidder_id})
    app.application.config['auction'].mapping[dutch_bidder_id] = \
        len(app.application.config['auction'].mapping) + 1
    app.application.config['auction'].bidders_data.append(
        {'id': sealedbid_bidder_id})
    app.application.config['auction'].mapping[sealedbid_bidder_id] = \
        len(app.application.config['auction'].mapping) + 1
    app.application.config['auction'].bidders_data.append(
        {'id': bestbid_bidder_id})
    app.application.config['auction'].mapping[bestbid_bidder_id] = \
        len(app.application.config['auction'].mapping) + 1
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'ok',
        u'data': {
            u'bid': 34300,
            u'bidder_id': u'f7c8cd1d56624477af8dc3aa9c4b3ea3'
        }
    }
    assert app.application.config['auction'].bidders_count == 1

    # Prepare auction switch_to_sealedbid
    current_stage = \
        app.application.config['auction'].auction_document['current_stage'] + 1
    stage = app.application.config['auction'].auction_document[
        'stages'][current_stage]
    app.application.config['auction'].switch_to_sealedbid(stage)

    data['bid'] = -10
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'failed',
        u'errors': {
            u'bid': [u'To low value'],
            u'bidder_id': [u'Not allowed to post bid for dutch winner']
        }
    }

    data['bid'] = 34300
    data['bidder_id'] = sealedbid_bidder_id
    s['remote_oauth'] = (u'aMALGpjnB1iyBwXJM6betfgT4usZZZ', '')
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'failed',
        u'errors': {
            u'bid': [u"Bid value can't be less or equal current amount"]
        }
    }

    data['bid'] = -1
    data['bidder_id'] = bestbid_bidder_id
    s['remote_oauth'] = (u'aMALGpjnB1iyBwXJM6betfgT4usYYY', '')
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'ok',
        u'data': {
            u'bid': -1,
            u'bidder_id': u'f7c8cd1d56624477af8dc3aa9c4b3ea5'
        }
    }
    assert app.application.config['auction'].bids_queue.qsize() == 1

    data['bid'] = 34301
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'ok',
        u'data': {
            u'bid': 34301,
            u'bidder_id': u'f7c8cd1d56624477af8dc3aa9c4b3ea5'
        }
    }
    assert app.application.config['auction'].bids_queue.qsize() == 2

    data['bid'] = 34802
    data['bidder_id'] = sealedbid_bidder_id
    s['remote_oauth'] = (u'aMALGpjnB1iyBwXJM6betfgT4usZZZ', '')
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'ok',
        u'data': {
            u'bid': 34802,
            u'bidder_id': u'f7c8cd1d56624477af8dc3aa9c4b3ea4'
        }
    }
    assert app.application.config['auction'].bids_queue.qsize() == 3

    # Prepare auction switch_to_end_sealedbid
    current_stage = \
        app.application.config['auction'].auction_document['current_stage'] + 1
    stage = app.application.config['auction'].auction_document[
        'stages'][current_stage]
    app.application.config['auction'].end_sealedbid(stage)

    # Prepare auction switch_to_bestbid
    current_stage = \
        app.application.config['auction'].auction_document['current_stage'] + 1
    stage = app.application.config['auction'].auction_document[
        'stages'][current_stage]
    app.application.config['auction'].switch_to_bestbid(stage)

    data['bid'] = 34803
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'failed',
        u'errors': {
            u'bidder_id': [u"bidder_id don't match with dutchWinner.bidder_id"]
        }
    }

    data['bidder_id'] = dutch_bidder_id
    data['bid'] = 34300
    s['remote_oauth'] = (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', '')
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'failed',
        u'errors': {
            u'bid': [u"Bid value can't be less or equal current amount"]
        }
    }

    data['bidder_id'] = dutch_bidder_id
    data['bid'] = 34701
    s['remote_oauth'] = (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', '')
    with patch('openprocurement.auction.insider.server.session', s), \
         patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'failed',
        u'errors': {
            u'bid': [
                u"The amount you suggest should not be less than the greatest"
                u" bid made during the previous stage."
            ]
        }
    }

    data['bidder_id'] = dutch_bidder_id
    data['bid'] = 34803
    s['remote_oauth'] = (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', '')
    with patch('openprocurement.auction.insider.server.session', s), \
            patch('openprocurement.auction.insider.forms.session', s):
        res = app.post('/postbid', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data) == {
        u'status': u'ok',
        u'data': {
            u'bid': 34803,
            u'bidder_id': u'f7c8cd1d56624477af8dc3aa9c4b3ea3'
        }
    }

    # Prepare auction switch_to_end_auction
    current_stage = \
        app.application.config['auction'].auction_document['current_stage'] + 1
    stage = app.application.config['auction'].auction_document[
        'stages'][current_stage]
    app.application.config['auction'].end_bestbid(stage)


def test_server_kickclient(app):
    s = {
        'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', ''),
        'client_id': 'b3a000cdd006b4176cc9fafb46be0273'
    }
    data = {
        'client_id': s['client_id'],
        'bidder_id': u'f7c8cd1d56624477af8dc3aa9c4b3ea3'
    }
    headers = {'Content-Type': 'application/json'}

    res = app.get('/kickclient')
    assert res.status == '405 METHOD NOT ALLOWED'
    assert res.status_code == 405

    res = app.post('/kickclient', data=json.dumps(data), headers=headers)
    assert res.status == '401 UNAUTHORIZED'
    assert res.status_code == 401

    with patch('openprocurement.auction.insider.server.session', s):
        res = app.post('/kickclient', data=json.dumps(data), headers=headers)
    assert res.status == '200 OK'
    assert res.status_code == 200
    assert json.loads(res.data)['status'] == 'ok'
