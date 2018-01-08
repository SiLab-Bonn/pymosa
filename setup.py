#!/usr/bin/env python
from setuptools import setup, find_packages  # This setup relies on setuptools since distutils is insufficient and badly hacked code

version = '0.0.1'
author = 'Yannick Dieter'
author_email = 'dieter@physik.uni-bonn.de'

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
    name='pymosa',
    version=version,
    description='Readout of up to six Mimosa26 silicon detector planes.',
    url='https://github.com/SiLab-Bonn/pymosa',
    license='MIT License',
    long_description='',
    author=author,
    maintainer=author,
    author_email=author_email,
    maintainer_email=author_email,
    packages=find_packages(),
    setup_requires=['setuptools'],
    install_requires=required,
    include_package_data=True,  # accept all data files and directories matched by MANIFEST.in or found in source control
    package_data={'': ['README.*', 'VERSION'], 'docs': ['*'], 'examples': ['*']},
    keywords=['silicon', 'detector', 'telescope', 'Mimosa26', 'EUDET'],
    platforms='any'
)
