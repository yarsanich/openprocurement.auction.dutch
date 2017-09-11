# -*- coding: utf-8 -*-

from gevent import monkey
monkey.patch_all()

import os.path
import datetime
import json
import sys
import argparse
import contextlib
import tempfile
from dateutil.tz import tzlocal
from pkg_resources import iter_entry_points
from gevent.subprocess import check_output, sleep

from openprocurement.auction.tests.main import update_auctionPeriod


PWD = os.path.dirname(os.path.realpath(__file__))
CWD = os.getcwd()


def run_insider(tender_file_path):
    with open(tender_file_path) as _file:
        auction_id = json.load(_file).get('data', {}).get('id')
        if auction_id:
            with update_auctionPeriod(tender_file_path, auction_type='simple') as auction_file:
                check_output(TESTS['insider']['worker_cmd'].format(CWD, auction_id, auction_file).split())
    sleep(30)


TESTS = {
    "insider": {
        "worker_cmd": '{0}/bin/auction_insider planning {1}'
                      ' {0}/etc/auction_worker_insider.yaml'
                      ' --planning_procerude partial_db --auction_info {2}',
        "runner": run_insider,
        'auction_worker_defaults': 'auction_worker_defaults:{0}/etc/auction_worker_insider.yaml',
        'suite': PWD
    },
}


def includeme(tests):
    tests.update(TESTS)
