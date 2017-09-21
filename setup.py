#!/usr/bin/env python

from setuptools import setup


if __name__ == '__main__':
    setup(
        name='serverfiles',
        description="An utility that accesses files on a HTTP server and stores them locally for reuse.",
        author='Bioinformatics Laboratory, FRI UL',
        author_email='marko.toplak@fri.uni-lj.si',
        packages=["serverfiles"],
        install_requires=[
            'requests>=2.11.1',
        ],
        version='0.2.1',
        zip_safe=False,
        test_suite="tests.suite"
    )
