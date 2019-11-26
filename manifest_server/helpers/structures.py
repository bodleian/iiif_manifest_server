import logging
from typing import List, Dict
from manifest_server.helpers.identifiers import get_identifier

log = logging.getLogger(__name__)


def compute_v2_hierarchy(results: List, object_id: str, request, config: Dict) -> Dict:
    """
    Takes a list of work object results and returns a dictionary
    corresponding to the work hierarchy (ranges and sub-ranges).

    :param results: A list of Solr work results
    :param object_id: An Object ID
    :param request: A Sanic request object
    :param config: A manifest server config dict
    :return: A work object hierarchy dictionary keyed by URI
    """
    hierarchy: Dict = {}

    for res in results:
        parent_wk_id: str = res.get('parent_work_id', None)
        wk_id: str = res.get('work_id')

        if not parent_wk_id:
            continue

        if parent_wk_id not in hierarchy:
            hierarchy[parent_wk_id] = []

        range_tmpl: str = config['templates']['range_id_tmpl']
        ident: str = get_identifier(request, object_id, range_tmpl, range_id=wk_id)

        hierarchy[parent_wk_id].append(ident)

    return hierarchy


def treeize(res: List, search: List, out: List) -> None:
    """
    A recursive function that takes a flat list of search results and returns
    the parent/child relationship tree. Used to construct the sequences objects for
    v3 sequences.

    Uses an array and a copy of the array, and puts the results in an output array.
    Only the root objects are directly appended to the array; all others will be appended
    to an object's '_children' array. This way the whole tree gets constructed.

    It's implemented as a recursive function, rather than a for loop,
    so that we can operate on the results array directly and remove it from the results
    once we've assigned it a parent.

    :param res: The results array
    :param search: A copy of the results array used to find objects and put them in their right place
    :param out: The output array
    :return: None; the output array will contain the results as a reference.
    """
    # Since we pop results from this list, it will eventually drain itself and return None.
    if not res:
        log.debug("No res; returning.")
        return None

    it: Dict = res.pop()
    work_id: str = it['work_id']

    it['_children'] = [s for s in search if s.get('parent_work_id') == work_id]

    if not it.get('parent_work_id'):
        out.append(it)

    treeize(res, search, out)

    return None
