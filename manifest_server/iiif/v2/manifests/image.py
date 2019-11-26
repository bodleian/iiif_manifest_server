import re
from typing import Dict, Pattern

import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr import SolrResult

IMAGE_ID_SUB: Pattern = re.compile(r"_image")


class Image(ContextDictSerializer):
    iid = serpy.MethodField(
        label="@id"
    )

    rtype = StaticField(
        label="@type",
        value="dctypes:Image"
    )

    format = StaticField(
        value="image/jpeg"
    )

    width = serpy.IntField(
        attr="width_i"
    )

    height = serpy.IntField(
        attr="height_i"
    )
    service = serpy.MethodField()

    def get_iid(self, obj: SolrResult) -> str:
        cfg = self.context.get('config')
        req = self.context.get('request')

        image_tmpl = cfg['templates']['image_id_tmpl']

        # Images have the suffix "_image" in Solr.
        identifier = re.sub(IMAGE_ID_SUB, "", obj.get("id"))
        return get_identifier(req, identifier, image_tmpl)  # type: ignore

    def get_service(self, obj: SolrResult) -> Dict:
        req = self.context.get('request')
        cfg = self.context.get('config')
        image_tmpl = cfg['templates']['image_id_tmpl']
        identifier = re.sub(IMAGE_ID_SUB, "", obj.get("id"))
        image_id = get_identifier(req, identifier, image_tmpl)  # type: ignore

        return {
            "@context": "http://iiif.io/api/image/2/context.json",
            "profile": "http://iiif.io/api/image/2/level1.json",
            "@id": image_id
        }
