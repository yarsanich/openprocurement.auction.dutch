from datetime import timedelta
from decimal import Decimal

BIDS_KEYS_FOR_COPY = ("bidder_id", "amount", "time", "dutch_winner")
PROCUREMENT_METHOD_TYPE = 'dgfInsider'
REQUEST_QUEUE_SIZE = -1
REQUEST_QUEUE_TIMEOUT = 32
# DUTCH_TIMEDELTA = timedelta(hours=5, minutes=15)

DUTCH_ROUNDS = 81
DUTCH_DOWN_STEP = Decimal('0.01')
MULTILINGUAL_FIELDS = ["title", "description"]
ADDITIONAL_LANGUAGES = ["ru", "en"]


PRESTARTED = 'pre-started'
DUTCH = 'dutch'
PRESEALEDBID = 'pre-sealedbid'
SEALEDBID = 'sealedbid'
PREBESTBID = 'pre-bestbid'
BESTBID = 'bestbid'
END = 'announcement'

INVALIDATE_GRANT = timedelta(0, 230)

DUTCH_TIMEDELTA = timedelta(minutes=405)
FIRST_PAUSE = timedelta(seconds=30)
FIRST_PAUSE_SECONDS = timedelta(seconds=5)
LAST_PAUSE_SECONDS = timedelta(seconds=5)
END_DUTCH_PAUSE = timedelta(seconds=30)
SEALEDBID_TIMEDELTA = timedelta(minutes=10)
BESTBID_TIMEDELTA = timedelta(minutes=5)
END_PHASE_PAUSE = timedelta(seconds=20)
