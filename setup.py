import os
from setuptools import setup, find_packages

VERSION = '1.0.4'
INSTALL_REQUIRES = [
    'setuptools',
    'simplejson',
    'openprocurement.auction'
]
EXTRAS_REQUIRE = {
    'test': [
        'pytest',
        'pytest-cov'
    ]
}
ENTRY_POINTS = {
    'console_scripts': [
        'auction_insider = openprocurement.auction.insider.cli:main',
    ],
    'openprocurement.auction.components': [
        'dutch = openprocurement.auction.insider.includeme:dutch_components'
    ],
    'openprocurement.auction.routes': [
        'dutch = openprocurement.auction.insider.includeme:dutch_routes'
    ],
    'openprocurement.auction.robottests': [
        'insider = openprocurement.auction.insider.tests.functional.main:includeme'
    ]
}

setup(name='openprocurement.auction.insider',
      version=VERSION,
      description="",
      long_description=open(os.path.join("docs", "HISTORY.txt")).read(),
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
      url='https://github.com/yarsanich/openprocurement.auction.insider',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['openprocurement', 'openprocurement.auction'],
      include_package_data=True,
      zip_safe=False,
      install_requires=INSTALL_REQUIRES,
      extras_require=EXTRAS_REQUIRE,
      entry_points=ENTRY_POINTS
      )
