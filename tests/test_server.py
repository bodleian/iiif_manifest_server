from manifest_server.server import app

# @pytest.fixture
# def client():
#     return testing.TestClient(application)


def test_root_response():
    """Ensure an info file gets served on the root."""
    request, response = app.test_client.get("/info.json")
    assert response.status == 200


def test_no_manifest_id():
    """ No manifest ID should raise a 404 Not Found. """
    request, response = app.test_client.get("/iiif/manifest")
    assert response.status == 404


def test_manifest_fetch():
    request, response = app.test_client.get("/iiif/manifest/f1b545b1-623c-4e4c-a49e-18ea5a39e1a1.json")
    assert response.status == 200


def test_bad_manifest_id():
    request, response = app.test_client.get("/iiif/manifest/foo.json")
    assert response.status == 404


def test_talbot_manifest_fetch():
    """
    Make sure items filtered out of the main select handler are still accessible
    """
    request, response = app.test_client.get("/iiif/manifest/452d6b51-949c-447d-9880-1108ffdfd96e.json")
    assert response.status == 200


# V2 manifests MUST be sent with a plain application/json response unless ld+json is specifically
# requested.
def test_v2_implicit_manifest_retrieval():
    request, response = app.test_client.get("/iiif/manifest/f1b545b1-623c-4e4c-a49e-18ea5a39e1a1.json")
    content_type = response.headers.get('Content-Type')
    assert 'presentation/2' not in content_type
    assert 'ld+json' not in content_type


def test_v2_explicit_manifest_retrieval():
    accept_hdr = "application/json"
    request, response = app.test_client.get("/iiif/manifest/f1b545b1-623c-4e4c-a49e-18ea5a39e1a1.json",
                                            headers={"Accept": accept_hdr})
    content_type = response.headers.get('Content-Type')
    assert 'presentation/2' not in content_type


def test_v2_jsonld_request():
    accept_hdr = "application/ld+json"
    request, response = app.test_client.get("/iiif/manifest/f1b545b1-623c-4e4c-a49e-18ea5a39e1a1.json",
                                            headers={"Accept": accept_hdr})
    content_type = response.headers.get('Content-Type')
    assert "ld+json" in content_type


def test_v3_no_manifest_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/manifest/f1b545b1-623c-4e4c-a49e-18ea5a39e1b1.json",
                                            headers={"Accept": accept_hdr})
    assert response.status == 404


def test_v3_explicit_manifest_retrieval():
    accept_hdr = "application/json"
    request, response = app.test_client.get("/iiif/manifest/f1b545b1-623c-4e4c-a49e-18ea5a39e1a1.json",
                                            headers={"Accept": accept_hdr})
    content_type = response.headers.get('Content-Type')
    assert 'presentation/3' not in content_type


def test_v3_jsonld_request():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/manifest/f1b545b1-623c-4e4c-a49e-18ea5a39e1a1.json",
                                            headers={"Accept": accept_hdr})
    content_type = response.headers.get('Content-Type')
    assert "ld+json" in content_type
    assert "presentation/3" in content_type


def test_v3_unacceptable_header():
    # Tests retrieving a v2 object with a v3 Accept.
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/sequence/a0c0c7ac-30ae-4f4f-9002-57f562410453_default.json",
                                            headers={"Accept": accept_hdr})
    assert response.status == 406


def test_v2_canvas_fetch():
    request, response = app.test_client.get("/iiif/canvas/a0c0c7ac-30ae-4f4f-9002-57f562410453.json")
    assert response.status == 200


def test_v3_canvas_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/canvas/a0c0c7ac-30ae-4f4f-9002-57f562410453.json",
                                            headers={"Accept": accept_hdr})
    content_type = response.headers.get('Content-Type')
    assert "presentation/3" in content_type
    assert response.status == 200


def test_v3_image_annotationpage_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/annotationpage/a0c0c7ac-30ae-4f4f-9002-57f562410453.json",
                                            headers={"Accept": accept_hdr})
    content_type = response.headers.get('Content-Type')
    assert "presentation/3" in content_type
    assert response.status == 200


def test_v3_text_annotationpage_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/annotationpage/dd0a4bdd-9e48-4add-b604-43e9674851b6.json",
                                            headers={"Accept": accept_hdr})
    content_type = response.headers.get('Content-Type')
    assert "presentation/3" in content_type
    assert response.status == 200


def test_v2_image_annotation_fetch():
    request, response = app.test_client.get("/iiif/annotation/a0c0c7ac-30ae-4f4f-9002-57f562410453.json")
    assert response.status == 200


def test_v3_image_annotation_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/annotation/a0c0c7ac-30ae-4f4f-9002-57f562410453.json",
                                            headers={"Accept": accept_hdr})
    content_type = response.headers.get('Content-Type')
    assert "presentation/3" in content_type
    assert response.status == 200


def test_v2_text_annotation_fetch():
    request, response = app.test_client.get("/iiif/annotation/04db9bdb-2597-4d8f-b8fa-6cbd15ad5e3f.json")
    assert response.status == 200


def test_v2_multilingual_text_annotation_fetch():
    request, response = app.test_client.get("/iiif/annotation/3aafd4b7-479d-43da-be7f-dde9f339d5b7.json")
    assert response.status == 200


def test_v3_text_annotation_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/annotation/04db9bdb-2597-4d8f-b8fa-6cbd15ad5e3f.json",
                                            headers={"Accept": accept_hdr})
    content_type = response.headers.get('Content-Type')
    assert "presentation/3" in content_type
    assert response.status == 200


def test_v3_multilingual_text_annotation_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/annotation/3aafd4b7-479d-43da-be7f-dde9f339d5b7.json",
                                            headers={"Accept": accept_hdr})
    content_type = response.headers.get('Content-Type')
    assert "presentation/3" in content_type
    assert response.status == 200


def test_v2_annotation_list_fetch():
    request, response = app.test_client.get("/iiif/annotationlist/dd0a4bdd-9e48-4add-b604-43e9674851b6.json")
    assert response.status == 200


def test_v2_manifest_with_annotation_list_fetch():
    request, response = app.test_client.get("/iiif/manifest/14ec0ba2-b25b-4fb9-a430-6bce15c2b4ce.json")
    assert response.status == 200


def test_v3_manifest_with_annotation_page_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/manifest/14ec0ba2-b25b-4fb9-a430-6bce15c2b4ce.json",
                                            headers={"Accept": accept_hdr})
    assert response.status == 200


def test_v2_sequence_fetch():
    request, response = app.test_client.get("/iiif/sequence/f1b545b1-623c-4e4c-a49e-18ea5a39e1a1_default.json")
    assert response.status == 200


def test_v3_sequence_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/sequence/f1b545b1-623c-4e4c-a49e-18ea5a39e1a1_default.json",
                                            headers={"Accept": accept_hdr})
    assert response.status == 406


def test_v2_structure_fetch():
    request, response = app.test_client.get("/iiif/range/87923c49-c0db-4cba-aed8-a6bff34633c0/LOG_0102")
    assert response.status == 200


def test_v2_image_range_in_metadata_fetch():
    # Copernicus et al, 1661, The systeme of the world in four dialogues…
    request, response = app.test_client.get("/iiif/range/b760b2a3-e687-466c-8471-618f8356afb6/LOG_0006")
    assert response.status == 200
    image_range = response.json.get('metadata')[0].get("value")
    assert image_range == 'verso'


def test_v3_structure_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/range/87923c49-c0db-4cba-aed8-a6bff34633c0/LOG_0102",
                                            headers={"Accept": accept_hdr})
    assert response.status == 200


def test_v3_range_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    # Copernicus et al, 1661, The systeme of the world in four dialogues…
    request, response = app.test_client.get("/iiif/range/b760b2a3-e687-466c-8471-618f8356afb6/LOG_0006",
                                            headers={"Accept": accept_hdr})
    assert response.status == 200
    description = response.json.get('metadata')[2].get("value")
    assert description == {'en': ['Dedication to the most serene Grand Duke of Tuscany (verso; immediately after title-page).',
                                  'Printed by William Leybourne.']}


def test_v3_image_range_in_metadata_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    # Copernicus et al, 1661, The systeme of the world in four dialogues…
    request, response = app.test_client.get("/iiif/range/b760b2a3-e687-466c-8471-618f8356afb6/LOG_0006",
                                            headers={"Accept": accept_hdr})
    assert response.status == 200
    image_range = response.json.get('metadata')[0].get("value")
    assert image_range == {'en': ['verso']}


def test_invalid_range_request():
    request, response = app.test_client.get("/iiif/range/87923c49-c0db-4cba-aed8-a6bff34633c0/LOG_0102/Foo/bar/baz")
    assert response.status == 404


def test_v2_collection_fetch():
    request, response = app.test_client.get("/iiif/collection/maps")
    assert response.status == 200


def test_v3_collection_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/collection/maps",
                                            headers={"Accept": accept_hdr})
    content_type = response.headers.get('Content-Type')
    assert "presentation/3" in content_type
    assert response.status == 200


def test_v2_all_collection_fetch():
    request, response = app.test_client.get("/iiif/collection/all")
    assert response.status == 200


def test_v2_top_collection_fetch():
    request, response = app.test_client.get("/iiif/collection/top")
    assert response.status == 200


def test_v3_all_collection_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/collection/all",
                                            headers={"Accept": accept_hdr})
    assert response.status == 200


def test_v3_top_collection_fetch():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/collection/top",
                                            headers={"Accept": accept_hdr})
    assert response.status == 200


def test_v2_fake_collection():
    request, response = app.test_client.get("/iiif/collection/flibflab")
    assert response.status == 404


def test_v3_fake_collection():
    accept_hdr = "application/ld+json;profile=http://iiif.io/api/presentation/3/context.json"
    request, response = app.test_client.get("/iiif/collection/flibflab",
                                            headers={"Accept": accept_hdr})
    assert response.status == 404


def test_activity_streams_top():
    request, response = app.test_client.get("/iiif/activity/all-changes")
    assert response.status == 200


def test_activity_streams_collection_page():
    request, response = app.test_client.get("/iiif/activity/page-10")
    assert response.status == 200


def test_activity_streams_collection_first_page():
    request, response = app.test_client.get("/iiif/activity/page-0")
    assert response.status == 200


def test_activity_streams_collection_last_page():
    # The last page will change depending on the number of results, so
    # we fetch it from the top activity stream page first.
    request, response = app.test_client.get("/iiif/activity/all-changes")
    last = response.json.get("last")
    req2, resp2 = app.test_client.get(last['id'])
    assert resp2.status == 200


def test_activity_streams_activity_page():
    request, response = app.test_client.get("/iiif/activity/create/5c7b2cfa-b8cb-469d-8895-1463513f28d0")
    assert response.status == 200


def test_activity_streams_not_found():
    request, response = app.test_client.get("/iiif/activity/create/blah")
    assert response.status == 404


def test_invalid_manifest_uuid():
    request, response = app.test_client.get("/iiif/manifest/3A18896580-65E5-11E0-A8FC-EAAAA2B3687C:DS.3.json")
    assert response.status == 404


def test_invalid_canvas_uuid():
    request, response = app.test_client.get("/iiif/canvas/3A18896580-65E5-11E0-A8FC-EAAAA2B3687C:DS.3.json")
    assert response.status == 404


def test_invalid_sequence_uuid():
    request, response = app.test_client.get("/iiif/sequence/3A18896580-65E5-11E0-A8FC-EAAAA2B3687C:DS.3.json")
    assert response.status == 404


def test_invalid_annotation_list_uuid():
    request, response = app.test_client.get("/iiif/annotationlist/3A18896580-65E5-11E0-A8FC-EAAAA2B3687C:DS.3.json")
    assert response.status == 404


def test_invalid_annotation_page_uuid():
    request, response = app.test_client.get("/iiif/annotationpage/3A18896580-65E5-11E0-A8FC-EAAAA2B3687C:DS.3.json")
    assert response.status == 404


def test_invalid_annotation_uuid():
    request, response = app.test_client.get("/iiif/annotation/3A18896580-65E5-11E0-A8FC-EAAAA2B3687C:DS.3.json")
    assert response.status == 404


def test_invalid_collection_id_spaces():
    request, response = app.test_client.get("/iiif/collection/oriental AND type:collection")
    assert response.status == 404


def test_collection_id_single_word_hyphens():
    request, response = app.test_client.get("/iiif/collection/early-modern-and-modern-manuscripts")
    assert response.status == 200


def test_collection_id_single_word():
    request, response = app.test_client.get("/iiif/collection/papyri")
    assert response.status == 200


def test_invalid_collection_id_second_word():
    request, response = app.test_client.get("/iiif/collection/foo all")
    assert response.status == 404


def test_invalid_collection_id_first_word():
    request, response = app.test_client.get("/iiif/collection/all foo")
    assert response.status == 404


def test_invalid_collection_id_slashes():
    request, response = app.test_client.get("/iiif/collection/all/foo")
    assert response.status == 404


def test_invalid_collection_id_colons():
    request, response = app.test_client.get("/iiif/collection/all::foo")
    assert response.status == 404


def test_invalid_collection_id_backslashes():
    request, response = app.test_client.get(r"/iiif/collection/all\\")
    assert response.status == 404


def test_invalid_collection_id_quotes():
    request, response = app.test_client.get(r"/iiif/collection/all\" AND t:t")
    assert response.status == 404


def test_invalid_collection_id_s_in_word():
    request, response = app.test_client.get("/iiif/collection/maps")
    assert response.status == 200


def test_invalid_range_colons():
    request, response = app.test_client.get("/iiif/range/3A18896580-65E5-11E0-A8FC-EAAAA2B3687C:DS.3./LOG_0102")
    assert response.status == 404


def test_invalid_range_backslashes():
    request, response = app.test_client.get("/iiif/range/3A18896580-65E5-11E0-A8FC-EAAAA2B3687C\\DS.3./LOG_0102")
    assert response.status == 404


def test_invalid_range_quotes():
    request, response = app.test_client.get("/iiif/range/3A18896580-65E5-11E0-A8FC-EAAAA2B3687C\"DS.3./LOG_0102")
    assert response.status == 404
    

def test_valid_range():
    request, response = app.test_client.get("/iiif/range/748a9d50-5a3a-440e-ab9d-567dd68b6abb/LOG_0000")
    assert response.status == 200
