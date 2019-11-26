import logging
from typing import Dict, Optional

import pysolr
import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier, IIIF_V2_CONTEXT
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr import SolrManager, SolrResult
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.iiif.v2 import Canvas

log = logging.getLogger(__name__)


def create_v2_sequence(request, sequence_id: str, config: Dict) -> Optional[Dict]:
    record: pysolr.Results = SolrConnection.search("*:*", fq=["type:object", f"id:{sequence_id}"], rows=1)

    if record.hits == 0:
        return None

    object_record = record.docs[0]
    sequence: Sequence = Sequence(object_record, context={"request": request,
                                                          "config": config,
                                                          "direct_request": True})

    return sequence.data


class Sequence(ContextDictSerializer):
    ctx = serpy.MethodField(
        label="@context"
    )
    sid = serpy.MethodField(
        label="@id"
    )
    stype = StaticField(
        label="@type",
        value="sc:Sequence"
    )
    label = StaticField(
        value="Default"
    )
    canvases = serpy.MethodField()

    def get_ctx(self, obj: SolrResult) -> Optional[str]:  # pylint: disable-msg=unused-argument
        direct_request: bool = self.context.get('direct_request')
        return IIIF_V2_CONTEXT if direct_request else None

    def get_sid(self, obj: Dict) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        obj_id = obj.get('id')
        sequence_tmpl = cfg['templates']['sequence_id_tmpl']

        return get_identifier(req, obj_id, sequence_tmpl)

    def get_canvases(self, obj: SolrResult) -> Optional[Dict]:
        req = self.context.get('request')
        cfg = self.context.get('config')
        obj_id = obj.get('id')

        # Check if the canvases have annotations. We don't actually
        # need to retrieve them, just get the number of hits.
        has_annotations_res = SolrConnection.search(
            "*:*",
            fq=["type:annotationpage", f"object_id:{obj_id}"],
            rows=0
        )
        has_annotations = has_annotations_res.hits > 0

        manager: SolrManager = SolrManager(SolrConnection)
        fq = ["type:surface", f"object_id:{obj_id}"]
        sort = "sort_i asc"
        fl = ["*,[child parentFilter=type:surface childFilter=type:image]"]
        rows: int = 100
        manager.search("*:*", fq=fq, fl=fl, sort=sort, rows=rows)

        if manager.hits == 0:
            return None

        return Canvas(manager.results, context={'request': req,
                                                'config': cfg,
                                                'has_annotations': has_annotations}, many=True).data
