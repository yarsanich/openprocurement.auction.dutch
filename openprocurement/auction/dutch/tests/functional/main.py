# -*- coding: utf-8 -*-
from gevent import monkey
monkey.patch_all()

import os
import datetime
import json
import contextlib
import tempfile
from dateutil.tz import tzlocal
from gevent.subprocess import check_output, sleep


PWD = os.path.dirname(os.path.realpath(__file__))
CWD = os.getcwd()


@contextlib.contextmanager
def update_auctionPeriod(path, auction_type):
    with open(path) as file:
        data = json.loads(file.read())
    new_start_time = (datetime.datetime.now(tzlocal()) + datetime.timedelta(seconds=120)).isoformat()
    if auction_type == 'esco':
        data['data']['auctionPeriod']['startDate'] = new_start_time

    with tempfile.NamedTemporaryFile(delete=False) as auction_file:
        json.dump(data, auction_file)
        auction_file.seek(0)
    yield auction_file.name
    auction_file.close()

# XXX TODO Fix tests with dutch worker
# def run_esco(tender_file_path, auction_id):
#     with update_auctionPeriod(tender_file_path, auction_type='esco') as auction_file:
#         check_output('{0}/bin/auction_esco planning {1}'
#                      ' {0}/etc/auction_worker_esco.yaml --planning_procerude partial_db --auction_info {2}'.format(CWD, auction_id, auction_file).split())
#     sleep(30)


# def includeme(actions):
#     actions['esco'] = ({'action': run_esco, 'suite_dir': PWD},)
#     actions['all'] += actions['esco']
