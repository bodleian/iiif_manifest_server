from typing import Optional, Dict, List, Any

import pysolr
import serpy

from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.identifiers import get_identifier, IIIF_V3_CONTEXT
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.solr import SolrManager, SolrResult
from manifest_server.helpers.solr_connection import SolrConnection


def create_v3_collection(request: Any, collection_id: str, config: Dict) -> Optional[Dict]:
    """
    Retrieves a collection object from Solr. Collection records are stored as `type:collection` in Solr
    and collection IDs are attached to individual objects. This method first retrieves the collection,
    and then passes it along to the Collection serializer, which will manage the retrieval of the individual
    members of the collection.

    A special case is the 'top' collection, which will retrieve a list of all other collections
    (except 'top' and 'all'). The 'all' collection is a list of every manifest object we have in the Solr core.

    :param request: A sanic request object
    :param collection_id: A collection id to retrieve.
    :param config: The configuration dictionary
    :return: A Dict representing a IIIF-serialized Collection.
    """
    fq: List = ["type:collection", f'collection_id:"{collection_id.lower()}"']
    record: pysolr.Results = SolrConnection.search("*:*", fq=fq, rows=1)

    if record.hits == 0:
        return None

    object_record = record.docs[0]
    collection: Collection = Collection(object_record, context={"request": request,
                                                                "config": config})

    return collection.data


class CollectionCollection(ContextDictSerializer):
    """
        A Collection entry in the items list.
    """
    cid = serpy.MethodField(
        label="id"
    )
    type = StaticField(
        value="Collection"
    )
    label = serpy.MethodField()

    def get_cid(self, obj: Dict) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')

        iid: str = obj.get('collection_id')
        tmpl: str = cfg['templates']['collection_id_tmpl']

        return get_identifier(req, iid, tmpl)

    def get_label(self, obj: Dict) -> Dict:
        name: str = obj.get('name_s')
        return {'en': [f"{name}"]}


class CollectionManifest(ContextDictSerializer):
    """
        A Manifest entry in the items list.
    """
    mid = serpy.MethodField(
        label="id"
    )

    label = serpy.StrField(
        attr="full_shelfmark_s"
    )
    type = StaticField(
        value="Manifest"
    )
    thumbnail = serpy.MethodField()

    def get_mid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')

        iid: str = obj.get('id')
        tmpl: str = cfg['templates']['manifest_id_tmpl']

        return get_identifier(req, iid, tmpl)

    def get_thumbnail(self, obj: SolrResult) -> Optional[List]:
        image_uuid: str = obj.get('thumbnail_id')

        if not image_uuid:
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')

        image_tmpl: str = cfg['templates']['image_id_tmpl']

        image_ident: str = get_identifier(req, image_uuid, image_tmpl)
        thumbsize: str = cfg['common']['thumbsize']

        thumb_service: List = [{
            "@id": f"{image_ident}/full/{thumbsize},/0/default.jpg",
            "service": {
                "type": "ImageService2",
                "profile": "level1",
                "@id": image_ident
            }
        }]

        return thumb_service


class Collection(ContextDictSerializer):
    """
        A top-level IIIF Collection object.
    """
    ctx = StaticField(
        label="@context",
        value=IIIF_V3_CONTEXT
    )
    cid = serpy.MethodField(
        label="id"
    )

    ctype = StaticField(
        label="type",
        value="Collection"
    )

    label = serpy.MethodField()
    summary = serpy.MethodField()
    items = serpy.MethodField()

    def get_cid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        tmpl: str = cfg['templates']['collection_id_tmpl']
        cid: str = obj.get('collection_id')

        return get_identifier(req, cid, tmpl)

    def get_label(self, obj: SolrResult) -> Dict:
        return {"en": [f"{obj.get('name_s')}"]}

    def get_summary(self, obj: SolrResult) -> Dict:
        return {"en": [f"{obj.get('description_s')}"]}

    def get_items(self, obj: SolrResult) -> List:
        """
        Gets a list of the child items. In v3 manifests this will either be Manifest objects or Collection objects.

        !!! NB: A collection will ONLY have manifests or Collections. The Solr index does not support mixed
            manifest and sub-collections !!!

        Two Solr queries are necessary to determine whether what is being requested is a parent collection (in
        which case the parent_collection_id field will match the requested path) OR a set of Manifests (in
        which case the first query will return 0 results, and then we re-query for the list of objects.)

        :param obj: A dict representing the Solr record for that collection.
        :return: A list of objects for the `items` array in the Collection.
        """
        req = self.context.get('request')
        cfg = self.context.get('config')

        manager: SolrManager = SolrManager(SolrConnection)
        coll_id: str = obj.get('collection_id')

        # first try to retrieve sub-collections (collections for which this is a parent)
        fq = ["type:collection", f"parent_collection_id:{coll_id}"]
        fl = ["id", "name_s", "description_s", "type", "collection_id"]
        rows: int = 100

        manager.search("*:*", fq=fq, fl=fl, rows=rows, sort="name_s asc")

        if manager.hits > 0:
            # bingo! it was a request for a sub-collection.
            return CollectionCollection(manager.results, many=True, context={'request': req,
                                                                             'config': cfg}).data

        # oh well; retrieve the manifest objects.
        fq = ["type:object", f"all_collections_id_sm:{coll_id}"]
        fl = ["id", "title_s", "full_shelfmark_s", "type"]
        sort = "institution_label_s asc, shelfmark_sort_ans asc"

        manager.search("*:*", fq=fq, fl=fl, rows=rows, sort=sort)

        return CollectionManifest(manager.results, many=True, context={'request': req,
                                                                       'config': cfg}).data
