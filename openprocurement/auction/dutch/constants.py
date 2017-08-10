from datetime import timedelta
from decimal import Decimal


PROCUREMENT_METHOD_TYPE = 'dgfNew'  # XXX TODO ProcurementMethodTypes for Dutch Auction
REQUEST_QUEUE_SIZE = -1
REQUEST_QUEUE_TIMEOUT = 32
# DUTCH_TIMEDELTA = timedelta(hours=5, minutes=15)
DUTCH_TIMEDELTA = timedelta(minutes=10)
DUTCH_ROUNDS = 70
DUTCH_DOWN_STEP = Decimal('0.01')
MULTILINGUAL_FIELDS = ["title", "description"]
ADDITIONAL_LANGUAGES = ["ru", "en"]
FIRST_PAUSE = timedelta(seconds=30)
DUTCH = 'dutch'
SEALEDBID = 'sealedbid'
BESTBID = 'bestbid'
INVALIDATE_GRANT = timedelta(0, 230)
FIRST_PAUSE_SECONDS = timedelta(seconds=30)
LAST_PAUSE_SECONDS = timedelta(seconds=30)
