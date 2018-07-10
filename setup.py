#!/usr/bin/env python
from setuptools import setup, find_packages  # This setup relies on setuptools since distutils is insufficient and badly hacked code

version = '0.0.1'
author = 'Ivan Caicedo, Yannick Dieter, Toko Hirono, Jens Janssen, David-Leon Pohl'
author_email = 'caicedo@physik.uni-bonn.de, dieter@physik.uni-bonn.de, hirono@physik.uni-bonn.de, janssen@physik.uni-bonn.de, pohl@physik.uni-bonn.de'

with open('VERSION') as version_file:
    version = version_file.read().strip()

with open('requirements.txt') as f:
    install_requires = f.read().splitlines()

setup(
    name='pymosa',
    version=version,
    description='DAQ for Mimosa26 silicon detector planes.',
    url='https://github.com/SiLab-Bonn/pymosa',
    license='MIT License',
    long_description='',
    author=author,
    maintainer=author,
    author_email=author_email,
    maintainer_email=author_email,
    install_requires=install_requires,
    packages=find_packages(),
    setup_requires=['setuptools'],
    include_package_data=True,  # accept all data files and directories matched by MANIFEST.in or found in source control
    keywords=['silicon', 'detector', 'telescope', 'Mimosa26', 'EUDET'],
    platforms='any',
    entry_points={
        'console_scripts': [
            'pymosa = pymosa.m26:main',
            'pymosa_eudaq = pymosa.eudaq:main'
        ]
    },
)
