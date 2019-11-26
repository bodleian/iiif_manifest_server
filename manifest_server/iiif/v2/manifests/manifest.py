import logging
import re
from typing import List, Dict, Optional

import pysolr
import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier, IIIF_V2_CONTEXT
from manifest_server.helpers.metadata import v2_metadata_block, get_links
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.helpers.solr import SolrResult
from manifest_server.iiif.v2.manifests.sequence import Sequence
from manifest_server.iiif.v2.manifests.structure import create_v2_structures

log = logging.getLogger(__name__)

IMAGE_ID_SUB = re.compile(r"_image")
SURFACE_ID_SUB = re.compile(r"_surface")


def create_v2_manifest(request, manifest_id: str, config: Dict) -> Optional[Dict]:
    record: pysolr.Results = SolrConnection.search("*:*", fq=["type:object", f"id:{manifest_id}"], rows=1)

    if record.hits == 0:
        return None

    object_record = record.docs[0]
    manifest: Manifest = Manifest(object_record, context={"request": request,
                                                          "config": config,
                                                          "solr_conn": SolrConnection})

    return manifest.data


class Manifest(ContextDictSerializer):
    ctx = StaticField(
        value=IIIF_V2_CONTEXT,
        label="@context"
    )
    # Manifest ID
    mid = serpy.MethodField(
        label="@id"
    )

    mtype = StaticField(
        value="sc:Manifest",
        label="@type"
    )

    label = serpy.StrField(
        attr="full_shelfmark_s"
    )
    description = serpy.StrField(
        attr="summary_s"
    )
    metadata = serpy.MethodField()
    nav_date = serpy.MethodField(label='navDate')
    rendering = serpy.MethodField()
    attribution = serpy.MethodField()
    logo = serpy.MethodField()
    thumbnail = serpy.MethodField()

    viewing_hint = serpy.MethodField(
        label="viewingHint"
    )
    viewing_direction = serpy.StrField(
        attr="viewing_direction_s",
        label="viewingDirection",
        required=False
    )
    sequences = serpy.MethodField()
    structures = serpy.MethodField()

    def get_mid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        conf = self.context.get('config')
        manifest_tmpl: str = conf['templates']['manifest_id_tmpl']

        return get_identifier(req, obj.get('id'), manifest_tmpl)

    def get_metadata(self, obj: SolrResult) -> Optional[List[Dict]]:
        # Talbot manifests are a bit different, so exclude their metadata
        if 'talbot' in obj.get('all_collections_id_sm', []):  # type: ignore
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')
        tmpl: str = cfg['templates']['digital_bodleian_permalink_tmpl']
        ident: str = get_identifier(req, obj.get('id'), tmpl)
        val: str = '<span><a href="{0}">View on Digital Bodleian</a></span>'.format(ident)

        metadata: List = [{
            "label": "Homepage",
            "value": val
        }]

        metadata += get_links(obj, 2)
        metadata += v2_metadata_block(obj)

        return metadata

    def get_rendering(self, obj: SolrResult) -> Optional[Dict]:
        # Talbot manifests are a bit different, so exclude their metadata
        if 'talbot' in obj.get('all_collections_id_sm', []):  # type: ignore
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')
        tmpl = cfg['templates']['digital_bodleian_permalink_tmpl']

        ident: str = get_identifier(req, obj.get('id'), tmpl)

        return {
            "@id": ident,
            "label": "View on Digital Bodleian",
            "format": "text/html"
        }

    def get_viewing_hint(self, obj: SolrResult) -> str:
        """
        The viewing types are controlled in the silo indexer; returns 'paged' by default
        :param obj:
        :return:
        """
        vtype: str = obj.get('viewing_type_s')

        if vtype and vtype in ["map", "sheet", "binding", "photo"]:
            return "individuals"

        return "paged"

    def get_attribution(self, obj: SolrResult) -> str:
        rights: str = obj.get("access_rights_sni", "")
        terms: str = obj.get("use_terms_sni", "")

        # If there is both rights and terms, will separate them with semicolon.
        # If there is only one, will join the empty string and then strip it off for display.
        attrb: str = ". ".join([rights, terms]).strip(". ")
        # The previous line would strip the final period. Put it back in.
        return f"{attrb}."

    def get_logo(self, obj: SolrResult) -> Optional[Dict]:
        logo_uuid: str = obj.get("logo_id")

        if not logo_uuid:
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')
        image_tmpl: str = cfg['templates']['image_id_tmpl']
        thumbsize: str = cfg['common']['thumbsize']

        logo_ident: str = get_identifier(req, logo_uuid, image_tmpl)

        logo_service: Dict = {
            "@id": f"{logo_ident}/full/{thumbsize},/0/default.jpg",
            "service": {
                "@context": "http://iiif.io/api/image/2/context.json",
                "profile": "http://iiif.io/api/image/2/level1.json",
                "@id": logo_ident
            }
        }

        return logo_service

    def get_thumbnail(self, obj: SolrResult) -> Optional[Dict]:
        image_uuid: str = obj.get('thumbnail_id')

        if not image_uuid:
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')

        image_tmpl: str = cfg['templates']['image_id_tmpl']

        image_ident: str = get_identifier(req, image_uuid, image_tmpl)
        thumbsize: str = cfg['common']['thumbsize']

        thumb_service: Dict = {
            "@id": f"{image_ident}/full/{thumbsize},/0/default.jpg",
            "service": {
                "@context": "http://iiif.io/api/image/2/context.json",
                "profile": "http://iiif.io/api/image/2/level1.json",
                "@id": image_ident
            }
        }

        return thumb_service

    def get_sequences(self, obj: SolrResult) -> List[Optional[Sequence]]:
        return [Sequence(obj, context={'request': self.context.get('request'),
                                       'config': self.context.get('config')}).data]

    def get_structures(self, obj: SolrResult) -> Optional[List[Dict]]:
        return create_v2_structures(self.context.get('request'),
                                    obj.get('id'),
                                    self.context.get('config'))

    def get_nav_date(self, obj: SolrResult) -> Optional[str]:
        year: Optional[int] = obj.get('start_date_i') or obj.get('end_date_i')

        if year is None:
            return None

        return f"{year}-01-01T00:00:00Z"
