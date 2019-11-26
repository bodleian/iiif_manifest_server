import logging
from typing import Optional, Dict, List

import pysolr
import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier, IIIF_V3_CONTEXT
from manifest_server.helpers.metadata import v3_metadata_block, get_links
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr import SolrManager, SolrResult
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.iiif.v3.manifests.canvas import Canvas
from manifest_server.iiif.v3.manifests.structure import create_v3_structures

log = logging.getLogger(__name__)


def create_v3_manifest(request, manifest_id: str, config: Dict) -> Optional[Dict]:
    fq: List = ["type:object", f"id:{manifest_id}"]
    record: pysolr.Results = SolrConnection.search("*:*", fq=fq, rows=1)

    if record.hits == 0:
        return None

    object_record = record.docs[0]

    manifest: Manifest = Manifest(object_record, context={"request": request,
                                                          "config": config})

    return manifest.data


class Manifest(ContextDictSerializer):
    """
    The main class for constructing a IIIF Manifest. Implemented as a serpy
    serializer. This docstring will serve as the documentation for this class, as well as the
    other serializer classes.

    The ContextDictSerializer superclass provides a 'context' object on this class. This
    can be used to pass values down through the various child classes, provided they are also given the same
    context. This lets us pass along things like the original request object, and the
    server configuration object, without needing to resolve it externally.

    For classes that implement de-referenceable objects, they provide a method field that will return
    None if that object is being embedded in a manifest, or the IIIF v3 context array if it's being
    de-referenced directly.

    When the values of this class are serialized, any fields that have a value of None will not
    be emitted in the output. Refer to the `to_value` method on the superclass for the implementation
    and docstring for this function.
    """
    ctx = StaticField(
        value=IIIF_V3_CONTEXT,
        label="@context"
    )

    mid = serpy.MethodField(
        label="id"
    )

    mtype = StaticField(
        value="Manifest",
        label="type"
    )

    label = serpy.MethodField()
    summary = serpy.MethodField()

    metadata = serpy.MethodField()
    homepage = serpy.MethodField()
    provider = serpy.MethodField()

    nav_date = serpy.MethodField(
        label='navDate'
    )
    logo = serpy.MethodField()
    thumbnail = serpy.MethodField()
    required_statement = serpy.MethodField(
        label="requiredStatement"
    )
    part_of = serpy.MethodField(
        label="partOf"
    )
    behaviour = serpy.MethodField(
        label="behavior"
    )
    items = serpy.MethodField()
    structures = serpy.MethodField()

    viewing_direction = serpy.StrField(
        attr="viewing_direction_s",
        label="viewingDirection",
        required=False
    )

    def get_mid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        conf = self.context.get('config')
        manifest_tmpl: str = conf['templates']['manifest_id_tmpl']

        return get_identifier(req, obj.get('id'), manifest_tmpl)

    def get_label(self, obj: SolrResult) -> Dict:
        return {"en": [f"{obj.get('full_shelfmark_s')}"]}

    def get_summary(self, obj: SolrResult) -> Dict:
        return {"en": [f"{obj.get('summary_s')}"]}

    def get_required_statement(self, obj: SolrResult) -> Dict:
        return {
            "label": {"en": ["Terms of Use"]},
            "value": {"en": [obj.get("use_terms_sni", None)]}
        }

    def get_part_of(self, obj: SolrResult) -> Optional[List]:
        colls: List[str] = obj.get('all_collections_link_smni')

        if not colls:
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')
        tmpl: str = cfg['templates']['collection_id_tmpl']

        ret: List[Dict] = []

        for collection in colls:
            cid, label = collection.split("|")
            ret.append({
                "id": get_identifier(req, cid, tmpl),
                "type": "Collection",
                "label": {"en": [label]}
            })

        return ret

    def get_homepage(self, obj: SolrResult) -> List:
        req = self.context.get('request')
        cfg = self.context.get('config')

        tmpl: str = cfg['templates']['digital_bodleian_permalink_tmpl']
        uuid: str = obj.get("id")

        conn: SolrManager = SolrManager(SolrConnection)
        fq: List = ['type:link', f"object_id:{uuid}"]

        conn.search("*:*", fq=fq)

        links: List = [{
            'id': get_identifier(req, uuid, tmpl),
            'type': "Text",
            "label": {"en": ["View on Digital Bodleian"]},
            "format": "text/html",
            "language": ["en"]
        }]

        if conn.hits > 0:
            for r in conn.results:
                links.append({
                    'id': r.get('target_s'),
                    'type': "Text",
                    "label": {"en": [r.get('label_s')]},
                    "format": "text/html",
                    "language": ["en"]
                })

        return links

    def get_logo(self, obj: SolrResult) -> Optional[List]:
        logo_uuid: str = obj.get("logo_id")

        if not logo_uuid:
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')
        image_tmpl: str = cfg['templates']['image_id_tmpl']

        logo_ident: str = get_identifier(req, logo_uuid, image_tmpl)
        thumbsize: str = cfg['common']['thumbsize']

        logo_service: List = [{
            "id": f"{logo_ident}/full/{thumbsize},/0/default.jpg",
            "type": "Image",
            "service": {
                "type": "ImageService2",
                "profile": "level1",
                "id": logo_ident
            }
        }]

        return logo_service

    def get_provider(self, obj: SolrResult) -> Optional[List]:
        """
            If a URI for the organization is not provided, we will not show any
            information about the organization.

        :param obj: A Solr record.
        :return: A 'provider' block.
        """
        uri: Optional[str] = obj.get("institution_uri_s", None)

        if not uri:
            return None

        org_name: Optional[str] = obj.get("holding_institution_s", None)
        org_homepage: Optional[str] = obj.get("institution_homepage_sni", None)

        provider_block: List = [{
            "id": uri,
            "type": "Agent",
            "label": {"en": [org_name]},
            "homepage": {
                "id": org_homepage,
                "type": "Text",
                "label": {"en": [org_name]},
                "format": "text/html"
            },
        }]

        return provider_block

    def get_thumbnail(self, obj: SolrResult) -> Optional[List]:
        image_uuid: str = obj.get('thumbnail_id')

        if not image_uuid:
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')

        image_tmpl: str = cfg['templates']['image_id_tmpl']

        image_ident: str = get_identifier(req, image_uuid, image_tmpl)
        thumbsize: str = cfg['common']['thumbsize']

        thumb_service: List = [{
            "id": f"{image_ident}/full/{thumbsize},/0/default.jpg",
            "service": {
                "type": "ImageService2",
                "profile": "level1",
                "id": image_ident
            }
        }]

        return thumb_service

    def get_behaviour(self, obj: SolrResult) -> List:
        vtype = obj.get('viewing_type_s')

        if vtype and vtype in ["map", "sheet", "binding", "photo"]:
            return ["individuals"]

        return ["paged"]

    def get_metadata(self, obj: SolrResult) -> Optional[List[Dict]]:
        # description_sm is already included in the summary
        metadata: List = get_links(obj, 3)
        metadata += v3_metadata_block(obj)

        return metadata

    def get_items(self, obj: SolrResult) -> Optional[List]:
        req = self.context.get('request')
        cfg = self.context.get('config')
        obj_id: str = obj.get('id')

        # Check if the canvases have annotations. We don't actually
        # need to retrieve them, just get the number of hits.
        has_annotations_res = SolrConnection.search(
            "*:*",
            fq=["type:annotationpage", f"object_id:{obj_id}"],
            rows=0
        )
        has_annotations = has_annotations_res.hits > 0

        manager: SolrManager = SolrManager(SolrConnection)
        fq: List = ["type:surface", f"object_id:{obj_id}"]
        sort: str = "sort_i asc"
        fl: List = ["*,[child parentFilter=type:surface childFilter=type:image]"]
        rows: int = 100
        manager.search("*:*", fq=fq, fl=fl, sort=sort, rows=rows)

        if manager.hits == 0:
            return None

        return Canvas(manager.results, context={"request": req,
                                                "config": cfg,
                                                "has_annotations": has_annotations}, many=True).data

    def get_structures(self, obj: SolrResult) -> Optional[List[Dict]]:
        return create_v3_structures(self.context.get("request"),
                                    obj.get("id"),
                                    self.context.get("config"))

    def get_nav_date(self, obj: SolrResult) -> Optional[str]:
        year: Optional[int] = obj.get('start_date_i') or obj.get('end_date_i')
        if year is None:
            return None
        return f"{year}-01-01T00:00:00Z"
