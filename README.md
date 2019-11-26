# Manifest Microservice

This project is the Digital Bodleian IIIF Manifest microservice. It serves both 2.1 and 3.0
IIIF manifests by transforming them from a Solr index into a JSON-LD document. 

## Installation

This project requires pipenv and Python 3.6+.

Install and configure a Python virtual environment:

```
  $> pipenv --python 3.6
  $> pipenv install
```

Configuration parameters can be set by copying `configuration.yml.tmpl` to `configuration.yml` and
changing the values accordingly.

The manifest server can be run with gunicorn. Run `pipenv shell` to enter the virtual environment
shell and then:

`(venv) $> gunicorn --reload manifest_server.server:app --worker-class sanic.worker.GunicornWorker -b localhost:8001`

## Notes for the Open Source version

We have open-sourced this code for reference purposes. It is highly unlikely that it will work out-of-the-box, since it is closely tied to the underlying Solr index structures we use, but we think there may be some value in providing a real-world production example to members of the IIIF community. This application has been in use for over a year at the Bodleian with very few problems, and only one known outstanding bug (see below).

The basic principle is that it transforms Solr documents into IIIF JSON-LD on-the-fly using [Serpy](https://github.com/clarkduvall/serpy) serializers. The serializers can be found in the `iiif/` directory. This pattern will likely be the most useful for reference. Other features that may be useful include handling of content negotiation (see `server.py`), de-referencing  objects, and our implementation of ActivityStreams and IIIF collections. Feel free to borrow as needed, or simply browse out of interest.

It uses Serpy as the Python microframework. If that doesn't work for you the code for managing request and for doing the actual processing is fairly well separated, and swapping out a different framework should not be a particularly onerous task. (The most likely source of difficulty will be figuring out how the different frameworks handle incoming request patterns and request headers.)

To make the most out of the application you should configure your front-end server to pass along the original request URLs in the `X-Forwarded-Host` and `X-Forwarded-Proto` headers. In our Nginx configuration this looks like:

```
proxy_set_header        X-Real-IP $remote_addr;
proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header        X-Forwarded-Host $host;
proxy_set_header        Host $host;
proxy_set_header        X-Forwarded-Proto $scheme;
proxy_set_header        X-Scheme $scheme;
```

This allows the manifest server to pick up on the incoming request header and use it as the value of the URIs
it generates for the `@id` parameters, which can be handy for testing that the linking and resolving functions work within a staging or QA environment before deploying to a public server.

There are unit tests but, again, they reference Bodleian-specific UUIDs. We currently have 95% test coverage,
so if you do get it to work with your setup then the tests provide near-comprehensive coverage.

### Notes about the Solr Setup

Some things to note about the underlying Solr structure.

We index our data from METS/MODS files. In this process, we extract the data into several record types: 'object' (for the main record), 'surface' (rougly equivalent to the IIIF canvas), 'image' (points to the image path on disk), 'work' (used to identify the intellectual components of a record, e.g., chapters), and several other types.

We use UUIDs for our record IDs. These are assigned to images and objects when they are catalogued, and then
indexed to Solr. Some Solr record IDs are not strictly UUIDs. In our METS/MODS the assigned UUID for an image is then translated to `[UUID]_surface` and `[UUID]_image` as the Solr document ID. 

Images are indexed as child documents of their surface. In theory we can support multiple images per canvas, but have no records at the moment where that is the case.

A fairly comprehensive list of the types of metadata we store in Solr is available in the `helpers/metadata.py` 
file. (Not all of these values are used on all records, of course!)

We have included a set of sample records and our Solr configuration files. With those two you should be able to set up a
local version of our manifest server to play with.

Once you have a Solr core configured with the provided schema and configuration, you can load the data into Solr with
with `curl`. Assuming you have called your Solr core "manifest_server", load it like this (repeat for the other file):

    curl 'http://localhost:8983/solr/manifest_server/update?commit=true' --data-binary @whats_the_score.json -H 'Content-type:application/json'



### What about images?

This service only deals with delivering Presentation API data. Our image delivery systems are separate, built using the [IIP Image Server](https://iipimage.sourceforge.io/).

### Known bugs

Range de-referencing for IIIFv3 manifests does not currently work.

### Bonus Features!

Also included in this release are two handy little classes.

The first, in `manifest_server/helpers/solr.py` is our SolrManager class. This wraps the `pysolr` library,
but provides a handy way of iterating through all results in a paged response from Solr. It will `yield` a
result document and, if it gets to the end of the list, will automatically request the next page and then
continue. This is handy for serializing IIIF manifests with lots of canvases.

The second is a small modification to the default `serpy.DictSerializer` class, `ContextDictSerializer` that provides two handy features. It features a `context` parameter which can be used to pass data down through nested serializers; we use it to pass along the original request, for example, so that nested serializers can have access to the incoming request object. It will also automatically strip out any keys that have a value
of `None` in the JSON-LD response, so that your IIIF manifests will only contain fields that have values.

### Support

This software, of course, comes with no guarantee of support. We're on the IIIF Slack channel, and can answer questions on a best-effort basis. If and when we find bugs in our production version we will update this project, with some lag. We have passed it through a fairly rigorous security and vulnerability scan, but make no
guarantees that it won't, at some point, blow up. Caveat programmer.


