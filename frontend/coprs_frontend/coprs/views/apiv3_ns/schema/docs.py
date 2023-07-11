"""
File for documentation for unicorn/small documentation in our API for Flask-restx.
 Some are manually written for passing it directly to Swagger UI.
"""

from coprs.views.apiv3_ns.schema import fields
from coprs.views.apiv3_ns.schema.fields import source_type, id_field


def _generate_docs(field_names, extra_fields=None):
    result_dict = {}
    for field_name in field_names:
        result_dict[field_name] = getattr(fields, field_name).description

    if extra_fields is None:
        return result_dict

    return result_dict | extra_fields


query_docs = {
    "query": {
        "description": "Search projects according query keyword.",
        "example": "copr-cli",
    }
}

fullname_attrs = {"ownername", "projectname"}
fullname_docs = _generate_docs(fullname_attrs)

src_type_dict = {"source_type_text": source_type.description}
add_package_docs = _generate_docs(fullname_attrs | {"package_name"}, src_type_dict)

edit_package_docs = _generate_docs(fullname_docs, src_type_dict)

get_build_docs = _generate_docs({}, {"build_id": id_field.description})
