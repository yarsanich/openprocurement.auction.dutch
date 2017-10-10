from openprocurement.auction.auctions_server import auctions_proxy


def includeme(app):
    app.add_url_rule('/insider-auctions/<auction_doc_id>/<path:path>', 'insider-auctions',
                     auctions_proxy,
                     methods=['GET', 'POST'])
