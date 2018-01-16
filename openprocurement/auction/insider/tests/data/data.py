# -*- coding: utf-8 -*-
tender_data = {
    "data": {
        "tenderID": "UA-11111",
        "description": "Tender Description",
        "title": "Tender Title",
        "procurementMethodType": "dgfInsider",
        "minimalStep": {
            "currency": "UAH",
            "amount": 35000.0,
            "valueAddedTaxIncluded": True
        },
        "auctionPeriod": {
            "startDate": "2016-12-26T15:50:14.003746+02:00",
            "endDate": None
        },
        "auctionParameters": {
            "type": "dutch",
            "steps": 80
        },
        "bids": [{
            "date": "2014-11-19T08:22:21.726234+00:00",
            "id": "c26d9eed99624c338ce0fca58a0aac32",
            "value": {
                "currency": None,
                "amount": 0,
                "valueAddedTaxIncluded": True
            },
            "tenderers": [{
                "contactPoint": {
                    "telephone": "+380139815286",
                    "name": "Эммануил Капустина",
                    "email": "automation+4077486456@smartweb.com.ua"
                },
                "identifier": {
                    "scheme": "UA-EDR",
                    "id": "46171",
                    "uri": "http://9665642342.promtest.ua",
                    "legalName": "Фомин-Александрова"
                },
                "name":
                    "Концертний заклад культури 'Муніципальна академічна " \
                    "чоловіча хорова капела ім. Л.М. Ревуцького'",
                "address": {
                    "postalCode": "849999",
                    "countryName": "Україна",
                    "streetAddress": "6973 Афанасьева Mountain Apt. 965",
                    "region": "Донецька область",
                    "locality": "Donetsk"
                }
            }]},
            {
            "date": "2014-11-19T08:22:24.038426+00:00",
            "id": "e4456d02263441ffb2f00ceafa661bb2",
            "value": {
                    "currency": None,
                    "amount": 0,
                    "valueAddedTaxIncluded": True
            },
            "tenderers": [{
                "contactPoint": {
                    "telephone": "+380139815286",
                    "name": "Эммануил Капустина",
                    "email": "automation+4077486456@smartweb.com.ua"
                },
                "identifier": {
                    "scheme": "UA-EDR",
                    "id": "46171",
                    "uri": "http://9665642342.promtest.ua",
                    "legalName": "Фомин-Александрова"
                },
                "name": "КОМУНАЛЬНЕ ПІДПРИЄМСТВО 'КИЇВПАСТРАНС'",
                "address": {
                    "postalCode": "849999",
                    "countryName": "Україна",
                    "streetAddress": "6973 Афанасьева Mountain Apt. 965",
                    "region": "Донецька область",
                    "locality": "Donetsk"
                }
            }]}
        ],
        "procuringEntity": {
            "identifier": {
                "scheme": "https://ns.openprocurement.org/ua/edrpou",
                "id": "21725150",
                "uri": "http://sch10.edu.vn.ua/",
                "legalName":
                    "Заклад 'Загальноосвітня школа І-ІІІ ступенів № 10 " \
                    "Вінницької міської ради'"
            },
            "name": "ЗОСШ #10 м.Вінниці",
            "address": {
                "postalCode": "21027",
                "countryName": "Україна",
                "streetAddress": "вул. Стахурського. 22",
                "region": "м. Вінниця",
                "locality": "м. Вінниця"
            }
        },
        "items": [{
            "unit": {
                "name": "item"
            },
            "additionalClassifications": [{
                "scheme": "ДКПП",
                "id": "55.51.10.300",
                "description": "Послуги шкільних їдалень"
            }],
            "description": "Послуги шкільних їдалень",
            "classification": {
                "scheme": "CPV",
                "id": "55523100-3",
                "description": "Послуги з харчування у школах"
            },
            "quantity": 5
        }],
        "dateModified": "2014-11-19T08:22:24.866669+00:00",
        "id": "11111111111111111111111111111111",
        "value": {
            "amount": 35000,
            "valueAddedTaxIncluded": False,
            "currency": "UAH"
        }
    }
}


test_organization = {
    "name": u"Державне управління справами",
    "identifier": {
        "scheme": u"UA-EDR",
        "id": u"00037256",
        "uri": u"http://www.dus.gov.ua/"
    },
    "address": {
        "countryName": u"Україна",
        "postalCode": u"01220",
        "region": u"м. Київ",
        "locality": u"м. Київ",
        "streetAddress": u"вул. Банкова, 11, корпус 1"
    },
    "contactPoint": {
        "name": u"Державне управління справами",
        "telephone": u"0440000000"
    }
}


test_auction_document = {
    'current_phase': 'dutch',
    'current_stage': 3,
    'stages': [
        {
            "start": "2017-07-14T11:05:46+03:00",
            "type": "pause",
            "stage": "pause"
        },
        {
            'amount': 10000
        },
        {
            'amount': 9000
        },
        {
            'amount': 8000
        },
    ]
}

new_bid_from_cdb = {
        "date": "2014-11-19T08:22:21.726234+00:00",
        "id": "11111111111111111111111111111111",
        "value": {
            "currency": None,
            "amount": 0,
            "valueAddedTaxIncluded": True
        },
        "tenderers": [{
            "contactPoint": {
                "telephone": "+380961089777",
                "name": "Іларіо Зірвиголова",
                "email": "ilario_headchick@headhouse.com"
            },
            "identifier": {
                "scheme": "UA-EDR",
                "id": "46171",
                "uri": "http://9665642342.promtest.ua",
                "legalName": "Фомин-Александрова"
            },
            "name":
                "Заклад народної магії 'Магія повсюди'",
            "address": {
                "postalCode": "46000",
                "countryName": "Україна",
                "streetAddress": "6973 Shadow Apt. 965",
                "region": "Тернопільська область",
                "locality": "Ternopil"
            }
        }]}


bidders = {
        'dutch_bidder': {
            'bidder_id': 'f7c8cd1d56624477af8dc3aa9c4b3ea3',
            'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', '')
        },
        'sealedbid_bidder': {
            'bidder_id': 'f7c8cd1d56624477af8dc3aa9c4b3ea4',
            'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4usZZZ', '')
        },
        'bestbid_bidder': {
            'bidder_id': 'f7c8cd1d56624477af8dc3aa9c4b3ea5',
            'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4usYYY', '')
        },
        'new_valid_bidder': {
            'bidder_id': '1' * 32,
            'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4us111', '')
        },
        'invalid_bidder': {
            'bidder_id': '2' * 32,
            'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4us222', '')
        }
    }

parametrize_on_dutch_test = [
    (bidders['dutch_bidder'],
     {
         u'status': u'ok',
         u'data': {
             u'bid': 33250,
             u'bidder_id': bidders['dutch_bidder']['bidder_id']
        }
     }),
    (bidders['sealedbid_bidder'],
     {
         u'status': u'ok',
         u'data': {
             u'bid': 33250,
             u'bidder_id': bidders['sealedbid_bidder']['bidder_id']
        }
     }),
    (bidders['bestbid_bidder'],
     {
         u'status': u'ok',
         u'data': {
             u'bid': 33250,
             u'bidder_id': bidders['bestbid_bidder']['bidder_id']
        }
     }),
    (bidders['new_valid_bidder'],
     {
         u'status': u'ok',
         u'data': {
             u'bid': 33250,
             u'bidder_id': bidders['new_valid_bidder']['bidder_id']
        }
     }),
    (bidders['invalid_bidder'],
     {u'status': u'failed', u'errors': [[u'Bad bidder!']]})
]


parametrize_on_sealbid_test = [
    (bidders['sealedbid_bidder'],
     {
         u'status': u'ok',
         u'data': {
             u'bid': 33350,
             u'bidder_id': bidders['sealedbid_bidder']['bidder_id']
        }
     }),
    (bidders['bestbid_bidder'],
     {
         u'status': u'ok',
         u'data': {
             u'bid': 33350,
             u'bidder_id': bidders['bestbid_bidder']['bidder_id']
        }
     }),
    (bidders['new_valid_bidder'],
     {
         u'status': u'ok',
         u'data': {
             u'bid': 33350,
             u'bidder_id': bidders['new_valid_bidder']['bidder_id']
        }
     }),
    (bidders['invalid_bidder'],
     {
         u'status': u'ok',
         u'data': {
             u'bid': 33350,
             u'bidder_id': bidders['invalid_bidder']['bidder_id']
         }
     })
]