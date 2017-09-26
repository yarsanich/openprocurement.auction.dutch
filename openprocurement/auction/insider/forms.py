# -*- coding: utf-8 -*-
from flask import request, session, current_app as app
from decimal import ROUND_HALF_UP, Decimal

from wtforms import Form, StringField, DecimalField
from wtforms.validators import ValidationError, DataRequired
from datetime import datetime
from pytz import timezone
import wtforms_json

from openprocurement.auction.utils import prepare_extra_journal_fields
from openprocurement.auction.insider.constants import DUTCH, SEALEDBID, BESTBID
from openprocurement.auction.insider.utils import lock_bids, get_dutch_winner


wtforms_json.init()


def validate_bid_value(form, field):
    """
    On Dutch Phase: Bid must be equal current dutch amount.
    On Sealed Bids Phase: Bid must be greater then current dutch amount.
    On Best Bid Phase: Bid must be greater then current dutch amount.
    """
    phase = form.document.get('current_phase')
    if phase == DUTCH:
        try:
            current_stage = form.document['current_stage']
            current_amount = form.document['stages'][current_stage].get(
                'amount',
            )
            if not isinstance(current_amount, Decimal):
                current_amount = Decimal(str(current_amount))
            if current_amount != field.data:
                message = u"Passed value doesn't match"\
                          " current amount={}".format(current_amount)
                raise ValidationError(message)
            return True
        except KeyError as e:
            form[field.name].errors.append(e.message)
            raise e
    elif phase == BESTBID:
        # TODO: one percent step validation
        winner = get_dutch_winner(form.document)
        current_amount = winner.get('amount')
        if not isinstance(current_amount, Decimal):
            current_amount = Decimal(str(current_amount))
        if field.data != Decimal('-1') and (field.data <= current_amount):
            message = u'Bid value can\'t be less or equal current amount'
            form[field.name].errors.append(message)
            raise ValidationError(message)
        return True
    elif phase == SEALEDBID:
        if field.data <= Decimal('0.0') and field.data != Decimal('-1'):
            message = u'To low value'
            form[field.name].errors.append(message)
            raise ValidationError(message)
        winner = get_dutch_winner(form.document)
        dutch_winner_value = winner.get('amount')

        if not isinstance(dutch_winner_value, Decimal):
            dutch_winner_value = Decimal(str(dutch_winner_value))
        if field.data != Decimal('-1') and (field.data <= dutch_winner_value):
            message = u'Bid value can\'t be less or equal current amount'
            form[field.name].errors.append(message)
            raise ValidationError(message)
        return True
    else:
        raise ValidationError(
            'Not allowed to post bid on current'
            ' ({}) phase'.format(phase)
        )


def validate_bidder_id(form, field):
    phase = form.document.get('current_phase')
    if phase == BESTBID:
        try:
            dutch_winner = get_dutch_winner(form.document)
            if dutch_winner and dutch_winner['bidder_id'] != field.data:
                message = u'bidder_id don\'t match with dutchWinner.bidder_id'
                form[field.name].errors.append(message)
                raise ValidationError(message)
            return True
        except KeyError as e:
            form[field.name].errors.append(e)
            raise e
    elif phase == SEALEDBID:
        dutch_winner = get_dutch_winner(form.document)
        if dutch_winner.get('bidder_id') == field.data:
            message = u'Not allowed to post bid for dutch winner'
            form[field.name].errors.append(message)
            raise ValidationError(message)
        return True
    elif phase == DUTCH:
        return True
    else:
        raise ValidationError(
            'Not allowed to post bid on current'
            ' ({}) phase'.format(phase)
        )


class BidsForm(Form):
    bidder_id = StringField(
        'bidder_id',
        validators=[
            DataRequired(message=u'No bidder id'),
            validate_bidder_id
        ]
    )
    bid = DecimalField(
        'bid',
        places=2,
        rounding=ROUND_HALF_UP,
        validators=[
            DataRequired(message=u'Bid amount is required'),
            validate_bid_value
        ]
    )


def form_handler():
    auction = app.config['auction']
    form = app.bids_form.from_json(request.json)
    form.auction = auction
    form.document = auction.auction_document
    current_time = datetime.now(timezone('Europe/Kiev'))
    current_phase = form.document.get('current_phase')
    if not form.validate():
        app.logger.info(
            "Bidder {} with client_id {} wants place bid {} in {}on phase {} "
            "with errors {}".format(
                request.json.get('bidder_id', 'None'),
                session.get('client_id', ''),
                request.json.get('bid', 'None'),
                current_time.isoformat(),
                current_phase,
                repr(form.errors)
            ), extra=prepare_extra_journal_fields(
                request.headers
            )
        )
        return {'status': 'failed', 'errors': form.errors}
    if current_phase == DUTCH:
        with lock_bids(auction):
            ok = auction.add_dutch_winner({
                'amount': str(form.data['bid']),
                'time': current_time.isoformat(),
                'bidder_id': form.data['bidder_id']
            })
            if not isinstance(ok, Exception):
                app.logger.info(
                    "Bidder {} with client {} has won"
                    " dutch on value {}".format(
                        form.data['bidder_id'],
                        session.get('client_id'),
                        form.data['bid']
                    )
                )
                return {"status": "ok", "data": form.data}
            else:
                app.logger.info(
                    "Bidder {} with client_id {} wants place"
                    " bid {} in {} on dutch "
                    "with errors {}".format(
                        request.json.get('bidder_id', 'None'),
                        session.get('client_id'),
                        request.json.get('bid', 'None'),
                        current_time.isoformat(),
                        repr(ok)
                    ),
                    extra=prepare_extra_journal_fields(request.headers)
                )
                return {"status": "failed", "errors": [repr(ok)]}

    elif current_phase == SEALEDBID:
        try:
            auction.bids_queue.put({
                'amount': str(form.data['bid']),
                'time': current_time.isoformat(),
                'bidder_id': form.data['bidder_id']
            })
            return {"status": "ok", "data": form.data}
        except Exception as e:
            return {"status": "failed", "errors": [repr(e)]}
    elif current_phase == BESTBID:
        ok = auction.add_bestbid({
            'amount': str(form.data['bid']),
            'time': current_time.isoformat(),
            'bidder_id': form.data['bidder_id']
        })
        if not isinstance(ok, Exception):
            app.logger.info(
                "Bidder {} with client {} has won dutch on value {}".format(
                    form.data['bidder_id'],
                    session.get('client_id'),
                    form.data['bid']
                )
            )
            return {"status": "ok", "data": form.data}
        else:
            app.logger.info(
                "Bidder {} with client_id {} wants place"
                " bid {} in {} on dutch "
                "with errors {}".format(
                    request.json.get('bidder_id', 'None'),
                    session.get('client_id'),
                    request.json.get('bid', 'None'),
                    current_time.isoformat(),
                    repr(ok)
                ),
                extra=prepare_extra_journal_fields(request.headers)
            )
            return {"status": "failed", "errors": [repr(ok)]}
    else:
        return {
            'status': 'failed',
            'errors': {
                'form': ['Bids period expired.']
            }
        }
