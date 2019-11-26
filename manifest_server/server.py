import logging
from typing import Dict, Callable, Optional, Union, Any

import yaml
import asyncio
import uvloop
from sanic import Sanic, response, request


from manifest_server.iiif.v2 import (
    create_v2_manifest,
    create_v2_canvas,
    create_v2_sequence,
    create_v2_annotation_list,
    create_v2_annotation,
    create_v2_collection,
    create_v2_range
)
from manifest_server.iiif.v3 import (
    create_v3_manifest,
    create_v3_canvas,
    create_v3_annotation_page,
    create_v3_annotation,
    create_v3_range,
    create_v3_collection
)

from manifest_server.iiif.activity import (
    create_ordered_collection,
    create_ordered_collection_page,
    create_activity
)

from manifest_server.iiif.root import create_root

config: Dict = yaml.safe_load(open('configuration.yml', 'r'))

app = Sanic()

debug_mode: bool = config['common']['debug']

# Indent levels can make a big difference in download size, but at the expense of making
# the output readable. Set to indent only in Debug mode.
JSON_INDENT: int = 0

if debug_mode:
    LOGLEVEL = logging.DEBUG
    JSON_INDENT = 4
else:
    LOGLEVEL = logging.WARNING
    asyncio.set_event_loop(uvloop.new_event_loop())

logging.basicConfig(format="[%(asctime)s] [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)",
                    level=LOGLEVEL)
log = logging.getLogger(__name__)


IIIF_CONTEXT_STR: str = "http://iiif.io/api/presentation/{iiif_version}/context.json"
IIIF_DISCOVERY_STR: str = "http://iiif.io/api/discovery/0/context.json"

DataCallable = Callable[[request.Request, Optional[Any], Dict], Optional[Dict]]


def _parse_request(req: request.Request, obj_id: Optional[str], v2_data_func: Optional[DataCallable],
                   v3_data_func: Optional[DataCallable]) -> response.HTTPResponse:
    """
    Since the logic of negotiation for returning v2/v3 objects is largely the same between
    manifests, canvases, sequences, and collections, this logic has been factored out here.
    This method takes a number of parameters and returns the appropriate JSON response, handling
    v2/v3 negotiation and response, and ld+json/json negotiation and response.
    :param req: The incoming request object.
    :param obj_id: The id to look up in Solr. This can be a canvas, manifest, or collection ID.
    :param v2_data_func: The function to call for returning a IIIF v2 response
    :param v3_data_func: The function to call for returning a IIII v3 response
    :return: A Sanic HTTPResponse object with either 404 (Not Found, text body), 406 (Not Acceptable, text body)
             or 200 (success, json body) statuses.
    """
    # read v2/v3 header X-IIIF-Version
    iiif_accept: str = req.headers.get('Accept')

    # Default to IIIF v2
    iiif_version: int = 2

    if iiif_accept and "presentation/3" in iiif_accept:
        iiif_version = 3

    if iiif_version == 2 and v2_data_func is None:
        # If the client asks for a v3 object using a v2 request.
        # Returns a 406 Not Acceptable, since the value of the 'Accept' header
        # and the server's ability to respond cannot agree.
        return response.text(
            'The requested resource is not available as a IIIFv2 response.',
            status=406
        )

    if iiif_version == 3 and v3_data_func is None:
        # inverse of above.
        return response.text(
            'The requested resource is not available as a IIIFv3 response.',
            status=406
        )

    if iiif_version == 3:
        log.debug('IIIF Version 3 object requested')
        data_obj = v3_data_func(req, obj_id, config)
    else:
        log.debug("IIIF Version 2 object requested (default).")
        data_obj = v2_data_func(req, obj_id, config)

    if not data_obj:
        return response.text(
            f"An object of ID {obj_id} was not found.",
            status=404
        )

    iiif_context: str = IIIF_CONTEXT_STR.format(iiif_version=iiif_version)

    headers: Dict = dict()

    if iiif_accept and 'ld+json' not in iiif_accept:
        headers['Content-Type'] = 'application/json'
    else:
        # If the response is plain JSON, flag it so that we can add the link header later.
        headers['Content-Type'] = f'application/ld+json;profile="{iiif_context}"'

    # NB: Escape forward slashes is an ambiguous part of the JSON spec. Disabling them makes the manifests more
    # readable. If problems arise with clients, we may need to revisit this parameter.
    return response.json(data_obj,
                         headers=headers,
                         status=200,
                         escape_forward_slashes=False,
                         indent=JSON_INDENT)


def _parse_activity_stream_request(req: request.Request, req_id: Union[str, int, None], response_func: DataCallable):
    """
    Handles requests for activity streams. Since these are outside of the IIIF v2/v3 requirements, we
    don't need to support this sort of content negotiation. However, we should respect the 'Accept' header
    for JSON/JSON-LD requests.

    :param req: A Sanic request object
    :param req_id: A variable for the ID passed in as part of the URL request
    :param response_func: The function handling the data response
    :return: A Sanic HTTPResponse object with either 404 (not found)
    """
    data_obj: Dict = response_func(req, req_id, config)

    if not data_obj:
        return response.text(
            f"The requested resource was not found",
            status=404
        )

    # read accept header for incoming request type
    iiif_accept: str = req.headers.get('Accept')
    headers: Dict = {}

    if iiif_accept and 'ld+json' not in iiif_accept:
        headers['Content-Type'] = 'application/json'
    else:
        headers['Content-Type'] = f'application/ld+json;profile="{IIIF_DISCOVERY_STR}"'

    return response.json(data_obj,
                         headers=headers,
                         status=200,
                         escape_forward_slashes=False,
                         indent=JSON_INDENT)


@app.route("/info.json")
async def root(req) -> response.HTTPResponse:
    # NB: The Root function is the same for v2 and v3 requests.
    return _parse_request(req, None, create_root, create_root)


@app.route("/iiif/manifest/<manifest_id:uuid>.json")
async def manifest(req, manifest_id: str) -> response.HTTPResponse:
    """
    Given a Digital Bodleian UUID, returns a IIIF Manifest.
    :param req: A request object
    :param manifest_id: A UUID to look up in Solr
    :return: An HTTP Response object
    """
    return _parse_request(req, manifest_id, create_v2_manifest, create_v3_manifest)


@app.route("/iiif/canvas/<canvas_id:uuid>.json")
async def canvas(req, canvas_id: str) -> response.HTTPResponse:
    return _parse_request(req, canvas_id, create_v2_canvas, create_v3_canvas)


@app.route("/iiif/sequence/<sequence_id:uuid>_default.json")
async def sequence(req, sequence_id: str) -> response.HTTPResponse:
    # Sequences are deprecated in v3.
    return _parse_request(req, sequence_id, create_v2_sequence, None)


@app.route("/iiif/annotationlist/<annolist_id:uuid>.json")
async def annotation_list(req, annolist_id: str) -> response.HTTPResponse:
    return _parse_request(req, annolist_id, create_v2_annotation_list, None)


@app.route("/iiif/annotationpage/<annopage_id:uuid>.json")
async def annotation_page(req, annopage_id: str) -> response.HTTPResponse:
    return _parse_request(req, annopage_id, None, create_v3_annotation_page)


@app.route("/iiif/annotation/<annotation_id:uuid>.json")
async def annotation(req, annotation_id: str) -> response.HTTPResponse:
    return _parse_request(req, annotation_id, create_v2_annotation, create_v3_annotation)


@app.route(r"/iiif/collection/<collection_id:[^\s]+>")
async def collection(req, collection_id: str) -> response.HTTPResponse:
    return _parse_request(req, collection_id, create_v2_collection, create_v3_collection)


@app.route("/iiif/range/<object_id:uuid>/<range_id:string>")
async def iiif_range(req, object_id: str, range_id: str) -> response.HTTPResponse:
    return _parse_request(req, f'{object_id}/{range_id}', create_v2_range, create_v3_range)


# NB: Declaring the route parameter as an integer will also cast the page_id parameter to an integer.
@app.route("/iiif/activity/page-<page_id:int>")
async def iiif_activity_page(req, page_id: int) -> response.HTTPResponse:
    return _parse_activity_stream_request(req, page_id, create_ordered_collection_page)


@app.route("/iiif/activity/create/<manifest_id:uuid>")
async def iiif_create_activity(req, manifest_id: str) -> response.HTTPResponse:
    return _parse_activity_stream_request(req, manifest_id, create_activity)


@app.route("/iiif/activity/all-changes")
async def iiif_activity(req) -> response.HTTPResponse:
    return _parse_activity_stream_request(req, None, create_ordered_collection)
