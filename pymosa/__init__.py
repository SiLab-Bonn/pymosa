# http://stackoverflow.com/questions/17583443/what-is-the-correct-way-to-share-package-version-with-setup-py-and-the-package
from pkg_resources import get_distribution, DistributionNotFound

__project__ = 'pymosa'
__version__ = None  # required for initial installation

try:
    __version__ = get_distribution(__project__).version
except DistributionNotFound:
    __version__ = __project__ + '-' + '(local)'
else:
    __version__ = __project__ + '-' + __version__