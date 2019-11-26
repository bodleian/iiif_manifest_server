"""
    A Singleton for a global Solr connection. Methods that wish
    to make use of a global Solr connection can import this module
    and it will give them an instance of a pysolr connection that
    they can then use to perform searches.

      >>> from manifest_server.helpers.solr_connection import SolrConnection
      >>> res = SolrConnection.search("MS Bodl 266")

"""
from typing import Dict
import yaml
import logging

import pysolr


log = logging.getLogger(__name__)

config: Dict = yaml.safe_load(open('configuration.yml', 'r'))

solr_url = config['solr']['server']
SolrConnection: pysolr.Solr = pysolr.Solr(solr_url, search_handler='iiif')

log.debug('Solr connection set to %s', solr_url)
