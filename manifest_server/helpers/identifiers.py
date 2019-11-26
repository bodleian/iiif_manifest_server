from typing import List, Dict, Any

IIIF_CONTEXT_STR: str = "http://iiif.io/api/presentation/{iiif_version}/context.json"
IIIF_DISCOVERY_STR: str = "http://iiif.io/api/discovery/0/context.json"

IIIF_V2_CONTEXT: str = IIIF_CONTEXT_STR.format(iiif_version=2)
IIIF_V3_CONTEXT: List = [
    "http://www.w3.org/ns/anno.jsonld",
    IIIF_CONTEXT_STR.format(iiif_version=3)
]

IIIF_ASTREAMS_CONTEXT: List = [
    IIIF_DISCOVERY_STR,
    "https://www.w3.org/ns/activitystreams"
]

# A constant definition of The Bodleian's VIAF entry
IIIF_ASTREAMS_ACTOR: Dict = {
    "id": "http://viaf.org/viaf/173632201",
    "type": "Organization"
}


def get_identifier(request: Any, identifier: str, template: str, range_id=None) -> str:
    """
    Takes a request object, parses it out, and returns a templated identifier suitable
    for use in an "id" field, including the incoming request information on host and scheme (http/https).

    :param request: A Sanic request object
    :param identifier: An identifier (typically containing a UUID) to template
    :param template: A string containing formatting variables
    :param range_id: An optional string corresponding to a range ID (used to create identifiers for ranges)
    :return: A templated string
    """
    fwd_scheme_header = request.headers.get('X-Forwarded-Proto')
    fwd_host_header = request.headers.get('X-Forwarded-Host')

    scheme = fwd_scheme_header if fwd_scheme_header else request.scheme
    host = fwd_host_header if fwd_host_header else request.host

    if range_id:
        return template.format(scheme=scheme, host=host, identifier=identifier, range=range_id)

    return template.format(scheme=scheme, host=host, identifier=identifier)
