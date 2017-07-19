# coding: utf-8


from dist_git.providers import DistGitProvider


class TestDistGitProvider(object):
    def test_module_name(self):
        provider = DistGitProvider(None)

        # http://copr-dist-git.fedorainfracloud.org/git/frostyx/hello/hello.git
        assert provider.module_name("/git/frostyx/hello/hello.git") == "frostyx/hello/hello"
        assert provider.module_name("/cgit/frostyx/hello/hello.git") == "frostyx/hello/hello"

        # https://src.fedoraproject.org/git/rpms/hello.git
        assert provider.module_name("/git/rpms/hello.git") == "rpms/hello"
