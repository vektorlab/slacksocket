from setuptools import setup
from slacksocket import __version__

setup(name='slacksocket',
      version=__version__,
      packages=['slacksocket'],
      description='Slack RTM API Websocket client',
      author='Bradley Cicenas',
      author_email='bradley.cicenas@gmail.com',
      url='https://github.com/bcicen/slacksocket',
      install_requires=['requests >= 2.2.1','websocket-client >= 0.11.0'],
      license='http://opensource.org/licenses/MIT',
      classifiers=(
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License ',
          'Natural Language :: English',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
      ),
      keywords='slack rtm websocket api')
