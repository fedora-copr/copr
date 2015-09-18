# coding: utf-8

from logging import basicConfig, getLogger
import time
from copr.client_v2.net_client import RequestError
from copr.client_v2.resources import Build
basicConfig()
log = getLogger(__name__)


#from copr.client_v2.client import CoprClient
# from copr.client_v2.entities import ProjectEntity

from copr import create_client2_from_params


def main():
    copr_url = "http://copr-fe-dev.cloud.fedoraproject.org"
    client = create_client2_from_params(
        root_url=copr_url,
        login="wczictdaerhmwfxolham",
        token="kxcnwfmleulpnkckzspxxgwhxjolhc"
    )

    def pp(project):
        print("Project: {} id {}, {}\n {}\n{}".format(
            project.name,
            project.id,
            project.description,
            project.repos,
            [(x, y.href) for x, y in project._links.items()]
        ))

    def t1():
        project = client.projects.get_one(2262)
        #
        pp(project)
        # import ipdb; ipdb.set_trace()
        x = 2

    # res = project.update()
    # print(res)
    #
    def t3(project):
        p = project.get_self()
        pp(p)

    def t2():
        plist = client.projects.get_list(limit=20)
        for p in plist:
            #print(p)
            #print(p.get_href_by_name("builds"))
            pp(p)
            print("==")
            print("==")
            print("==")


    #t1()
    # t2()

    def t4():
        project = client.projects.get_one(3554)
        #pp(project)
        #print(project._response.json)

        name = "fedora-21-x86_64"
        #pc = project.get_project_chroot(name)
        #print(pc)
        for pc in project.get_project_chroot_list():
            print(pc)

    t4()

    def t5():
        build = client.builds.get_one(117578)
        #build._handle.cancel(build._entity)
        build._handle.delete(build.id)
        #import ipdb; ipdb.set_trace()
        build = client.builds.get_one(117578)
        print(build)

    # t5()

    def t6():

        project = client.projects.get_one(3554)
        print(project)

        # new_c = project.get_project_chroot("epel-5-x86_64")
        # print(new_c)
        # new_c.disable()
        # time.sleep(3)

        for pc in project.get_project_chroot_list():
            print(pc)
            # pc.disable()



        x = 2

    t6()

    #
    def t7():

        srpm = "http://miroslav.suchy.cz/copr/copr-ping-1-1.fc20.src.rpm"

        b = client.builds.create_from_url(project_id=4007, srpm_url=srpm)
        """:type: Build"""
        print(b)
        b.cancel()
        b = b.get_self()
        print(b)
        #op = b.delete()
        #print(op)

    # t7()

    def t8():

        srpm = "/tmp/tito/copr-backend-1.73.tar.gz"
        b = client.builds.create_from_file(project_id=4007, file_path=srpm)
        print(b)
        b.cancel()
        b = b.get_self()
        print(b)

    # t8()

    def t9():

        mcl = client.mock_chroots.get_list(active_only=False)
        for mc in mcl:
            print(mc)

    # t9()

    def t10():
        pass

if __name__ == "__main__":
    try:
        main()
    except RequestError as err:
        log.exception(err)
        log.error("error occurred while fetching: {}, with params: {}"
                  .format(err.url, err.request_kwargs))
        log.error("status code: {}, message: {} {}"
                  .format(err.response.status_code, err.msg, err.response_json))
    except Exception:
        log.exception("something went wrong")
