from sqlalchemy import func
from sqlalchemy import types
from sqlalchemy.ext import compiler

from coprs import db

class Tsvector(types.UnicodeText):
    # TODO: define the custom operator to perform fulltext searches ?
    pass

@compiler.compiles(Tsvector, 'postgresql')
def compile_tsvector(element, compiler, **kw):
    return 'tsvector'

@compiler.compiles(Tsvector, 'sqlite')
def compile_tsvector(element, compiler, **kw):
    return 'text'


class FullTextQuery(db.Query):
    def fulltext(self, column, search_string):
        if db.engine.dialect.name == 'postgresql':
            search_with_or = ' | '.join(search_string.split())
            return self.filter(column.op('@@@')(func.to_tsquery(search_with_or)))
        else:
            return self.filter(column.like('%{0}%'.format(search_string)))
