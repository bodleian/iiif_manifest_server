import re
from typing import Dict, Optional, List, Pattern

import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier, IIIF_V2_CONTEXT
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr import SolrManager, SolrResult
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.helpers.structures import compute_v2_hierarchy
from manifest_server.helpers.metadata import (
    v2_metadata_block,
    WORKS_METADATA_FILTER_FIELDS,
    WORKS_METADATA_FIELD_CONFIG
)

SURFACE_ID_SUB: Pattern = re.compile(r"_surface$")


def create_v2_range(request, range_id: str, config: Dict) -> Optional[Dict]:
    """
    Handles a lookup for a specific range. Due to the nature of how the
    range hierarchy is computed, we have to compute the full hierarchy, and then
    just select the requested one and return it.

    :param request: A Sanic request object
    :param range_id: The range ID being requested.
    :param config: A manifest server config dictionary
    :return: A Dictionary containing the requested Range block
    """
    # A range query will always have two components: The object ID and the range ID.
    # Fail early if this is not the case.
    if '/' not in range_id:
        return None

    obj_id, log_id = range_id.split("/")
    structures: Optional[List[Dict]] = create_v2_structures(request, obj_id, config, direct_request=True)

    if not structures:
        return None

    range_tmpl: str = config['templates']['range_id_tmpl']
    ident: str = get_identifier(request, obj_id, range_tmpl, range_id=log_id)

    s: Dict = {}

    # cycle through the structures until we find the one we want
    for struct in structures:
        if not struct.get('@id') == ident:
            continue
        s = struct
        break

    return s


def create_v2_structures(request, obj_id: str, config: Dict, direct_request: bool = False) -> Optional[List[Dict]]:
    """
    Creates the full structure hierarchy for a given object ID.

    :param request: A Sanic request object
    :param obj_id: An object ID to use to lookup the works
    :param config: A configuration dictionary
    :param direct_request: True if the range is being requested directly; otherwise false if embedded in a manifest.
    :return: A Dictionary suitable for embedding in a manifest, or for being filtered to provide a certain response
        in the `create_v2_range` method above.
    """
    manager: SolrManager = SolrManager(SolrConnection)
    fq: List = ["type:work", f"object_id:{obj_id}"]
    # Restrict the returned fields to only those that are needed.
    fl: List = WORKS_METADATA_FILTER_FIELDS
    # make a list of the keys in works_metadata_field_config to extend the field list
    rows: int = 100
    sort: str = "work_id asc"
    manager.search("*:*", fq=fq, fl=fl, sort=sort, rows=rows)

    if manager.hits == 0:
        return None

    # we will need to iterate through this list a few times, so we evaluate it to a list
    results: List = list(manager.results)

    hierarchy: Dict = compute_v2_hierarchy(results, obj_id, request, config)

    return Structure(results, context={"request": request,
                                       "config": config,
                                       "hierarchy": hierarchy,
                                       "direct_request": direct_request}, many=True).data


class Structure(ContextDictSerializer):
    ctx = serpy.MethodField(
        label="@context"
    )

    sid = serpy.MethodField(
        label="@id"
    )

    stype = StaticField(
        label="@type",
        value="sc:Range"
    )

    label = serpy.StrField(
        attr="work_title_s"
    )
    within = serpy.MethodField()

    viewing_hint = serpy.MethodField(
        label="viewingHint",
        required=False
    )

    # members = serpy.MethodField()
    canvases = serpy.MethodField()
    ranges = serpy.MethodField()
    metadata = serpy.MethodField()

    def get_ctx(self, obj: SolrResult) -> Optional[str]:  # pylint: disable-msg=unused-argument
        direct_request: bool = self.context.get('direct_request')
        return IIIF_V2_CONTEXT if direct_request else None

    def get_sid(self, obj: Dict) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        range_tmpl: str = cfg['templates']['range_id_tmpl']

        identifier: str = obj.get("object_id")
        range_id: str = obj.get("work_id")

        return get_identifier(req, identifier, range_tmpl, range_id=range_id)

    def get_within(self, obj: SolrResult) -> Optional[List]:
        """When requested directly, give a within parameter to point back to
           the parent manuscript.
        """
        direct_request: bool = self.context.get('direct_request')

        if not direct_request:
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')

        manifest_tmpl: str = cfg['templates']['manifest_id_tmpl']
        wid: str = get_identifier(req, obj.get('object_id'), manifest_tmpl)

        return [{
            "id": wid,
            "type": "Manifest"
        }]

    def get_viewing_hint(self, obj: SolrResult) -> Optional[str]:
        if not obj.get("parent_work_id"):
            return "top"
        return None

    def get_ranges(self, obj: SolrResult) -> Optional[List]:
        hierarchy = self.context.get('hierarchy')
        wk_id = obj.get("work_id")

        # If the work ID is not in the hierarchy, it contains
        # a list of canvases; return None.
        if wk_id not in hierarchy:
            return None

        return hierarchy[wk_id]

    def get_canvases(self, obj: SolrResult) -> Optional[List]:
        hierarchy = self.context.get('hierarchy')
        wk_id = obj.get("work_id")

        # If the work id is in the hierarchy, this contains
        # a list of ranges; return None.
        if wk_id in hierarchy:
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')
        surfaces: List = obj.get('surfaces_sm')
        canvas_tmpl: str = cfg['templates']['canvas_id_tmpl']

        ret: List = []
        for s in surfaces:
            ret.append(get_identifier(req, re.sub(SURFACE_ID_SUB, "", s), canvas_tmpl))

        return ret

    def get_metadata(self, obj: SolrResult) -> Optional[List[Dict]]:
        return v2_metadata_block(obj, WORKS_METADATA_FIELD_CONFIG)
