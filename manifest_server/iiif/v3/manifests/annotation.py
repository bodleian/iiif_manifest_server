import re
from abc import abstractmethod
from typing import List, Optional, Dict, Pattern, Union
import html

import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier, IIIF_V3_CONTEXT
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.helpers.solr import SolrResult
from manifest_server.iiif.v3.manifests.image import Image

IMAGE_ID_SUB: Pattern = re.compile(r"_image")
SURFACE_ID_SUB: Pattern = re.compile(r"_surface")


def create_v3_annotation(request, annotation_id: str, config: Dict) -> Optional[Dict]:
    # check for image annotations first
    fq: List[str] = ["type:image", f"id:{annotation_id}_image"]
    fl: List[str] = ["id", "surface_id", "width_i", "height_i", "object_id"]
    image_record = SolrConnection.search("*:*", fq=fq, fl=fl, rows=1)

    if image_record.hits != 0:
        image_annotation = ImageAnnotation(image_record.docs[0], context={"request": request,
                                                                          "config": config,
                                                                          "direct_request": True})
        return image_annotation.data

    # check if there's a non-image annotation matching the id
    # safest to put these in separate solr calls because of the child documents
    fq = ["type:annotation", f"id:{annotation_id}"]
    fl = ["*", "[child parentFilter=type:annotation childFilter=type:annotation_body]"]
    anno_record = SolrConnection.search("*:*", fq=fq, fl=fl, rows=1)

    if anno_record.hits == 0:
        return None

    annotation = TextAnnotation(anno_record.docs[0], context={"request": request,
                                                              "config": config,
                                                              "direct_request": True})
    return annotation.data


class BaseAnnotation(ContextDictSerializer):
    ctx = serpy.MethodField(
        label="@context"
    )
    aid = serpy.MethodField(
        label="id"
    )

    itype = StaticField(
        label="type",
        value="Annotation"
    )
    target = serpy.MethodField()
    body = serpy.MethodField()

    def get_aid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        annotation_tmpl: str = cfg['templates']['annotation_id_tmpl']

        # The substitution here is only needed for image annotations, but won't affect other annotations
        annotation_id: str = re.sub(IMAGE_ID_SUB, "", obj.get("id"))

        return get_identifier(req, annotation_id, annotation_tmpl)

    @abstractmethod
    def get_body(self, obj: SolrResult) -> Union[List[Dict], Dict]:
        """
        Get the body of this annotation - either an Image or a representation of the text for a text annotation
        :param obj:
        :return:
        """

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

    def get_target(self, obj: SolrResult) -> str:
        """
        This method may be overridden in subclasses to e.g. reference a specific region of the canvas
        :param obj: A Solr Result object
        :return: the uri for the canvas this annotation is attached to
        """
        req = self.context.get('request')
        cfg = self.context.get('config')
        canvas_tmpl: str = cfg['templates']['canvas_id_tmpl']

        identifier: str = re.sub(SURFACE_ID_SUB, "", obj['surface_id'])
        return get_identifier(req, identifier, canvas_tmpl)


class ImageAnnotation(BaseAnnotation):
    motivation = StaticField(
        value="painting"
    )

    def get_body(self, obj: SolrResult) -> Dict:
        return Image(obj, context={"request": self.context.get('request'),
                                   "config": self.context.get("config")}).data


class TextAnnotation(BaseAnnotation):
    # TODO: consider adding the motivation value from the source data
    #  wait until we have mirador to test against
    motivation = StaticField(
        value="supplementing"
    )

    def get_body(self, obj: SolrResult) -> List[Dict]:
        # TODO: once we have an annotation viewer that supports v3,
        #  check if this should be a list or an oa:Choice or something else
        bodies = []

        if '_childDocuments_' in obj:

            for solr_body in obj['_childDocuments_']:
                chars = f'<p dir="{solr_body["direction_s"]}">{html.escape(solr_body["text_s"])}</p>'
                bodies.append({
                    "@type": "cnt:ContentAsText",
                    "chars": chars,
                    "format": "text/html",
                    "language": solr_body['language_s']
                })

        return bodies

    def get_target(self, obj: SolrResult):
        """
        Get the base canvas uri using the BaseAnnotation super class's implementation of get_target

        :param obj: A Solr result object
        :return: the uri for the canvas this annotation is attached to, with an xywh parameter to show what region the
                  annotation applies to
        """
        target_uri = super().get_target(obj)
        return f"{target_uri}#xywh={obj['ulx_i']},{obj['uly_i']},{obj['width_i']},{obj['height_i']}"
