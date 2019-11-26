import logging
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.server import app
from tripoli import IIIFValidator

log = logging.getLogger(__name__)


def test_check_manifest_sample_is_valid():
    res = SolrConnection.search("*:*", fq=["type:object"], fl=["id"], rows=3)

    for obj in res.docs:
        assert check_manifest(obj['id'], v3=False)
        assert check_manifest(obj['id'], v3=True)


def check_manifest(uuid: str, v3: bool):
    url = f"/iiif/manifest/{uuid}.json"
    if v3:
        accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
        request, response = app.test_client.get(url, headers={"Accept": accept_hdr})
    else:
        request, response = app.test_client.get(url)

    if response.status != 200:
        log.error(f"Status {response.status} when accessing {url} in {'v3' if v3 else 'v2'}")
        return False

    if not v3:
        # Tripoli only supports v2 manifests at the moment
        iv = IIIFValidator()
        iv.validate(response.text)
        if not iv.is_valid:
            log.error(f"v2 {url} was invalid: {';'.join([str(e) for e in iv.errors])}")
            return False
        if len(iv.warnings) > 0:
            log.warning(f"v2 {url} validation warnings: {';'.join([str(w) for w in iv.warnings])}")

    return True
