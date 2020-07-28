.. warning::
    Legacy client is obsolete, please use Client version 3 instead. :ref:`This document <migration>` describes the migration process.


Create client
-------------
::

    from copr.client import CoprClient

    # using default config location  ~/.config/copr
    cl = CoprClient.create_from_file_config()

    # using config at ~/.config/alt_copr
    cl = CoprClient.create_from_file_config("~/.config/alt_copr")

    # directly
    cl = CoprClient(username="foo", login="abcd", token="efgk", copr_url="http://example.com/")

Get projects list
-----------------
::

    # your projects
    result = cl.get_projects_list().projects_list

    # other user projects
    result = cl.get_projects_list(username="rhscl")

    # print list for humans and machines
    from pprint import pprint
    for prj in result.projects_list:
        print(prj)
        pprint(prj.get_project_details().data)


Search for projects
-------------------
::

    result = cl.search_projects("python")
    # print list for humans
    for prj in result.projects_list:
        print(prj)



Create/update/delete project
----------------------------
::

    result = cl.create_project("hello_world", chroots=["fedora-20-x86_64"],
        description="My cool app")

    # assert correct description
    assert result.handle.get_project_details().description == "My cool app"

    # add instruction
    result.handle.modify_project(instructions="How does one patch KDE2 under FreeBSD?")
    # which is shorter than
    cl.modify_project("hello_world", instructions="...")

    # delete project
    result.handle.delete_project()
    # again shortcut for
    cl.delete_project("hello_world")



Work with builds
----------------
::

    # building new package
    result = cl.create_new_build("hello_world",
        pkgs=["http://example.com/pkg.src.rpm",])

    # retrieve build statuses
    for bw in result.builds_list:
        print("{0}:{1}".format(bw.build_id, bw.handle.get_build_details().status))

    # cancel all created build
    for bw in result.builds_list:
        bw.handle.cancel_build()

    # get build status for each chroot
    for bw in result.builds_list:
        print("build: {0}".format(bw.build_id))
        for ch, status in bw.handle.get_build_details().data["chroots"].items():
            print("\t chroot {0}:\t {1}".format(ch, status))

    # simple build progress:
    import time, datetime
    watched = set(result.builds_list)
    done = set()
    while watched != done:
        print("time: {0}".format(datetime.datetime.now()))
        for bw in watched:
            if bw in done:
                continue
            status = bw.handle.get_build_details().status
            print("{0}: {1}".format(bw.build_id, status))
            if status in ["skipped", "failed", "succeeded"]:
                done.add(bw)
        time.sleep(10)

    # cancel all created build
    for bw in result.builds_list:
        bw.handle.cancel_build()
