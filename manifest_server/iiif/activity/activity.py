from typing import List, Dict, Optional

import serpy
import pysolr

from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import (
    IIIF_ASTREAMS_CONTEXT,
    get_identifier,
    IIIF_ASTREAMS_ACTOR
)
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.helpers.solr import SolrResult


def create_activity(request, manifest_id: str, config: Dict) -> Optional[Dict]:
    fq: List = ["type:object",
                f"id:{manifest_id}"]
    fl: List = ["id", "accessioned_dt", "full_shelfmark_s"]
    rows: int = 1
    results: pysolr.Results = SolrConnection.search("*:*", fq=fq, fl=fl, rows=rows)

    if results.hits == 0:
        return None

    return Activity(results.docs[0], context={'request': request,
                                              'config': config,
                                              'direct_request': True}).data


class Activity(ContextDictSerializer):
    ctx = serpy.MethodField(
        label="@context"
    )
    id = serpy.MethodField()
    # We only publish Create events (for now...)
    type = StaticField(
        value="Create"
    )
    end_time = serpy.MethodField(
        label="endTime"
    )
    object = serpy.MethodField()
    actor = StaticField(
        value=IIIF_ASTREAMS_ACTOR
    )

    def get_ctx(self, obj: SolrResult) -> Optional[List]:  # pylint: disable-msg=unused-argument
        direct: bool = self.context.get('direct_request', False)
        return IIIF_ASTREAMS_CONTEXT if direct else None

    def get_id(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        activity_create_id_tmpl: str = cfg['templates']['activitystream_create_id_tmpl']

        return get_identifier(req, obj.get('id'), activity_create_id_tmpl)

    def get_end_time(self, obj: SolrResult) -> str:
        return obj.get('accessioned_dt')

    def get_object(self, obj: SolrResult) -> Dict:
        req = self.context.get('request')
        cfg = self.context.get('config')

        manifest_tmpl: str = cfg['templates']['manifest_id_tmpl']
        mfid = get_identifier(req, obj.get('id'), manifest_tmpl)
        label: str = obj.get("full_shelfmark_s")

        return {
            "id": mfid,
            "type": "Manifest",
            "name": label
        }
