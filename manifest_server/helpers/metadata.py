from typing import List, Dict, Optional
from manifest_server.helpers.solr import SolrManager, SolrResult
from manifest_server.helpers.solr_connection import SolrConnection


# Map Solr fields to IIIF Metadata fields.
# The order of the fields here controls the order of fields as
# they will appear in the metadata block of the IIIF manifests.
FIELD_CONFIG: Dict[str, str] = {
    "title_s": "Title",
    "other_titles_sm": "Other Titles",
    "volume_s": "Volume",
    # person roles
    "creators_sm": "Creator",
    "contributors_sm": "Contributor",
    "authors_sm": "Author",
    "composers_sm": "Composer",
    "artists_sm": "Artist",
    "attributed_artists_sm": "Attributed Artist",
    "follower_of_artists_sm": "Artist (Follower of)",
    "studio_of_artists_sm": "Artist (Studio of)",
    "school_of_artists_sm": "Artist (School of)",
    "art_copyists_sm": "Copy by",
    "after_artists_sm": "After",
    "formerly_attributed_artists_sm": "Formerly Attributed Artist",
    "architects_sm": "Architect",
    "draughtsmen_sm": "Draughtsman",
    "sitters_sm": "Sitter",
    "illustrators_sm": "Illustrator",
    "publishers_sm": "Publisher",
    "printers_sm": "Printer",
    "translators_sm": "Translator",
    "editors_sm": "Editors",
    "scribes_sm": "Scribe",
    "commentators_sm": "Commentators",
    "annotators_sm": "Annotator",
    "arrangers_sm": "Arranger",
    "compilers_sm": "Compiler",
    "engravers_sm": "Engraver",
    "cartographers_sm": "Cartographer",
    "surveyors_sm": "Surveyor",
    "former_owners_sm": "Former Owner",
    "patrons_sm": "Patron",
    "photographers_sm": "Photographer",
    "photography_studios_sm": "Photography Studio",
    "witnesses_sm": "Witness",
    # end person roles
    "languages_sm": "Language",
    "date_statement_sm": "Date Statement",
    "origins_sm": "Place of Origin",
    "description_sm": "Description",
    "contents_sm": "Contents",
    "contents_note_sm": "Contents Note",
    "format_sm": "Format",
    "materials_sm": "Materials",
    "layout_sm": "Layout",
    "hands_sm": "Hand",
    "inscriptions_sm": "Inscription",
    "signed_sm": "Signed",
    "counties_sm": "County",
    "watermarks_sm": "Watermark",
    "musical_notation_sm": "Musical Notation",
    "extent_sm": "Extent",
    "collation_sm": "Collation",
    "scale_sm": "Scale",
    "dimensions_sm": "Dimensions",
    "decoration_sm": "Decoration",
    "binding_sm": "Binding",
    "incipits_sm": "Incipit",
    "provenance_sm": "Provenance",
    "bod_accession_date_sm": "Accession Date",
    "bod_accession_source_sm": "Accession Source",
    "bod_accession_type_sm": "Accession Type",
    "origin_note_sm": "Origin Note",
    "exhibition_history_sm": "Exhibited",
    "location_note_sm": "Location Note",
    "record_origin_sm": "Record Origin",
    "collections_sm": "Collection",
    "subjects_sm": "Subject",
    "catalogue_description_sm": "Catalogue Description",
    "catalogue_identifiers_sm": "Catalogue Identifier",
    "catalogue_url_smni": "Catalogue Link",
    "other_identifiers_sm": "Other Identifier",
    "related_items_sm": "Related Items",
    "digitization_note_sm": "Digitization note",
    "digitization_project_s": "Digitization Project",
    "acknowledgements_sm": "Acknowledgements",
    "sponsors_sm": "Digitization Sponsor",
    "accessioned_dt": "Record Created",
    "holding_institution_s": "Holding Institution"
}

CANVAS_FIELD_CONFIG: Dict[str, str] = {
    "work_titles_sm": "Title",
    **FIELD_CONFIG
}

WORKS_METADATA_FIELD_CONFIG: Dict[str, str] = {
    "image_range_s": "Image Range",
    **FIELD_CONFIG
}

WORKS_METADATA_FILTER_FIELDS: List = [
    'work_id',
    'parent_work_id',
    'work_title_s',
    'surfaces_sm',
    'object_id'
] + list(WORKS_METADATA_FIELD_CONFIG.keys())


def get_links(obj: SolrResult, version: int) -> List:
    conn: SolrManager = SolrManager(SolrConnection)
    fq: List = ['type:link', f"object_id:{obj.get('id')}"]

    conn.search("*:*", fq=fq)

    if conn.hits == 0:
        return []

    lnks: List = []

    for r in conn.results:
        if version == 2:
            lnk = format_v2_related_links(r)
        else:
            lnk = format_v3_related_links(r)

        lnks += lnk

    return lnks


def format_v2_related_links(res: Dict) -> List:
    """
    Format a list of Solr 'link' documents for inclusion in the v3 metadata block.

    :param res: A Solr 'link' document result
    :return: A list of formatted links to be added to the metadata block.
    """
    return [{"label": "Additional Information",
             "value": f"<a href=\"{res.get('target_s')}\">{res.get('label_s')}</a>"}]


def v2_metadata_block(obj: SolrResult, field_config: Optional[Dict[str, str]] = None) -> Optional[List[Dict]]:
    """
    A helper method for constructing the manifest metadata block.
    Separated from the main manifest constructor to hide a lot of messy configuration and implementation.

    :param obj: A dictionary object containing values for metadata
    :param field_config: A dictionary of solr fields to manifest fields. Defaults to the one for manifest level metadata
    :return: A dictionary suitable for use in the IIIF metadata block.
    """
    if not field_config:
        field_config = FIELD_CONFIG

    metadata: List = []

    for field, label in field_config.items():
        val = obj.get(field, None)

        if not val:
            continue

        if isinstance(val, list):
            fval = [{"label": label, "value": v} for v in val]
        else:
            fval = [{"label": label, "value": val}]

        metadata += fval

    return metadata or None


def format_v3_related_links(res: Dict) -> List:
    """
    Format a list of Solr 'link' documents for inclusion in the v3 metadata block.

    :param res: A Solr 'link' document result
    :return: A list of formatted links to be added to the metadata block.
    """
    return [{"label": {"en": ["Additional Information"]},
             "value": {"en": [f"<a href=\"{res.get('target_s')}\">{res.get('label_s')}</a>"]}}]


def v3_metadata_block(obj: SolrResult, field_config: Optional[Dict[str, str]] = None) -> Optional[List[Dict]]:
    """
    A helper method for returning a IIIF Prezi3 metadata block. The main difference
    between this and the previous version is that all labels will come with a language value
    and be rendered as a list of values instead of a singleton.

    :param obj: A dictionary object containing metadata values
    :param field_config: A dictionary of solr fields to manifest fields. Defaults to the one for manifest level metadata
    :return: A list of Metadata labels and values to be embedded in a manifest.
    """
    if not field_config:
        field_config = FIELD_CONFIG

    metadata: List = []

    for field, label in field_config.items():
        val = obj.get(field, None)

        if not val:
            continue

        if isinstance(val, list):
            fval = [{"label": {"en": [label]}, "value": {"en": val}}]
        else:
            fval = [{"label": {"en": [label]}, "value": {"en": [val]}}]
        metadata += fval

    return metadata or None
