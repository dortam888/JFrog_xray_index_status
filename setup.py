#!/usr/bin/env python

from setuptools import setup

setup(
    name='jfrog-xray_index_status',
    version='1.0',
    description='Checking the index status of the repositories and alert in case of percantage down from threshold',
    author='dort',
    author_email='dort@jfrog.com',
    url='https://github.com/dortam888/JFrog_xray_index_status',
    packages=['indexed_health_check'],
    install_requires=['pandas', 'requests']
)
