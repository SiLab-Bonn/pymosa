# http://stackoverflow.com/questions/17583443/what-is-the-correct-way-to-share-package-version-with-setup-py-and-the-package
from pkg_resources import get_distribution, DistributionNotFound

try:
    __version__ = get_distribution('pymosa').version
except DistributionNotFound:
    __version__ = '(local)'
