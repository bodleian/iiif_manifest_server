import pysolr

from manifest_server.helpers.solr import SolrManager
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.metadata import get_links


def test_solr_manager_initial_state():
    m = SolrManager(pysolr.Solr("http://digital1-qa-solr1.bodleian.ox.ac.uk:8983/solr/digital_bodleian_ingest"))
    # Trigger the warnings
    assert m._res is None
    assert m.hits == 0


def test_context_serializer_without_context():
    # Trigger the 'no context in kwargs' branch
    m = ContextDictSerializer({})
    assert True


def test_get_links():
    link_obj = {
        "id": "6172cfa3-9f7c-4120-9a3a-8751b7913961",
    }

    v2_response = get_links(link_obj, 2)  # type: ignore
    v3_response = get_links(link_obj, 3)  # type: ignore

    v2_response_value = v2_response[0]['value']
    assert v2_response_value == "<a href=\"http://medieval-qa.bodleian.ox.ac.uk/catalog/manuscript_100\">Catalogue of Western Medieval Manuscripts in Oxford Libraries</a>"

    v3_response_value = v3_response[0]['value']['en'][0]
    assert v3_response_value == "<a href=\"http://medieval-qa.bodleian.ox.ac.uk/catalog/manuscript_100\">Catalogue of Western Medieval Manuscripts in Oxford Libraries</a>"
