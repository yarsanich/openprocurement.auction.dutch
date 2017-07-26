# -*- coding: utf-8 -*-
def prepare_initial_bid_stage(bidder_name="", bidder_id="", time="",
                              amount_features="", coeficient="", amount=""):
    # XXX TODO Remove features and coeficients
    stage = dict(bidder_id=bidder_id, time=str(time))
    stage["label"] = dict(
        en="Bidder #{}".format(bidder_name),
        uk="Учасник №{}".format(bidder_name),
        ru="Участник №{}".format(bidder_name)
    )
    stage['amount'] = amount if amount else 0
    if amount_features is not None and amount_features != "":
        stage['amount_features'] = str(amount_features)
    if coeficient:
        stage['coeficient'] = str(coeficient)
    return stage


def post_results_data(self, with_auctions_results=True):
    """TODO: make me work"""


def announce_results_data(self, results=None):
    """TODO: make me work"""
