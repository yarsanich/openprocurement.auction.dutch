# -*- coding: utf-8 -*-
import os
import datetime
import json
from gevent.subprocess import check_output, sleep


PWD = os.path.dirname(os.path.realpath(__file__))
CWD = os.getcwd()


def run_dutch(tender_file_path):
    with open(tender_file_path) as _file:
        auction_id = json.load(_file).get('data').get('id')
    with update_auctionPeriod(tender_file_path, auction_type='dutch') as auction_file:
        check_output('{0}/bin/auction_insider planning {1}'
                     ' {0}/etc/auction_worker_insider.yaml --planning_procerude partial_db --auction_info {2}'.format(CWD, auction_id, auction_file).split())
    sleep(30)


def includeme(tests):
    tests['insider'] = {
        "worker_cmd": '{0}/bin/auction_insider planning {1}'
                      ' {0}/etc/auction_worker_insider.yaml'
                      ' --planning_procerude partial_db --auction_info {2}',
        "runner": run_dutch,
        'auction_worker_defaults': 'auction_worker_defaults:{0}/etc/auction_worker_insider.yaml'.format(PWD),
        'suite': PWD
    }
