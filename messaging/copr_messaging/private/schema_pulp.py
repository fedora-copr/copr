"""Optional Pulp metadata shared by the legacy message formats."""


PULP_METADATA_SCHEMA = {
    "type": "object",
    "description": "Optional Pulp metadata for the completed build.",
    "properties": {
        "publication_href": {
            "type": "string",
            "minLength": 1,
            "description":
                "Relative Pulp API href of the last publication captured while "
                "processing this build in this chroot. It may include other "
                "builds or omit RPMs replaced during batching or concurrent "
                "updates. Availability depends on the retention policy.",
        },
    },
}
