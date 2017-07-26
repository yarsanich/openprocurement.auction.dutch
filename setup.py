import os
from setuptools import setup, find_packages

VERSION = '0.1.0'
INSTALL_REQUIRES = [
    'setuptools',
    'openprocurement.auction',
    'openprocurement.auction.worker'
]
EXTRAS_REQUIRE = {
    'test': [
        'pytest',
        'pytest-cov'
    ]
}
ENTRY_POINTS = {
    'console_scripts': [
        'auction_dutch = openprocurement.auction.dutch.cli:main',
    ],
    # XXX TODO procurementMethodType for Dutch
    # 'openprocurement.auction.auctions': [
    #     'esco.EU = openprocurement.auction.esco.includeme:includeme'
    # ],
    'openprocurement.auction.robottests': [
        'dutch_tests = openprocurement.auction.dutch.tests.functional.main:includeme'
    ]
}

setup(name='openprocurement.auction.dutch',
      version=VERSION,
      description="",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
      ],
      keywords='',
      author='Quintagroup, Ltd.',
      author_email='info@quintagroup.com',
      license='Apache License 2.0',
      url='https://github.com/yarsanich/openprocurement.auction.dutch',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['openprocurement', 'openprocurement.auction'],
      include_package_data=True,
      zip_safe=False,
      install_requires=INSTALL_REQUIRES,
      extras_require=EXTRAS_REQUIRE,
      entry_points=ENTRY_POINTS
      )
