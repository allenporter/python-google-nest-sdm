
from setuptools import setup

version = '0.0.1'

setup(name='google_nest_sdm',
      version=version,
      description='Python API for talking to Google Nest using the SDM API',
      keywords='nest',
      author='Allen Porter',
      author_email='allen.porter@gmail.com',
      url='https://github.com/allenporter/python-google-nest-sdm',
      packages=['google_nest_sdm'],
      install_requires=[
          'asyncio==3.4.3',
          'aiohttp==3.6.2',
      ])
