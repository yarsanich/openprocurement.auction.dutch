# -*- coding: utf-8 -*-
# from da
from flask import request, session, current_app as app

from wtforms import Form, FloatField, StringField
from wtforms.validators import InputRequired, ValidationError, StopValidation
from fractions import Fraction
from datetime import datetime
from pytz import timezone
import wtforms_json

from openprocurement.auction.utils import prepare_extra_journal_fields

wtforms_json.init()


def validate_bid_value(form, field):
    """
    On Dutch Phase: Bid must be equal current dutch amount.
    On Sealed Bids Phase: Bid must be greater then current dutch amount.
    On Best Bid Phase: Bid must be greater then current dutch amount.
    """
    try:
        current_amount = form.document['TODO: Назва поля, поле масив'][-1]
    except KeyError as e:
        form[field.name].errors.append(e.message)
        raise e

    if field.data <= 0.0 and field.data != -1:
        message = u'To low value'
        form[field.name].errors.append(message)
        raise ValidationError(message)

    current_phase = form.document.get('phase')
    if current_phase == 'dutch':
        if Fraction(field.data) != Fraction(current_amount):
            message = u'applyAmount don\'t match with currentDutchAmount'
            form[field.name].errors.append(message)
            raise ValidationError(message)
    elif current_phase == 'sealedBids' or current_phase == 'bestBid':
        if (Fraction(current_amount) >= Fraction(self.bid.data) and
                field.data != -1):
            message = u'Bid value can\'t be less or equal current amount'
            form[field.name].errors.append(message)
            raise ValidationError(message)
    else:
        message = u'Invalid auction phase'
        form[field.name].errors.append(message)
        raise ValidationError(message)


def validate_bidder_id(form, field):
    """
    On Dutch Phase: Bidder id is trusted.
    On Sealed Bids Phase: Bidder id must don't be equal dutchWinner.bidder_id.
    On Best Bid Phase: Bidder id must be equal dutchWinner.bidder_id.
    """
    current_phase = form.document.get('phase')
    if current_phase == 'dutch':
        return

    try:
        dutch_winner = form.document['dutchWinner']['bidder_id']
    except KeyError as e:
        form[field.name].errors.append(e)
        raise e

    if current_phase == 'sealedBids':
        if dutch_winner == field.data:
            message = u'bidder_id match with dutchWinner.bidder_id'
            form[field.name].errors.append(message)
            raise ValidationError(message)
    elif current_phase == 'bestBid':
        if dutch_winner != field.data:
            message = u'bidder_id don\'t match with dutchWinner.bidder_id'
            form[field.name].errors.append(message)
            raise ValidationError(message)
    else:
        message = u'Unknown auction phase'
        form[field.name].errors.append(message)
        raise ValidationError(message)


class BidsForm(Form):
    bidder_id = StringField(
        'bidder_id',
        validators=[
            DataRequired(message=u'No bidder id'),
            validate_bidder_id
        ]
    )
    bid = FloatField(
        'bid',
        validators=[
            DataRequired(message=u'Bid amount is required'),
            validate_bid_value
        ]
    )


def _process_form(form):
    try:
        form.validate():
        if form.data['bid'] == -1.0:
            app.logger.info(
                "Bidder {} with client_id {} canceled bids in stage {} in {} "
                "on phase {}".format(
                    form.data['bidder_id'], session['client_id'],
                    form.document['current_stage'], current_time.isoformat(),
                    form.document['phase']),
                extra=prepare_extra_journal_fields(request.headers))
        else:
            app.logger.info(
                "Bidder {} with client_id {} placed bid {} in {} on phase "
                "{}".format(
                    form.data['bidder_id'], session['client_id'],
                    form.data['bid'], current_time.isoformat(),
                    form.document['phase']),
                extra=prepare_extra_journal_fields(request.headers))
        return {'status': 'ok', 'data': form.data}
    except (ValidationError, KeyError):
        app.logger.info(
            "Bidder {} with client_id {} wants place bid {} in {}on phase {} "
            "with errors {}".format(
                request.json.get('bidder_id', 'None'), session['client_id'],
                request.json.get('bid', 'None'), current_time.isoformat(),
                form.document['phase'], repr(form.errors)),
            extra=prepare_extra_journal_fields(request.headers))
        return {'status': 'failed', 'errors': form.errors}


def form_handler():
    auction = app.config['auction']
    form = app.bids_form.from_json(request.json)
    form.document = auction.auction_document
    current_time = datetime.now(timezone('Europe/Kiev'))
    if form.document['phase'] in ['dutch', 'bestBid']:
        with auction.bids_actions:
            form_result = _process_form(form)
            if form_result['status'] = 'ok':
                # write data
                auction.add_bid(form.document['current_stage'],
                                {'amount': form.data['bid'],
                                 'bidder_id': form.data['bidder_id'],
                                 'time': current_time.isoformat()})
                if (form.document.get('dutchWinner', {}) != {} and
                        form.document['phase'] == 'dutch'):
                    form.bid.errors.append('Exist another bid')
                    form_result['status'] = 'failed'
                    form_result['errors'] = form.errors
            return form_result
    elif (form.document['phase'] == 'sealedBids' and
            current_time < auction.best_bid_phase_start):
            auction.requests_queue.put(request)
            try:
                form_result = _process_form(form)
                if form_result['status'] == 'ok':
                    auction.add_bid((
                        form.document['current_stage'],
                        {
                            'amount': form.data['bid'],
                            'bidder_id': form.data['bidder_id'],
                            'time': current_time.isoformat()
                        }
                    ))
            except:
                app.logger.critical('Error while processing request')
                form.bid.errors.append('Internal server error')
                form_result = {
                    'status': 'failed',
                    'errors': form.errors
                }
            auction.requests_queue.get()
            return form_result
    else:
        return {'status': 'failed',
               'errors': { 'form': ['Bids period expired.']}}
