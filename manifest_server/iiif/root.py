import serpy
from typing import List, Dict
from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.identifiers import IIIF_ASTREAMS_CONTEXT, get_identifier


def create_root(req, obj, conf) -> Dict:  # pylint: disable-msg=unused-argument
    return IIIFRoot({}, context={"request": req,
                                 "config": conf}).data


# The ActivityStreams context does not contain the Prezi3 Collection
# definition in the right place, so we'll import it here until such time that
# it does.
ROOT_CONTEXT: List = [*IIIF_ASTREAMS_CONTEXT, *[{
    "Collection": "http://iiif.io/api/presentation/3#Collection",
}]]


class IIIFRoot(ContextDictSerializer):
    """
    A small serializer that represents the root response for iiif.bodleian.ox.ac.uk. Points to
    browseable endpoints for our IIIF Service.
    """
    ctx = StaticField(
        label="@context",
        value=ROOT_CONTEXT
    )
    rid = serpy.MethodField(
        label="id"
    )
    items = serpy.MethodField()

    def get_rid(self, obj):  # pylint: disable-msg=unused-argument
        req = self.context.get('request')
        fwd_scheme_header = req.headers.get('X-Forwarded-Proto')
        fwd_host_header = req.headers.get('X-Forwarded-Host')
        scheme = fwd_scheme_header if fwd_scheme_header else req.scheme
        host = fwd_host_header if fwd_host_header else req.host

        return f"{scheme}://{host}/info.json"

    def get_items(self, obj) -> List[Dict]:  # pylint: disable-msg=unused-argument
        req = self.context.get('request')
        cfg = self.context.get('config')

        coll_id_tmpl: str = cfg['templates']['collection_id_tmpl']
        coll_top_id: str = get_identifier(req, "top", coll_id_tmpl)
        coll_all_id: str = get_identifier(req, "all", coll_id_tmpl)

        as_id_tmpl: str = cfg['templates']['activitystream_id_tmpl']
        as_top_id: str = get_identifier(req, "all-changes", as_id_tmpl)

        return [{
            "id": coll_top_id,
            "type": "Collection",
            "name": "Top-level collection"
        }, {
           "id": coll_all_id,
           "type": "Collection",
           "name": "All manifests"
        }, {
            "id": as_top_id,
            "type": "OrderedCollection",
            "name": "ActivityStream"
        }]
