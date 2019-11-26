from manifest_server.server import app
import ujson as json


def test_presentation_2_response_context():
    request, response = app.test_client.get("/iiif/manifest/f1b545b1-623c-4e4c-a49e-18ea5a39e1a1.json")
    assert response.json.get('@context') == "http://iiif.io/api/presentation/2/context.json"


def test_presentation_3_response_context():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/manifest/f1b545b1-623c-4e4c-a49e-18ea5a39e1a1.json",
                                            headers={"Accept": accept_hdr})
    # this, being an ld+json response type, only comes in the body.
    ctx = json.loads(response.body).get('@context')
    assert "http://iiif.io/api/presentation/3/context.json" in ctx
    assert "http://www.w3.org/ns/anno.jsonld" in ctx


def test_structures_in_v2_response():
    request, response = app.test_client.get("/iiif/manifest/87923c49-c0db-4cba-aed8-a6bff34633c0.json")
    structures = response.json.get("structures")
    assert structures is not None
    assert len(structures) > 0


def test_structures_in_v3_response():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/manifest/87923c49-c0db-4cba-aed8-a6bff34633c0.json",
                                            headers={"Accept": accept_hdr})
    structures = response.json.get("structures")
    assert structures is not None
    assert len(structures) > 0


def test_v2_collection_all():
    request, response = app.test_client.get("/iiif/collection/all")
    manifests = response.json.get('manifests', None)
    collections = response.json.get('collections', None)
    assert len(manifests) > 0
    assert collections is None


def test_v2_collection_top():
    request, response = app.test_client.get('/iiif/collection/top')
    manifests = response.json.get('manifests', None)
    collections = response.json.get('collections', None)
    assert manifests is None
    assert len(collections) > 0


def test_metadata_ordering():
    # Tests the order of metadata fields. This is a fairly brute-force test that simply checks whether the metadata
    # block matches the expected order. If it fails, it may not be that the IIIF manifest is wrong, it's just
    # that something has happened that changes the order of the keys.
    expected_order = [
        "Homepage",
        "Additional Information",
        "Author",
        "Illustrator",
        "Language",
        "Language",
        "Language",
        "Date Statement",
        "Description",
        "Description",
        "Record Origin",
        "Collection",
        "Record Created",
        "Holding Institution",
    ]

    request, response = app.test_client.get('/iiif/manifest/ae9f6cca-ae5c-4149-8fe4-95e6eca1f73c.json')
    metadata = response.json.get('metadata')

    assert len(metadata) == len(expected_order)
    for i, field_dict in enumerate(metadata):
        assert field_dict['label'] == expected_order[i]
