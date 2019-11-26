import logging

from manifest_server.helpers.solr_connection import SolrConnection
from tests.test_manifest_validity import check_manifest
from manifest_server.helpers.solr import SolrManager

log = logging.getLogger(__name__)
fh = logging.FileHandler('errors.log')
fh.setLevel(logging.WARNING)
formatter = logging.Formatter('[%(asctime)s] [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)')
fh.setFormatter(formatter)
log.addHandler(fh)


def check_all_manifests():
    """
    Check *all* manifests for validity. Takes a long time
    :return:
    """
    manager: SolrManager = SolrManager(SolrConnection)
    manager.search("*:*", fq=["type:object"], fl=["id"], rows=100)
    successes = 0
    failures = 0

    for object_id in manager.results:
        succeeded = check_manifest(object_id['id'], v3=False)
        succeeded &= check_manifest(object_id['id'], v3=True)
        if succeeded:
            successes += 1
        else:
            failures += 1

    total = successes + failures
    log.info(f"{successes} successes, {failures} failures, {total} total, {(successes/total)*100:.2f}% successful")


if __name__ == "__main__":
    check_all_manifests()
