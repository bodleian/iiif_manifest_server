import re
from typing import List, Any, Optional, Dict, Pattern
import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier, IIIF_V2_CONTEXT
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr import SolrManager, SolrResult
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.iiif.v2.manifests.annotation import TextAnnotation

SURFACE_ID_SUB: Pattern = re.compile(r"_surface")


def create_v2_annotation_list(request: Any, annotation_page_id: str, config: Dict) -> Optional[Dict]:
    """
    :param request: A sanic request object
    :param annotation_page_id: An annotation page to retrieve annotations for
    :param config: The configuration dict
    :return: A Dict representing a IIIF-serialized Annotation List.
    """
    fq: List = [f'id:"{annotation_page_id}"']
    fl = ["id,label_s"]
    record = SolrConnection.search(q="*:*", fq=fq, fl=fl, rows=1)

    if record.hits == 0:
        return None

    annotation_list: AnnotationList = AnnotationList(record.docs[0], context={"request": request,
                                                                              "config": config})
    return annotation_list.data


class AnnotationList(ContextDictSerializer):
    """
        Serializes a list of annotations
    """
    cid = serpy.MethodField(
        label="@id"
    )

    ctx = StaticField(
        value=IIIF_V2_CONTEXT,
        label="@context"
    )

    ctype = StaticField(
        label="@type",
        value="sc:AnnotationList"
    )

    label = serpy.StrField(attr='label_s')

    resources = serpy.MethodField()

    def get_cid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')

        tmpl: str = cfg['templates']['annolist_id_tmpl']

        return get_identifier(req, obj['id'], tmpl)

    def get_resources(self, obj: SolrResult) -> List[Dict]:
        req = self.context.get('request')
        cfg = self.context.get('config')

        manager: SolrManager = SolrManager(SolrConnection)
        fq: List = ["type:annotation", f'annotationpage_id:"{obj["id"]}"']
        fl: List = ["*", "[child parentFilter=type:annotation childFilter=type:annotation_body]"]
        manager.search("*:*", fq=fq, fl=fl, rows=100)

        if manager.hits == 0:
            return []

        return TextAnnotation(list(manager.results), context={'request': req,
                                                              'config': cfg}, many=True).data
