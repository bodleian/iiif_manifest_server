import re
from abc import abstractmethod
from typing import Dict, Optional, List, Pattern

import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier, IIIF_V3_CONTEXT
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr import SolrManager, SolrResult
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.iiif.v3.manifests.annotation import ImageAnnotation, TextAnnotation

SURFACE_ID_SUB: Pattern = re.compile(r"_surface")


def create_v3_annotation_page(request, annotation_page_id: str, config: Dict) -> Optional[Dict]:

    fq = [f'id:"{annotation_page_id}_surface" OR id:{annotation_page_id}']
    fl = ['*,[child parentFilter="type:surface OR type:annotationpage" childFilter="type:image"]']
    sort = "sort_i asc"

    record = SolrConnection.search("*:*", fq=fq, fl=fl, sort=sort, rows=1)

    if record.hits == 0:
        return None

    annopage_record: Dict = record.docs[0]
    annopage: BaseAnnotationPage

    if annopage_record['type'] == "surface":
        annopage = ImageAnnotationPage(annopage_record, context={"request": request,
                                                                 "config": config,
                                                                 "direct_request": True})
    else:
        annopage = TextAnnotationPage(annopage_record, context={"request": request,
                                                                "config": config,
                                                                "direct_request": True})
    return annopage.data


class BaseAnnotationPage(ContextDictSerializer):
    ctx = serpy.MethodField(
        label="@context"
    )

    aid = serpy.MethodField(
        label="id"
    )
    atype = StaticField(
        label="type",
        value="AnnotationPage"
    )

    items = serpy.MethodField()
    part_of = serpy.MethodField(
        label="partOf"
    )

    def get_aid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        annopage_tmpl: str = cfg['templates']['annopage_id_tmpl']

        # Surfaces have the suffix "_surface" in Solr. Strip it off for this identifier
        # this isn't necessary for annotationpage ids, but also won't affect them
        annopage_id: str = re.sub(SURFACE_ID_SUB, "", obj.get("id"))

        return get_identifier(req, annopage_id, annopage_tmpl)

    def get_ctx(self, obj: SolrResult) -> Optional[List]:  # pylint: disable-msg=unused-argument
        """
        If the resource is requested directly (instead of embedded in a manifest)
        return the context object; otherwise it will inherit the context of the parent.

        Note that the 'direct_request' context object is not passed down to children,
        so it will only appear in a top-level object.
        :param obj: Dictionary object to be serialized
        :return: List containing the appropriate context objects.
        """
        direct_request: bool = self.context.get('direct_request')
        return IIIF_V3_CONTEXT if direct_request else None

    @abstractmethod
    def get_items(self, obj: SolrResult) -> List[Dict]:
        """
        Return a list of Annotations for this page - the type of annotation will depend on the AnnotationPage subclass
        :param obj:
        :return:
        """

    def get_part_of(self, obj: SolrResult) -> Optional[List]:
        """When requested directly, give a within parameter to point back to
           the parent manuscript.
        """
        direct_request: bool = self.context.get('direct_request', False)

        if not direct_request:
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')

        manifest_tmpl: str = cfg['templates']['manifest_id_tmpl']
        wid: str = get_identifier(req, obj.get('object_id'), manifest_tmpl)

        # get object shelfmark for the label
        fq = [f'id:"{obj.get("object_id")}"', 'type:object']
        fl = ['full_shelfmark_s']

        res = SolrConnection.search(q='*:*', fq=fq, fl=fl, rows=1)

        if res.hits == 0:
            return None

        object_record = res.docs[0]

        return [{
            "id": wid,
            "type": "Manifest",
            "label": object_record.get('full_shelfmark_s')
        }]


class ImageAnnotationPage(BaseAnnotationPage):
    def get_items(self, obj: SolrResult) -> List[Dict]:
        return ImageAnnotation(obj.get('_childDocuments_'),
                               context={"request": self.context.get('request'),
                                        "config": self.context.get('config')}, many=True).data


class TextAnnotationPage(BaseAnnotationPage):
    label = serpy.StrField(
        attr="label_s"
    )

    def get_items(self, obj: SolrResult) -> List[Dict]:
        manager: SolrManager = SolrManager(SolrConnection)
        fq: List = ["type:annotation", f'annotationpage_id:"{obj["id"]}"']
        fl: List = ["*", "[child parentFilter=type:annotation childFilter=type:annotation_body]"]
        manager.search("*:*", fq=fq, fl=fl, rows=100)

        if manager.hits == 0:
            return []

        return TextAnnotation(list(manager.results), context={"request": self.context.get('request'),
                                                              "config": self.context.get('config')}, many=True).data
