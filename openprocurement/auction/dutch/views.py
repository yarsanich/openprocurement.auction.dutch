from openprocurement.auction.auctions_server import auctions_proxy


def includeme(app):
    app.add_url_rule('/dutch-tenders/<auction_doc_id>/<path:path>', 'dutch-tenders',
                     auctions_proxy,
                     methods=['GET', 'POST'])
