# -*- coding: utf-8 -*-
import datetime
import logging
import os
import pytest
import yaml
import couchdb

from dateutil.tz import tzlocal
from StringIO import StringIO

from openprocurement.auction.dutch.auction import Auction, SCHEDULER
from openprocurement.auction.dutch.forms import BidsForm
from openprocurement.auction.dutch.mixins import LOGGER
from openprocurement.auction.dutch.tests.data.data import tender_data


def update_auctionPeriod(data):
    new_start_time = (datetime.datetime.now(tzlocal()) + datetime.timedelta(seconds=120)).isoformat()
    if 'lots' in data['data']:
        for lot in data['data']['lots']:
            lot['auctionPeriod']['startDate'] = new_start_time
    data['data']['auctionPeriod']['startDate'] = new_start_time


PWD = os.path.dirname(os.path.realpath(__file__))

worker_defaults_file_path = os.path.join(PWD, "openprocurement/auction/dutch/tests/data/auction_worker_defaults.yaml")
with open(worker_defaults_file_path) as stream:
    worker_defaults = yaml.load(stream)


@pytest.yield_fixture(scope="function")
def auction():
    update_auctionPeriod(tender_data)

    yield Auction(
        tender_id=tender_data['data']['tenderID'],
        worker_defaults=yaml.load(open(worker_defaults_file_path)),
        auction_data=tender_data,
        lot_id=False
    )


@pytest.fixture(scope='function')
def db(request):
    server = couchdb.Server("http://" + worker_defaults['COUCH_DATABASE'].split('/')[2])
    name = worker_defaults['COUCH_DATABASE'].split('/')[3]

    def delete():
        del server[name]

    if name in server:
        delete()
    server.create(name)
    request.addfinalizer(delete)


class LogInterceptor(object):
    def __init__(self, logger):
        self.log_capture_string = StringIO()
        self.test_handler = logging.StreamHandler(self.log_capture_string)
        self.test_handler.setLevel(logging.INFO)
        logger.addHandler(self.test_handler)


@pytest.fixture(scope='function')
def logger():
    return LogInterceptor(LOGGER)


@pytest.fixture(scope='function')
def scheduler():
    return SCHEDULER


@pytest.fixture(scope='function')
def bids_form(auction):
    form = BidsForm()
    auction.prepare_auction_document()
    form.document = auction.auction_document
    return form


def pytest_addoption(parser):
    parser.addoption("--worker", action="store_true", help="runs worker test", dest='worker')


def pytest_configure(config):
    # register an additional marker
    config.addinivalue_line("markers", "worker: mark test to run only if worker option is passed (--worker)")


def pytest_runtest_setup(item):
    worker_marker = item.get_marker("worker")
    if worker_marker is not None:
        if not item.config.getoption("worker", False):
            pytest.skip("test requires worker option (--worker)")
