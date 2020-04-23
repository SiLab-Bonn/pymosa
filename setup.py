#!/usr/bin/env python
from setuptools import setup, find_packages  # This setup relies on setuptools since distutils is insufficient and badly hacked code
import pkg_resources

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
    setup_requires=['setuptools', 'online_monitor>=0.4.2<0.5'],
    include_package_data=True,  # accept all data files and directories matched by MANIFEST.in or found in source control
    keywords=['silicon', 'detector', 'telescope', 'Mimosa26', 'EUDET'],
    platforms='any',
    entry_points={
        'console_scripts': [
            'pymosa = pymosa.m26:main',
            'pymosa_monitor = pymosa.online_monitor.start_pymosa_online_monitor:main',
        ]
    },
)

# FIXME: bad practice to put code into setup.py
# Add the online_monitor Pymosa plugins
try:
    import os
    import pymosa
    from online_monitor.utils import settings
    # Get the absoulte path of this package
    package_path = os.path.dirname(pymosa.__file__)
    # Add online_monitor plugin folder to entity search paths
    settings.add_producer_sim_path(os.path.join(package_path, 'online_monitor'))
    settings.add_converter_path(os.path.join(package_path, 'online_monitor'))
    settings.add_receiver_path(os.path.join(package_path, 'online_monitor'))
except (ImportError, pkg_resources.DistributionNotFound):
    pass
