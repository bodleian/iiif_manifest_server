import re
from abc import abstractmethod
from typing import List, Dict, Pattern, Optional, Union

import serpy
import html

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier, IIIF_V2_CONTEXT
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.helpers.solr import SolrResult
from manifest_server.iiif.v2.manifests.image import Image

IMAGE_ID_SUB: Pattern = re.compile(r"_image$")
SURFACE_ID_SUB: Pattern = re.compile(r"_surface$")

# putting this in the manifest server for now, as it's mostly necessary
# because of needing a final concatenated annotation
# should re evaluate if this should be indexed if we get non-multi lingual
# multi-body annotations, or if we decide to use headers permanently
LANGUAGE_TO_HEADER_MAP: Dict[str, str] = {
    "ar-latn": "Arabic (Romanized)",
    "ar": "Arabic",
    "en": "English"
}


def create_v2_annotation(request, annotation_id: str, config: Dict) -> Optional[Dict]:
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
        label="@id"
    )
    itype = StaticField(
        label="@type",
        value="oa:Annotation"
    )
    motivation = StaticField(
        value="sc:painting"
    )
    on = serpy.MethodField()
    resource = serpy.MethodField()

    def get_ctx(self, obj: SolrResult) -> Optional[str]:  # pylint: disable-msg=unused-argument
        """
        If the resource is requested directly (instead of embedded in a manifest)
        return the context object; otherwise it will inherit the context of the parent.

        Note that the 'direct_request' context object is not passed down to children,
        so it will only appear in a top-level object.
        :param obj: Dictionary object to be serialized
        :return: List containing the appropriate context objects.
        """
        direct_request: bool = self.context.get('direct_request')
        return IIIF_V2_CONTEXT if direct_request else None

    def get_aid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        annotation_tmpl: str = cfg['templates']['annotation_id_tmpl']

        # The substitution here is only needed for image annotations, but won't affect other annotations
        annotation_id: str = re.sub(IMAGE_ID_SUB, "", obj["id"])

        return get_identifier(req, annotation_id, annotation_tmpl)

    @abstractmethod
    def get_resource(self, obj: SolrResult) -> Union[List[Dict], Dict]:
        """
        Get the body of this annotation - either an Image or a representation of the text for a text annotation
        :param obj:
        :return:
        """

    def get_on(self, obj: SolrResult) -> Union[str, List[Dict]]:
        """
        This method may be overridden in subclasses to e.g. reference a specific region of the canvas
        :param obj:
        :return: the uri for the canvas this annotation is attached to
        """
        req = self.context.get('request')
        cfg = self.context.get('config')
        canvas_tmpl = cfg['templates']['canvas_id_tmpl']

        identifier = re.sub(SURFACE_ID_SUB, "", obj['surface_id'])
        identifier_uri = get_identifier(req, identifier, canvas_tmpl)

        return identifier_uri


class ImageAnnotation(BaseAnnotation):
    def get_resource(self, obj: SolrResult) -> Dict:
        return Image(obj, context={"request": self.context.get('request'),
                                   "config": self.context.get("config")}).data


class TextAnnotation(BaseAnnotation):
    def get_resource(self, obj: SolrResult) -> List[Dict]:
        resources = []

        if not obj.get('_childDocuments_'):
            # There's no text associated with this annotation
            # Mirador 2 returns 'undefined' as the text if no resources are supplied, so we supply an empty one
            return [{
                "@type": "dctypes:Text",
                "chars": "",
                "format": "text/html"
            }]

        child_docs: List = obj['_childDocuments_']

        for body in child_docs:
            chars = f'<p dir="{body["direction_s"]}">{html.escape(body["text_s"])}</p>'
            resources.append({
                "@type": "dctypes:Text",
                "chars": chars,
                "format": "text/html",
                "language": body['language_s']
            })

        if len(child_docs) > 1:
            # Add a final item with all of the bodies concatenated.
            # This is to work around a Mirador 2 bug (https://github.com/ProjectMirador/mirador/issues/2663)
            # which only shows the last body.
            # Once this is fixed or we move to Mirador 3 we should remove this.
            concatenated_chars = ""

            for body in child_docs:
                header = LANGUAGE_TO_HEADER_MAP.get(body['language_s'])
                if header:
                    # mirador 2 doesn't display h2 etc tags in annotations, so we use strong instead
                    paragraph_contents = f'<strong>{header}</strong><br/>{html.escape(body["text_s"])}'
                else:
                    paragraph_contents = html.escape(body["text_s"])
                concatenated_chars += f'<p dir="{body["direction_s"]}">{paragraph_contents}</p>'

            resources.append({
                "@type": "dctypes:Text",
                "chars": concatenated_chars,
                "format": "text/html"
            })

        return resources

    def get_on(self, obj: SolrResult) -> Union[str, List[Dict]]:
        """
        Get the base canvas uri using the BaseAnnotation super class's implementation of get_on
        :param obj:
        :return: the uri for the canvas this annotation is attached to, with an xywh parameter to show what region the annotation applies to
        """
        target_uri = super().get_on(obj)

        if not obj.get('svg_s'):
            return f"{target_uri}#xywh={obj['ulx_i']},{obj['uly_i']},{obj['width_i']},{obj['height_i']}"

        req = self.context.get('request')
        cfg = self.context.get('config')
        manifest_tmpl = cfg['templates']['manifest_id_tmpl']
        manifest_uri = get_identifier(req, obj['object_id'], manifest_tmpl)

        return [
            {
                "@type": "oa:SpecificResource",
                "full": target_uri,
                "selector": {
                    "@type": "oa:Choice",
                    "default": {
                        "@type": "oa:FragmentSelector",
                        "value": f"xywh={obj['ulx_i']},{obj['uly_i']},{obj['width_i']},{obj['height_i']}"
                    },
                    "item": {
                        "@type": "oa:SvgSelector",
                        "value": obj['svg_s']
                    }
                },
                "within": {
                    "@id": manifest_uri,
                    "@type": "sc:Manifest"
                }
            }
        ]
