from datetime import timedelta
from decimal import Decimal


PROCUREMENT_METHOD_TYPE = 'dgfNew'  # XXX TODO ProcurementMethodTypes for Dutch Auction
REQUEST_QUEUE_SIZE = -1
REQUEST_QUEUE_TIMEOUT = 32
# DUTCH_TIMEDELTA = timedelta(hours=5, minutes=15)

DUTCH_ROUNDS = 3
DUTCH_DOWN_STEP = Decimal('0.01')
MULTILINGUAL_FIELDS = ["title", "description"]
ADDITIONAL_LANGUAGES = ["ru", "en"]


PRESTARTED = 'pre-started'
DUTCH = 'dutch'
PRESEALEDBID = 'pre-sealed'
SEALEDBID = 'sealedbid'
PREBESTBID = 'pre-bestbid'
BESTBID = 'bestbid'
END = 'finish'

INVALIDATE_GRANT = timedelta(0, 230)

DUTCH_TIMEDELTA = timedelta(minutes=1)
FIRST_PAUSE = timedelta(seconds=5)
FIRST_PAUSE_SECONDS = timedelta(seconds=10)
LAST_PAUSE_SECONDS = timedelta(seconds=10)
END_DUTCH_PAUSE = timedelta(seconds=30)
SEALEDBID_TIMEDELTA = timedelta(minutes=1)
BESTBID_TIMEDELTA = timedelta(seconds=10)
END_PHASE_PAUSE = timedelta(seconds=20)
