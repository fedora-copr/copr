from sqlalchemy import types
from sqlalchemy.ext import compiler

class Tsvector(types.UnicodeText):
    # TODO: define the custom operator to perform fulltext searches ?
    pass

@compiler.compiles(Tsvector, 'postgresql')
def compile_tsvector(element, compiler, **kw):
    return 'tsvector'
