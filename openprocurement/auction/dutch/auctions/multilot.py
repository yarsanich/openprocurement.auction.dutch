import logging

from openprocurement.auction.utils import get_latest_bid_for_bidder, make_request
from openprocurement.auction.worker.auctions import multilot
from openprocurement.auction.worker.utils import prepare_service_stage
from openprocurement.auction.worker.journal import AUCTION_WORKER_API_APPROVED_DATA


FORMATTER = lambda **kw: "{}_{}".format(kw.get('tender_id'), kw.get('lot_id'))
MULTILINGUAL_FIELDS = ['title', 'description']
ADDITIONAL_LANGUAGES = ['ru', 'en']
LOGGER = logging.getLogger('Auction Worker')


# Indentical methods
get_auction_info = multilot.get_auction_info
prepare_auction_and_participation_urls = multilot.prepare_auction_and_participation_urls
announce_results_data = multilot.announce_results_data


def prepare_auction_document(self):
    self.auction_document.update(
        {'_id': self.auction_doc_id,
         'stages': [],
         'tenderID': self._auction_data['data'].get('tenderID', ''),
         'procurementMethodType': self._auction_data['data'].get('procurementMethodType', ''),
         'TENDERS_API_VERSION': self.worker_defaults['TENDERS_API_VERSION'],
         'initial_bids': [],
         'current_stage': -1,
         "NBUdiscountRate": self._auction_data["data"].get("NBUdiscountRate"),
         'results': [],
         'minimalStep': self._lot_data.get('minimalStep', {}),
         'procuringEntity': self._auction_data['data'].get('procuringEntity', {}),
         'items': self._lot_data.get('items', []),
         'minValue': self._lot_data.get('value', {}),
         'lot': {}}
    )
    self.auction_document['auction_type'] = 'meat' if self.features else 'default'

    for key in MULTILINGUAL_FIELDS:
        for lang in ADDITIONAL_LANGUAGES:
            lang_key = '{}_{}'.format(key, lang)
            if lang_key in self._auction_data['data']:
                self.auction_document[lang_key] = self._auction_data['data'][lang_key]
            if lang_key in self._lot_data:
                self.auction_document['lot'][lang_key] = self._lot_data[lang_key]
        self.auction_document[key] = self._auction_data['data'].get(key, '')
        self.auction_document['lot'][key] = self._lot_data.get(key, '')

    self.auction_document['stages'].append(
        prepare_service_stage(
            start=self.startDate.isoformat(),
            type="pause"
        )
    )
    return self.auction_document


# TODO: bid['value']['amount']
def post_results_data(self, with_auctions_results=True):
    patch_data = {'data': {'bids': list(self._auction_data['data']['bids'])}}
    if with_auctions_results:
        for bid_index, bid in enumerate(self._auction_data['data']['bids']):
            if bid.get('status', 'active') == 'active':
                for lot_index, lot_bid in enumerate(bid['lotValues']):
                    if lot_bid['relatedLot'] == self.lot_id and lot_bid.get('status', 'active') == 'active':
                        auction_bid_info = get_latest_bid_for_bidder(self.auction_document["results"], bid["id"])
                        patch_data['data']['bids'][bid_index]['lotValues'][lot_index]["value"]["amount"] = auction_bid_info["amount"]
                        patch_data['data']['bids'][bid_index]['lotValues'][lot_index]["date"] = auction_bid_info["time"]
                        break

    LOGGER.info(
        "Approved data: {}".format(patch_data),
        extra={"JOURNAL_REQUEST_ID": self.request_id,
               "MESSAGE_ID": AUCTION_WORKER_API_APPROVED_DATA}
    )
    results = make_request(
        self.tender_url + '/auction/{}'.format(self.lot_id), data=patch_data,
        user=self.worker_defaults["TENDERS_API_TOKEN"],
        method='post',
        request_id=self.request_id, session=self.session
    )
    return results
