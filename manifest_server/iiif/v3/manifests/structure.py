import re
from typing import List, Dict, Optional, Pattern
import logging

import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier, IIIF_V3_CONTEXT
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr import SolrManager, SolrResult
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.helpers.structures import treeize
from manifest_server.helpers.metadata import (
    v3_metadata_block,
    WORKS_METADATA_FILTER_FIELDS,
    WORKS_METADATA_FIELD_CONFIG
)

SURFACE_ID_SUB: Pattern = re.compile(r"_surface$")

log = logging.getLogger(__name__)


def __find_in_tree(lst: List, ident: str) -> Dict:
    """
    Recursively search the tree of range results and find the one that has been requested.

    :param lst: A list of ranges or canvases
    :param ident: The "needle" identifier we are trying to find
    :return: A dictionary result or None if not found.
    """
    res: Dict = {}

    for itm in lst:
        if itm['id'] == ident:  # pylint: disable-msg=no-else-return
            return itm

        elif itm['type'] == 'Range' and itm.get('items'):
            res = __find_in_tree(itm.get('items'), ident)
            # added check if res was successful to break out of the recursion
            if res:
                return res

    return res


def create_v3_range(request, range_id: str, config: Dict) -> Optional[Dict]:
    """
    Handles a lookup for a particular range ID. Works by constructing the whole
    tree of results, and then searching in that result for the requested range. This is
    necessary because the results stored in Solr are flattened, so we need to know
    the nested relationships of all objects before selecting just the sub-part of the tree.

    :param request: A Sanic request object
    :param range_id: A range ID that has been requested
    :param config: A configuration dictionary
    :return: A Dictionary containing the requested part of the tree.
    """
    if "/" not in range_id:
        return None

    obj_id, log_id = range_id.split("/")

    range_tmpl: str = config['templates']['range_id_tmpl']
    ident: str = get_identifier(request, obj_id, range_tmpl, range_id=log_id)
    tree: Optional[List] = create_v3_structures(request, obj_id, config, direct_request=True)

    if not tree:
        return None

    res: Dict = __find_in_tree(tree, ident)

    return res


def create_v3_structures(request, obj_id: str, config, direct_request: bool = False) -> Optional[List]:
    manager: SolrManager = SolrManager(SolrConnection)
    fq: List = ["type:work", f"object_id:{obj_id}"]
    # Restrict the returned fields to only those that are needed.
    fl: List = WORKS_METADATA_FILTER_FIELDS
    rows: int = 100
    sort: str = "work_id asc"
    manager.search("*:*", fq=fq, sort=sort, fl=fl, rows=rows)

    if manager.hits == 0:
        return None

    results = list(manager.results)
    output: List = []

    # A recursive function that takes the results and creates a tree
    # from them. You don't want to know how long this took to sort out.
    treeize(results, results[:], output)

    # This is implemented as a recursive call on the output list, serializing any child records
    # before returning the whole structure as a blob.
    return StructureRangeItem(output, context={'request': request,
                                               'config': config,
                                               "direct_request": direct_request}, many=True).data


class StructureCanvasItem(ContextDictSerializer):
    cid = serpy.MethodField(
        label="id"
    )

    ctype = StaticField(
        label="type",
        value="Canvas"
    )

    def get_cid(self, obj: str) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        canvas_tmpl: str = cfg['templates']['canvas_id_tmpl']

        return get_identifier(req, re.sub(SURFACE_ID_SUB, "", obj), canvas_tmpl)


class StructureRangeItem(ContextDictSerializer):
    ctx = serpy.MethodField(
        label="@context"
    )

    sid = serpy.MethodField(
        label="id"
    )

    stype = StaticField(
        label="type",
        value="Range"
    )

    part_of = serpy.MethodField(
        label="partOf"
    )

    label = serpy.MethodField()
    metadata = serpy.MethodField()
    items = serpy.MethodField()

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
        """When requested directly, give a within parameter to point back to
           the parent manuscript.
        """
        direct_request: bool = self.context.get('direct_request')

        if not direct_request:
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')
        obj_id: str = obj.get('object_id')

        manifest_tmpl: str = cfg['templates']['manifest_id_tmpl']
        wid: str = get_identifier(req, obj_id, manifest_tmpl)

        return [{
            "id": wid,
            "type": "Manifest"
        }]

    def get_sid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        range_tmpl: str = cfg['templates']['range_id_tmpl']

        identifier: str = obj.get("object_id")
        range_id: str = obj.get("work_id")

        return get_identifier(req, identifier, range_tmpl, range_id=range_id)

    def get_label(self, obj: SolrResult) -> Dict:
        return {"en": [f"{obj.get('work_title_s')}"]}

    def get_metadata(self, obj: SolrResult) -> Optional[List[Dict]]:
        return v3_metadata_block(obj, WORKS_METADATA_FIELD_CONFIG)

    def get_items(self, obj: SolrResult) -> List:
        # If the object has a list of child objects,
        # it is a range; if not, it is a canvas.
        req = self.context.get('request')
        cfg = self.context.get('config')
        direct = self.context.get('direct_request')

        if obj.get('_children'):
            return StructureRangeItem(obj['_children'], context={'request': req,
                                                                 'config': cfg,
                                                                 'direct_request': direct}, many=True).data

        return StructureCanvasItem(obj['surfaces_sm'], context={'request': req,
                                                                'config': cfg,
                                                                'direct_request': direct}, many=True).data
