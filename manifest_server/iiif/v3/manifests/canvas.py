import logging
import re
from typing import Optional, List, Dict, Pattern

import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.metadata import v3_metadata_block, CANVAS_FIELD_CONFIG
from manifest_server.helpers.identifiers import get_identifier, IIIF_V3_CONTEXT
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr import SolrManager, SolrResult
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.iiif.v3.manifests.annotation_page import ImageAnnotationPage

log = logging.getLogger(__name__)

SURFACE_ID_SUB: Pattern = re.compile(r"_surface")


def create_v3_canvas(request, canvas_id: str, config: Dict) -> Optional[Dict]:
    """
    Creates a new canvas in response to a request. Used for directly requesting canvases.

    :param request: A Sanic request object
    :param canvas_id: An ID passed in from the URL. Note that this lacks the '_surface' suffix
    :param config: A server configuration dictionary
    :return: A V3 Canvas object
    """
    fq = ["type:surface", f"id:{canvas_id}_surface"]
    fl = ["*,[child parentFilter=type:surface childFilter=type:image]"]
    sort = "sort_i asc"
    record = SolrConnection.search("*:*", fq=fq, fl=fl, sort=sort, rows=1)

    if record.hits == 0:
        return None

    canvas_record: Dict = record.docs[0]
    canvas: Canvas = Canvas(canvas_record, context={"request": request,
                                                    "config": config,
                                                    "direct_request": True})
    return canvas.data


class Canvas(ContextDictSerializer):
    # Context will only be emitted if the canvas is being de-referenced directly;
    # otherwise, it will return None and will not appear when embedded in a manifest.
    ctx = serpy.MethodField(
        label="@context"
    )

    cid = serpy.MethodField(
        label="id"
    )

    ctype = StaticField(
        label="type",
        value="Canvas"
    )

    label = serpy.MethodField()

    width = serpy.MethodField()
    height = serpy.MethodField()

    items = serpy.MethodField()
    part_of = serpy.MethodField(
        label="partOf"
    )
    annotations = serpy.MethodField()

    metadata = serpy.MethodField()

    def get_label(self, obj: SolrResult) -> Dict:
        return {"en": [f"{obj.get('label_s')}"]}

    def get_width(self, obj: SolrResult) -> int:
        """
        Width and Height are not stored on the canvas, but on the child documents. Assume
        that the first child document, if there is one, contains the width/height for the
        canvas.
        """
        if "_childDocuments_" not in obj:
            return 0

        return obj.get('_childDocuments_')[0]['width_i']

    def get_height(self, obj: SolrResult) -> int:
        if "_childDocuments_" not in obj:
            return 0
        return obj.get("_childDocuments_")[0]['height_i']

    def get_cid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        canvas_tmpl: str = cfg['templates']['canvas_id_tmpl']

        # Surfaces have the suffix "_surface" in Solr. Strip it off for this identifier
        canvas_id: str = re.sub(SURFACE_ID_SUB, "", obj.get("id"))

        return get_identifier(req, canvas_id, canvas_tmpl)

    def get_items(self, obj: SolrResult) -> List[Dict]:
        req = self.context.get('request')
        cfg = self.context.get('config')
        image_annotation_page = ImageAnnotationPage(obj, context={"request": req, "config": cfg}).data
        return [image_annotation_page]

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

    def get_part_of(self, obj: SolrResult) -> Optional[List]:
        """
        When requested directly, give a within parameter to point back to
        the parent manuscript.
        """
        direct_request: bool = self.context.get('direct_request')

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

    def get_metadata(self, obj: SolrResult) -> Optional[List[Dict]]:
        return v3_metadata_block(obj, CANVAS_FIELD_CONFIG)

    def get_annotations(self, obj: SolrResult) -> Optional[List[Dict]]:
        """
        If the canvas has annotations, add them to the response. A call to check whether there are any
        annotations at all for this manifest is performed in the `Manifest` serializer, and the result
        is passed down here as an optimization, so that we don't have to check every canvas in Solr for
        annotations when the bulk of our manifests do not have any.

        :param obj: A Solr result object
        :return: A List object containing a pointer to the annotation pages, or None if no annotations.
        """
        has_annotations = self.context.get("has_annotations")

        if not has_annotations and not self.context.get("direct_request"):
            return None

        # check if the canvas has any non-image annotation pages
        sid = obj["id"]
        req = self.context.get('request')
        cfg = self.context.get('config')

        fq = ["type:annotationpage", f'surface_id:"{sid}"']
        fl = ["id"]
        manager: SolrManager = SolrManager(SolrConnection)
        manager.search(q='*:*', fq=fq, fl=fl)

        if manager.hits == 0:
            return None

        annotation_list_tmpl: str = cfg['templates']['annopage_id_tmpl']

        annotation_ids = [{"id": get_identifier(req, annotation_page['id'], annotation_list_tmpl),
                           "type": "AnnotationPage"}
                          for annotation_page in manager.results]
        return annotation_ids
