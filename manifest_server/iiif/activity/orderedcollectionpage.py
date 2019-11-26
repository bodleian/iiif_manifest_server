from typing import List, Dict, Optional
import math

import serpy
import pysolr
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import IIIF_ASTREAMS_CONTEXT, get_identifier
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.iiif.activity.activity import Activity


def create_ordered_collection_page(request, page_id: int, config: Dict) -> Optional[Dict]:
    fq: List = ["type:object",
                "!all_collections_id_sm:talbot"]
    sort: str = "accessioned_dt asc, shelfmark_sort_ans asc, id asc"
    fl: List = ["id", "accessioned_dt", "full_shelfmark_s"]
    rows: int = config['solr']['pagesize']
    start: int = page_id * int(rows)

    results: pysolr.Results = SolrConnection.search("*:*", fq=fq, fl=fl, sort=sort, rows=rows, start=start)

    if results.hits == 0:
        return None

    return OrderedCollectionPage({'results': results}, context={'request': request,
                                                                'config': config,
                                                                'page_id': page_id,
                                                                'direct_request': True}).data


class OrderedCollectionPage(ContextDictSerializer):
    ctx = StaticField(
        label="@context",
        value=IIIF_ASTREAMS_CONTEXT
    )

    id = serpy.MethodField()

    astype = StaticField(
        label="type",
        value="OrderedCollectionPage"
    )

    start_index = serpy.MethodField(
        label="startIndex"
    )

    part_of = serpy.MethodField(
        label="partOf"
    )

    prev = serpy.MethodField()
    next = serpy.MethodField()

    ordered_items = serpy.MethodField(
        label="orderedItems"
    )

    def get_id(self, obj: Dict) -> str:  # pylint: disable-msg=unused-argument
        req = self.context.get('request')
        conf = self.context.get('config')
        streams_tmpl: str = conf['templates']['activitystream_id_tmpl']
        page_id: int = self.context.get('page_id')

        return get_identifier(req, f"page-{page_id}", streams_tmpl)

    def get_part_of(self, obj: Dict) -> Dict:  # pylint: disable-msg=unused-argument
        req = self.context.get('request')
        conf = self.context.get('config')
        streams_tmpl: str = conf['templates']['activitystream_id_tmpl']

        parent_id = get_identifier(req, 'all-changes', streams_tmpl)

        return {
            "id": parent_id,
            "type": "OrderedCollection"
        }

    def get_start_index(self, obj: Dict) -> int:  # pylint: disable-msg=unused-argument
        cfg = self.context.get('config')

        pagesize: int = int(cfg['solr']['pagesize'])
        page_id: int = self.context.get('page_id')

        # The start index for the page is always one more than the end index of the previous.
        idx: int = (pagesize * page_id) + 1

        return idx

    def get_prev(self, obj: Dict) -> Optional[Dict]:  # pylint: disable-msg=unused-argument
        req = self.context.get('request')
        cfg = self.context.get('config')

        page_id: int = self.context.get("page_id")
        prev_page: int = page_id - 1

        # If we're on the first page, don't show the 'prev' key
        if prev_page < 0:
            return None

        page_tmpl: str = cfg['templates']['activitystream_id_tmpl']
        prev_page_id: str = get_identifier(req, f"page-{prev_page}", page_tmpl)

        return {
            "id": prev_page_id,
            "type": "OrderedCollectionPage"
        }

    def get_next(self, obj: Dict) -> Optional[Dict]:  # pylint: disable-msg=unused-argument
        req = self.context.get('request')
        cfg = self.context.get('config')

        hits: int = obj.get('results').hits
        pagesize: int = int(cfg['solr']['pagesize'])

        next_page = self.context.get("page_id") + 1
        last_page = math.floor(hits / pagesize)

        # If we're on the last page, don't show the next key
        if next_page > last_page:
            return None

        page_tmpl: str = cfg['templates']['activitystream_id_tmpl']
        next_page_id: str = get_identifier(req, f"page-{next_page}", page_tmpl)

        return {
            "id": next_page_id,
            "type": "OrderedCollectionPage"
        }

    def get_ordered_items(self, obj: Dict) -> Dict:
        activities: List = obj.get('results').docs

        return Activity(activities, many=True, context={'request': self.context.get('request'),
                                                        'config': self.context.get('config')}).data
