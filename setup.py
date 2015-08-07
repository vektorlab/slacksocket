import os
import sys
from setuptools import setup

exec(open('slacksocket/version.py').read())

setup(name='slacksocket',
      version=version,
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
          'Programming Language :: Python :: 3.4',
      ),
      keywords='slack rtm websocket api')
