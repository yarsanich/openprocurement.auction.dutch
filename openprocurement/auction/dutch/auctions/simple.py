import logging

from openprocurement.auction.utils import get_latest_bid_for_bidder, make_request
from openprocurement.auction.worker.auctions import simple
from openprocurement.auction.worker.utils import prepare_service_stage
from openprocurement.auction.worker.journal import AUCTION_WORKER_API_APPROVED_DATA


FORMATTER = lambda **kw: "{}".format(kw.get('tender_id'))
MULTILINGUAL_FIELDS = ["title", "description"]
ADDITIONAL_LANGUAGES = ["ru", "en"]
ROUNDS = 3
LOGGER = logging.getLogger('Auction Worker')


# Indentical methods
get_auction_info = simple.get_auction_info
prepare_auction_and_participation_urls = simple.prepare_auction_and_participation_urls
announce_results_data = simple.announce_results_data


def prepare_auction_document(self):
    self.auction_document.update(
        {"_id": self.auction_doc_id,
         "stages": [],
         "tenderID": self._auction_data["data"].get("tenderID", ""),
         "procurementMethodType": self._auction_data["data"].get("procurementMethodType", "default"),
         "TENDERS_API_VERSION": self.worker_defaults["TENDERS_API_VERSION"],
         "initial_bids": [],
         "current_stage": -1,
         "results": [],
         "procuringEntity": self._auction_data["data"].get("procuringEntity", {}),
         "items": self._auction_data["data"].get("items", []),
         "minValue": self._auction_data["data"].get("minValue", {}),
         "phase": "dutch"}
    )
    # XXX TODO Remove meat 
    if self.features:
        self.auction_document["auction_type"] = "meat"
    else:
        self.auction_document["auction_type"] = "default"

    for key in MULTILINGUAL_FIELDS:
        for lang in ADDITIONAL_LANGUAGES:
            lang_key = "{}_{}".format(key, lang)
            if lang_key in self._auction_data["data"]:
                self.auction_document[lang_key] = self._auction_data["data"][lang_key]
        self.auction_document[key] = self._auction_data["data"].get(key, "")

    self.auction_document['stages'].append(
        prepare_service_stage(
            start=self.startDate.isoformat(),
            type="pause"
        )
    )

    return self.auction_document


# TODO: bid['value']['amount']
def post_results_data(self, with_auctions_results=True):

    if with_auctions_results:
        for index, bid_info in enumerate(self._auction_data["data"]["bids"]):
            if bid_info.get('status', 'active') == 'active':
                auction_bid_info = get_latest_bid_for_bidder(self.auction_document["results"], bid_info["id"])
                self._auction_data["data"]["bids"][index]["value"]["amount"] = auction_bid_info["amount"]
                self._auction_data["data"]["bids"][index]["date"] = auction_bid_info["time"]

    data = {'data': {'bids': self._auction_data["data"]['bids']}}
    LOGGER.info(
        "Approved data: {}".format(data),
        extra={"JOURNAL_REQUEST_ID": self.request_id,
               "MESSAGE_ID": AUCTION_WORKER_API_APPROVED_DATA}
    )
    return make_request(
        self.tender_url + '/auction', data=data,
        user=self.worker_defaults["TENDERS_API_TOKEN"],
        method='post',
        request_id=self.request_id, session=self.session
    )
