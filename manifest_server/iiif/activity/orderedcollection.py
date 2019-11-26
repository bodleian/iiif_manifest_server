from typing import List, Dict, Optional
import math

import serpy
import pysolr

from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import IIIF_ASTREAMS_CONTEXT, get_identifier
from manifest_server.helpers.solr_connection import SolrConnection


def create_ordered_collection(request, req_id: str, config: Dict) -> Optional[Dict]:  # pylint: disable-msg=unused-argument
    """
    Creates the root object for Activity Stream responses. It is a minimal object,
    containing only pointers to the first and last pages, and the total number
    of results.

    :param request: A Sanic request object
    :param req_id: UNUSED. Added for API compatibility with other AS response functions
    :param config: A manifest server configuration dict
    :return: A dictionary for serialization as a JSON-LD response.
    """
    fq: List = ["type:object",
                "!all_collections_id_sm:talbot"]
    fl: List = ["id", "accessioned_dt", "full_shelfmark_s"]
    # We only need the number of hits for this query, so we don't have to retrieve any documents,
    # only the total that would be returned
    rows: int = 0
    results: pysolr.Results = SolrConnection.search("*:*", fq=fq, fl=fl, rows=rows)

    if results.hits == 0:
        return None

    return OrderedCollection({'results': results}, context={
        "request": request,
        "config": config,
        "direct_request": True
    }).data


class OrderedCollection(ContextDictSerializer):
    """
    Unlike other serializers in the manifest server, this one takes a dictionary that
    has a single key, 'results', which in turn wraps a pysolr.Results instance. We query
    that instance in this serializer to work out the numbers for the ordered collection,
    but we don't actually ever need the results. (See `create_ordered_collection` above
    for the Solr query that is serialized.)
    """
    ctx = StaticField(
        label="@context",
        value=IIIF_ASTREAMS_CONTEXT
    )

    id = serpy.MethodField()

    astype = StaticField(
        label="type",
        value="OrderedCollection"
    )

    total_items = serpy.MethodField(
        label="totalItems"
    )

    first = serpy.MethodField()
    last = serpy.MethodField()

    def get_id(self, obj: Dict) -> str:  # pylint: disable-msg=unused-argument
        req = self.context.get('request')
        conf = self.context.get('config')
        streams_tmpl: str = conf['templates']['activitystream_id_tmpl']

        return get_identifier(req, 'all-changes', streams_tmpl)

    def get_total_items(self, obj: Dict) -> int:
        return obj.get('results').hits

    def get_first(self, obj: Dict) -> Dict:  # pylint: disable-msg=unused-argument
        req = self.context.get('request')
        cfg = self.context.get('config')
        page_tmpl: str = cfg['templates']['activitystream_id_tmpl']

        return {
            "id": get_identifier(req, 'page-0', page_tmpl),
            "type": "OrderedCollectionPage"
        }

    def get_last(self, obj: Dict) -> Dict:
        req = self.context.get('request')
        cfg = self.context.get('config')

        pagesize: int = int(cfg['solr']['pagesize'])
        hits: int = int(obj.get('results').hits)
        page_no: int = math.floor(hits / pagesize)
        page_id: str = f"page-{page_no}"
        page_tmpl: str = cfg['templates']['activitystream_id_tmpl']

        return {
            "id": get_identifier(req, page_id, page_tmpl),
            "type": "OrderedCollectionPage"
        }
