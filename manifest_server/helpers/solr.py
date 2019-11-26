import logging
from typing import Optional, Dict, Iterator, NewType

import pysolr

log = logging.getLogger(__name__)

SolrResult = NewType('SolrResult', Dict)


class SolrManager:
    """
    Manages a Solr connection, allowing seamless iteration through paginated results:

        >>> m = SolrManager(pysolr.Solr("http://localhost/solr/core"))
        >>> m.search("*:*", fq=["type:something"], sort="some_i asc")
        >>> for r in m.results:
        ...     print(r)

    This will manage fetching the next page and results when needed. This class uses the cursorMark
    function, which returns a 'nextCursorMark' in the results objects to fetch the next page of results.
    Cursor marks are described in detail here:

    https://lucene.apache.org/solr/guide/7_1/pagination-of-results.html#fetching-a-large-number-of-sorted-results-cursors

    When calling the `.search()` method you should omit two parameters: `cursorMark` and a sort on
    the unique key (controlled using the SORT_STATEMENT parameter above). This will be added into the call prior
    to sending the query to Solr. Otherwise, the `.search()` method shadows the pysolr.Solr.search method, and the
    available arguments are the same. Unlike the pysolr.Solr.search method, however, it does not return a Result
    object -- the result object is managed by this class privately.

    Once `search()` has been called users can iterate through the `results` property and it will transparently
    fire off requests for the next page (technically, the next cursor mark) before yielding a result.
    """
    def __init__(self, solr_conn: pysolr.Solr, curs_sort_statement: str = "id asc") -> None:
        self._conn = solr_conn
        self._res: Optional[pysolr.Results] = None
        self._curs_sort_statement: str = curs_sort_statement
        self._hits: int = 0
        self._q: Optional[str] = None
        self._q_kwargs: Dict = {}
        self._cursorMark: str = "*"
        self._idx: int = 0
        self._page_idx: int = 0

    def search(self, q: str, **kwargs) -> None:
        """
        Shadows pysolr.Solr.search, but with additional housekeeping that manages
        the results object and stores the query parameters so that they can be used
        transparently in fetching pages.
        :param q: A default query parameter for Solr
        :param kwargs: Keyword arguments to pass along to pysolr.Solr.search
        :return: None
        """
        self._q = q
        self._q_kwargs = kwargs
        self._idx = 0
        self._page_idx = 0

        if "sort" in kwargs:
            self._q_kwargs['sort'] += f", {self._curs_sort_statement}"
        else:
            self._q_kwargs['sort'] = f"{self._curs_sort_statement}"

        self._cursorMark = "*"
        self._q_kwargs['cursorMark'] = self._cursorMark
        self._res = self._conn.search(q, **self._q_kwargs)
        self._hits = self._res.hits

    @property
    def hits(self) -> int:
        """
        Returns the number of hits found in response to a search.
        :return: Number of hits
        """
        if self._res is None:
            log.warning("A request for number of results was called before a search was initiated")

        return self._hits

    @property
    def results(self) -> Iterator[SolrResult]:
        """
        Provides a generator for pysolr.Results.docs, yielding
        the next result on every loop. In the case where the next result
        is on the next page, it will fetch the next page before yielding
        the first result on that page.
        :return: The full list of Solr results
        """
        if self._res is None:
            log.warning("A request for results was called before a search was initiated.")

        while self._idx < self._hits:
            try:
                yield self._res.docs[self._page_idx]  # type: ignore
            except IndexError:
                self._page_idx = 0
                self._cursorMark = self._res.nextCursorMark  # type: ignore
                self._q_kwargs['cursorMark'] = self._res.nextCursorMark  # type: ignore
                self._res = self._conn.search(self._q, **self._q_kwargs)
                self._hits = self._res.hits
                if self._res.docs:
                    yield self._res.docs[self._page_idx]
                else:
                    break

            self._page_idx += 1
            self._idx += 1
