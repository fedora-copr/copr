class SourceType:
    LINK = 1
    UPLOAD = 2
    GIT_AND_TITO = 3
    MOCK_SCM = 4
    PYPI = 5
    RUBYGEMS = 6
    DISTGIT = 7


class DistGitProvider(object):
    def __init__(self, source_json):
        self.clone_url = source_json["clone_url"]
        self.branch = source_json["branch"]

    def run(self):
        pass


def main():
    source_json = None
    provider = DistGitProvider(source_json)


if __name__ == "__main__":
    main()