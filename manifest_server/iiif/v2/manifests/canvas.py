import logging
import re
from typing import List, Dict, Optional, Pattern

import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier, IIIF_V2_CONTEXT
from manifest_server.helpers.metadata import v2_metadata_block, CANVAS_FIELD_CONFIG
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr import SolrManager, SolrResult
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.iiif.v2.manifests.annotation import ImageAnnotation

log = logging.getLogger(__name__)

SURFACE_ID_SUB: Pattern = re.compile(r"_surface")


def create_v2_canvas(request, canvas_id: str, config: Dict) -> Optional[Dict]:
    """
    Creates a new canvas in response to a request. Used for directly requesting canvases.

    :param request: A Sanic request object
    :param canvas_id: An ID passed in from the URL. Note that this lacks the '_surface' suffix
    :param config: A server configuration dictionary
    :return: A V2 Canvas object
    """
    fq = ["type:surface", f"id:{canvas_id}_surface"]
    fl = ["*,[child parentFilter=type:surface childFilter=type:image]"]
    sort = "sort_i asc"
    record = SolrConnection.search("*:*", fq=fq, fl=fl, sort=sort, rows=1)

    if record.hits == 0:
        return None

    canvas_record = record.docs[0]
    canvas: Canvas = Canvas(canvas_record, context={"request": request,
                                                    "config": config,
                                                    "direct_request": True})
    return canvas.data


class Canvas(ContextDictSerializer):
    ctx = serpy.MethodField(
        label="@context"
    )
    cid = serpy.MethodField(
        label="@id"
    )

    ctype = StaticField(
        label="@type",
        value="sc:Canvas"
    )

    label = serpy.StrField(
        attr="label_s"
    )

    width = serpy.MethodField()
    height = serpy.MethodField()

    images = serpy.MethodField()
    within = serpy.MethodField()

    metadata = serpy.MethodField()

    other_content = serpy.MethodField(label="otherContent")

    def get_ctx(self, obj: SolrResult) -> Optional[str]:  # pylint: disable-msg=unused-argument
        direct_request: bool = self.context.get('direct_request')
        return IIIF_V2_CONTEXT if direct_request else None

    def get_cid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        canvas_tmpl = cfg['templates']['canvas_id_tmpl']

        # Surfaces have the suffix "_surface" in Solr. Strip it off for this identifier
        canvas_id = re.sub(SURFACE_ID_SUB, "", obj.get("id"))

        return get_identifier(req, canvas_id, canvas_tmpl)

    def get_images(self, obj: SolrResult) -> List[Dict]:
        return ImageAnnotation(obj.get("_childDocuments_"), context={"request": self.context.get('request'),
                                                                     "config": self.context.get('config')}, many=True).data

    def get_width(self, obj: SolrResult) -> int:
        """
        Width and Height are required. If (for some reason) there is no image attached to this canvas
        then return a 0. This will allow manifest parsers to load the manifest so that any correct images
        will still be shown.

        :param obj: A Solr result
        :return: An integer representing the width of the canvas.
        """
        if "_childDocuments_" not in obj:
            return 0

        return obj.get('_childDocuments_')[0]['width_i']

    def get_height(self, obj: SolrResult) -> int:
        """
        See the comment for width above.

        :param obj: A Solr result
        :return: An integer representing the height of the canvas.
        """
        if "_childDocuments_" not in obj:
            return 0

        return obj.get("_childDocuments_")[0]['height_i']

    def get_within(self, obj: SolrResult) -> Optional[List]:
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
            "@id": wid,
            "@type": "Manifest",
            "label": object_record.get('full_shelfmark_s')
        }]

    def get_metadata(self, obj: SolrResult) -> Optional[List[Dict]]:
        return v2_metadata_block(obj, CANVAS_FIELD_CONFIG)

    def get_other_content(self, obj: SolrResult) -> Optional[List]:
        """
        If the canvas has annotations, add them to the response. A call to check whether there are any
        annotations at all for this manifest is performed in the `Manifest` serializer, and the result
        is passed down here as an optimization, so that we don't have to check every canvas in Solr for
        annotations when the bulk of our manifests do not have any.

        :param obj: A Solr result object
        :return: A List object containing a pointer to the annotation pages, or None if no annotations.
        """
        has_annotations = self.context.get("has_annotations")

        if not has_annotations and not self.context.get('direct_request'):
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

        annotation_list_tmpl: str = cfg['templates']['annolist_id_tmpl']

        annotation_ids = [{"@id": get_identifier(req, annotation_list['id'], annotation_list_tmpl),
                           "@type": "sc:AnnotationList"}
                          for annotation_list in manager.results]
        return annotation_ids
