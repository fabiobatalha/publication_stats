# coding: utf-8
import logging
from datetime import datetime, timedelta
import argparse

import requests

from elasticsearch import Elasticsearch
from elasticsearch.client import IndicesClient
from xylose.scielodocument import Article, Journal

import choices

ARTICLEMETA = "http://articlemeta.scielo.org/api/v1"
ISO_3166_COUNTRY_AS_KEY = {value: key for key, value in choices.ISO_3166.items()}

FROM = datetime.now() - timedelta(days=30)
FROM.isoformat()[:10]

ES = Elasticsearch()


def _config_logging(logging_level='INFO', logging_file=None):

    allowed_levels = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }

    logging_config = {
        'level': allowed_levels.get(logging_level, 'INFO'),
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    }

    if logging_file:
        logging_config['filename'] = logging_file

    logging.basicConfig(**logging_config)


def do_request(url, params):

    response = requests.get(url, params=params).json()

    return response



def fmt_document(document):
    return document


def fmt_journal(document):
    data = {}

    data['id'] = '_'.join([document.collection_acronym, document.scielo_issn])
    data['issn'] = document.scielo_issn
    data['collection'] = document.collection_acronym
    data['subject_areas'] = document.subject_areas
    data['included_at_year'] = document.creation_date[0:4]
    data['status'] = document.current_status
    data['title'] = document.title

    yield data


def country(country):
    if country in choices.ISO_3166:
        return country
    if country in ISO_3166_COUNTRY_AS_KEY:
        return ISO_3166_COUNTRY_AS_KEY[country]
    return 'undefined'


def pages(first, last):

    try:
        pages = int(last)-int(first)
    except:
        pages = 0

    if pages >= 0:
        return pages
    else:
        return 0


def fmt_article(document, collection='BR'):
    data = {}

    data['id'] = '_'.join([document.collection_acronym, document.publisher_id])
    data['pid'] = document.publisher_id
    data['issn'] = document.journal.scielo_issn
    data['journal_title'] = document.journal.title
    data['issue'] = '_'.join([document.collection_acronym, document.publisher_id[0:18]])
    data['publication_date'] = document.publication_date
    data['publication_year'] = document.publication_date[0:4]
    data['subject_areas'] = [i for i in document.journal.subject_areas]
    data['collection'] = document.collection_acronym
    data['document_type'] = document.document_type
    pgs = pages(document.start_page, document.end_page)
    data['pages'] = pgs
    data['languages'] = list(set([i for i in document.languages().keys()]+[document.original_language() or 'undefined']))
    data['aff_countries'] = ['undefined']
    if document.mixed_affiliations:
        data['aff_countries'] = list(set([country(aff.get('country', 'undefined')) for aff in document.mixed_affiliations]))
    data['citations'] = len(document.citations or [])

    yield data

def fmt_citation(document, collection='BR'):

    for citation in document.citations or []:
        data = {}
        data['id'] = '_'.join([document.collection_acronym, document.publisher_id, str(citation.index_number)])
        data['pid'] = document.publisher_id
        data['citation_type'] = citation.publication_type
        data['publication_year'] = citation.date[0:4]
        data['collection'] = document.collection_acronym

        yield data


def documents(endpoint, fmt=None, from_date=FROM):

    allowed_endpoints = ['journal', 'article', 'citation']

    if not endpoint in allowed_endpoints:
        raise TypeError('Invalid endpoint, expected one of: %s' % str(allowed_endpoints))

    params = {'offset': 0, 'from': from_date}

    if endpoint == 'article':
        xylose_model = Article
    elif endpoint == 'journal':
        xylose_model = Journal

    while True:
        identifiers = do_request(
            '{0}/{1}/identifiers'.format(ARTICLEMETA, endpoint),
            params
        )

        logging.debug('offset %s' % str(params['offset']))

        logging.debug('len identifiers %s' % str(len(identifiers['objects'])))

        if len(identifiers['objects']) == 0:
            raise StopIteration

        for identifier in identifiers['objects']:
            dparams = {
                'collection': identifier['collection']
            }

            if endpoint == 'article':
                dparams['code'] = identifier['code']
                if dparams['code'] == None:
                    continue

            elif endpoint == 'journal':
                dparams['issn'] = identifier['code'][0]
                if dparams['issn'] == None:
                    continue

            document = do_request(
                '{0}/{1}'.format(ARTICLEMETA, endpoint), dparams
            )

            if isinstance(document, dict):
                doc_ret = document
            elif isinstance(document, list):
                doc_ret = document[0]


            for item in fmt(xylose_model(doc_ret)):
                yield item

        params['offset'] += 1000


def main(doc_type, from_date=FROM):

    journal_settings_mappings = {      
        "mappings": {
            "journal": {
                "properties": {
                    "collection": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "id": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "issn": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "subject_areas": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "title": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "included_at_year": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "status": {
                        "type": "string",
                        "index" : "not_analyzed"
                    }
                }
            },
            "citation": {
                "properties": {
                    "collection": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "id": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "pid": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "citation_type": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "publication_year": {
                        "type": "string",
                        "index" : "not_analyzed"
                    }
                }
            },
            "article": {
                "properties": {
                    "id": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "pid": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "issn": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "issue": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "subject_areas": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "collection": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "languages": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "aff_countries": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "document_type": {
                        "type": "string",
                        "index" : "not_analyzed"
                    },
                    "journal_title": {
                        "type": "string",
                        "index" : "not_analyzed"
                    }
                }
            }
        }
    }

    try:
        ES.indices.create(index='production', body=journal_settings_mappings)
    except:
        logging.debug('Index already available')

    if doc_type == 'journal':
        endpoint = 'journal'
        fmt = fmt_journal
    elif doc_type == 'article':
        endpoint = 'article'
        fmt = fmt_article
    elif doc_type == 'citation':
        endpoint = 'article'
        fmt = fmt_citation
    else:
        logging.error('Invalid doc_type')
        exit()

    for document in documents(endpoint, fmt, from_date=from_date):
        logging.debug('loading document %s into index %s' % (document['id'], doc_type))
        ES.index(
            index='production',
            doc_type=doc_type,
            id=document['id'],
            body=document
        )

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description="Load SciELO Network data no analytics production"
    )

    parser.add_argument(
        '--from_date',
        '-f',
        default=FROM,
        help='ISO date like 2013-12-31'
    )

    parser.add_argument(
        '--logging_file',
        '-o',
        default='/tmp/dumpdata.log',
        help='Full path to the log file'
    )

    parser.add_argument(
        '--doc_type',
        '-d',
        choices=['article', 'journal', 'citation'],
        help='Document type that will be updated'
    )

    parser.add_argument(
        '--logging_level',
        '-l',
        default='DEBUG',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logggin level'
    )

    args = parser.parse_args()

    _config_logging(args.logging_level, args.logging_file)

    main(doc_type=args.doc_type, from_date=args.from_date)
