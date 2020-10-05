import pathlib
from setuptools import setup

VERSION = '0.1.3'

HERE = pathlib.Path(__file__).parent
README = (HERE / "README.md").read_text()

setup(name='google_nest_sdm',
      version=VERSION,
      description='Library for the Google Nest SDM API',
      long_description=README,
      long_description_content_type="text/markdown",
      keywords='google nest sdm camera therostat security doorbell',
      author='Allen Porter',
      author_email='allen@thebends.org',
      url='https://github.com/allenporter/python-google-nest-sdm',
      packages=['google_nest_sdm'],
      install_requires=[
          'aiohttp==3.6.2',
          'google-auth==1.22.0',
          'google-auth-oauthlib==0.4.1',
          'google-cloud-pubsub==2.1.0',
          'requests-oauthlib==1.3.0',
      ],
      entry_points = {
          'console_scripts': [
              'google_nest=google_nest_sdm.google_nest:main',
          ],
      },
      tests_require=[
          'pytest_aiohttp==0.3.0',
      ])
