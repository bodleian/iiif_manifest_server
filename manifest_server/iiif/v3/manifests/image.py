import re
from typing import Dict, Pattern

import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr import SolrResult

IMAGE_ID_SUB: Pattern = re.compile(r"_image")
SURFACE_ID_SUB: Pattern = re.compile(r"_surface")


class Image(ContextDictSerializer):
    iid = serpy.MethodField(
        label="id"
    )

    rtype = StaticField(
        label="type",
        value="Image"
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
        conf = self.context.get('config')
        req = self.context.get('request')

        image_tmpl = conf['templates']['image_id_tmpl']

        # Images have the suffix "_image" in Solr.
        identifier = re.sub(IMAGE_ID_SUB, "", obj.get("id"))
        return get_identifier(req, identifier, image_tmpl)

    def get_service(self, obj: SolrResult) -> Dict:
        req = self.context.get('request')
        cfg = self.context.get('config')
        image_tmpl = cfg['templates']['image_id_tmpl']
        identifier = re.sub(IMAGE_ID_SUB, "", obj.get("id"))
        image_id = get_identifier(req, identifier, image_tmpl)

        return {
            "type": "ImageService2",
            "profile": "level1",
            "id": image_id
        }
