from typing import List, Dict, Optional, Any
import serpy
import pysolr
from manifest_server.helpers.serializers import ContextDictSerializer
from manifest_server.helpers.fields import StaticField
from manifest_server.helpers.solr import SolrManager, SolrResult
from manifest_server.helpers.solr_connection import SolrConnection
from manifest_server.helpers.identifiers import get_identifier, IIIF_V2_CONTEXT


def create_v2_collection(request: Any, collection_id: str, config: Dict) -> Optional[Dict]:
    """
    Retrieves a collection object from Solr. Collection records are stored as `type:collection` in Solr
    and collection IDs are attached to individual objects. This method first retrieves the collection,
    and then passes it along to the Collection serializer, which will manage the retrieval of the individual
    members of the collection.

    A special case is the 'top' collection, which will retrieve a list of all other collections
    (except 'top' and 'all'). The 'all' collection is a list of every manifest object we have in the Solr core.

    Unlike in IIIF v3, a v2 Collection separates out the items into 'manifests' and 'collections'.

    :param request: A sanic request object
    :param collection_id: A collection id to retrieve.
    :param config: The configuration dict
    :return: A Dict representing a IIIF-serialized Collection.
    """

    fq: List = ["type:collection", f'collection_id:"{collection_id.lower()}"']
    rows: int = 1

    record: pysolr.Results = SolrConnection.search("*:*", fq=fq, rows=rows)

    if record.hits == 0:
        return None

    object_record = record.docs[0]
    collection: Collection = Collection(object_record, context={"request": request,
                                                                "config": config})

    return collection.data


class CollectionManifest(ContextDictSerializer):
    mid = serpy.MethodField(
        label="@id"
    )

    ctype = StaticField(
        label="@type",
        value="sc:Manifest"
    )

    label = serpy.StrField(
        attr="full_shelfmark_s"
    )
    thumbnail = serpy.MethodField()

    def get_mid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        manifest_id: str = obj.get('id')
        manifest_id_tmpl: str = cfg['templates']['manifest_id_tmpl']

        return get_identifier(req, manifest_id, manifest_id_tmpl)

    def get_thumbnail(self, obj: SolrResult) -> Optional[Dict]:
        image_uuid: str = obj.get('thumbnail_id')

        if not image_uuid:
            return None

        req = self.context.get('request')
        cfg = self.context.get('config')

        image_tmpl: str = cfg['templates']['image_id_tmpl']

        image_ident: str = get_identifier(req, image_uuid, image_tmpl)
        thumbsize: str = cfg['common']['thumbsize']

        thumb_service: Dict = {
            "@id": f"{image_ident}/full/{thumbsize},/0/default.jpg",
            "service": {
                "@context": "http://iiif.io/api/image/2/context.json",
                "profile": "http://iiif.io/api/image/2/level1.json",
                "@id": image_ident
            }
        }

        return thumb_service


class CollectionCollection(ContextDictSerializer):
    """
        Serializes a collection object for use in a nested collection.
    """
    cid = serpy.MethodField(
        label="@id"
    )
    ctype = StaticField(
        label="@type",
        value="sc:Collection"
    )
    label = serpy.StrField(
        attr="name_s"
    )
    description = serpy.StrField(
        attr="description_s"
    )

    def get_cid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')

        tmpl: str = cfg['templates']['collection_id_tmpl']
        cid: str = obj.get('collection_id')

        return get_identifier(req, cid, tmpl)


class Collection(ContextDictSerializer):
    ctx = StaticField(
        label="@context",
        value=IIIF_V2_CONTEXT
    )

    cid = serpy.MethodField(
        label="@id"
    )

    ctype = StaticField(
        label="@type",
        value="sc:Collection"
    )

    label = serpy.StrField(
        attr="name_s"
    )
    description = serpy.StrField(
        attr="description_s"
    )
    manifests = serpy.MethodField()
    collections = serpy.MethodField()

    def get_cid(self, obj: SolrResult) -> str:
        req = self.context.get('request')
        cfg = self.context.get('config')
        tmpl: str = cfg['templates']['collection_id_tmpl']
        cid: str = obj.get('collection_id')

        return get_identifier(req, cid, tmpl)

    def get_collections(self, obj: SolrResult) -> Optional[List]:
        coll_id: str = obj.get('collection_id')
        req = self.context.get('request')
        cfg = self.context.get('config')

        manager: SolrManager = SolrManager(SolrConnection)
        fq: List = ["type:collection", f"parent_collection_id:{coll_id}"]
        fl: List = ['id', 'name_s', 'description_s', 'collection_id', 'parent_collection_id']
        sort: str = "name_s asc"
        rows: int = 100

        manager.search("*:*", fq=fq, fl=fl, sort=sort, rows=rows)

        if manager.hits == 0:
            return None

        return CollectionCollection(manager.results, many=True, context={'request': req,
                                                                         'config': cfg}).data

    def get_manifests(self, obj: SolrResult) -> Optional[List]:
        coll_id: str = obj.get('collection_id')

        req = self.context.get('request')
        cfg = self.context.get('config')

        manager: SolrManager = SolrManager(SolrConnection)

        # The 'All' collection is for every object in the collection, so we
        # don't need to restrict it by collection.
        if coll_id == 'all':
            fq = ["type:object"]
        else:
            fq = ["type:object", f"all_collections_id_sm:{coll_id}"]

        sort: str = "institution_label_s asc, shelfmark_sort_ans asc"
        rows: int = 100
        fl = ["id", "title_s", "full_shelfmark_s", "thumbnail_id"]

        manager.search("*:*", fq=fq, sort=sort, fl=fl, rows=rows)

        if manager.hits == 0:
            return None

        return CollectionManifest(manager.results, many=True, context={'request': req,
                                                                       'config': cfg}).data
