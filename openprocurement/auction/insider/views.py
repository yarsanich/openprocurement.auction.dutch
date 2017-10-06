import os.path
from urlparse import urlparse, urlunparse, parse_qs
from urllib import urlencode
from flask import request, redirect, Response, abort
from sse import Sse
from openprocurement.auction.utils import get_mapping
from openprocurement.auction.proxy import StreamProxy


TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')


def includeme(app):
    @app.route('/insider-auctions/<auction_doc_id>/<path:path>',
                           methods=['GET', 'POST'])
    def proxy(auction_doc_id, path):
        app.logger.debug('Auction_doc_id: {}'.format(auction_doc_id))
        exists = auction_doc_id in app.db

        if path == 'login' and exists:
            public_document = app.db.get(auction_doc_id)

            if public_document.get('onHold', False):
                with open(os.path.join(TEMPLATES, 'not_started.html')) as _in:
                    template = _in.read()
                return template

        proxy_path = app.proxy_mappings.get(
            str(auction_doc_id),
            get_mapping,
            (app.config['REDIS'], str(auction_doc_id), False), max_age=60
        )
        app.logger.debug('Proxy path: {}'.format(proxy_path))
        if proxy_path:
            request.environ['PATH_INFO'] = '/' + path
            app.logger.debug('Start proxy to path: {}'.format(path))
            return StreamProxy(
                proxy_path,
                auction_doc_id=str(auction_doc_id),
                event_sources_pool=app.event_sources_pool,
                event_source_connection_limit=app.config['event_source_connection_limit'],
                pool=app.proxy_connection_pool,
                backend="gevent"
            )
        elif path == 'login' and exists:
            if 'X-Forwarded-For' in request.headers:
                query_dict = parse_qs(urlparse(request.url).query)
                query_dict['wait'] = [1]
                new_query = urlencode(query_dict, doseq=True)
                url = urlunparse(
                    urlparse(request.url)._replace(
                        netloc=request.headers['Host']
                        )._replace(query=new_query)
                ).replace('/login', '')
                app.logger.debug('Set redirect url to {}'.format(url))
                return redirect(url)
        elif path == 'event_source':
            events_close = Sse()
            events_close.add_message("Close", "Disable")
            return Response(
                events_close,
                mimetype='text/event-stream',
                content_type='text/event-stream'
            )

        return abort(404)
